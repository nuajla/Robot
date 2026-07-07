"""
ROS camera feed + panda_ros/PandaGripper motion control.

The pixel->robot affine transform and the 8-step grasp/pull motion sequence
are ported unchanged from cloth_pick_place_selector.py (same Z heights, same
step order) -- only the values now come from config.yaml instead of being
hard-coded, and the sequence runs from an HTTP request instead of a
keypress.

rospy / cv_bridge / robotblockset are imported lazily, inside __init__, not
at module load time, so this module -- and the whole Flask app -- can still
be imported on a machine without ROS (e.g. a Windows laptop with
capture.source=static_file and robot.enabled=false; see camera.py).

Unlike the SAM3 model in the sibling app, the ROS/robot connection is
established eagerly at construction, not deferred to first use: for a
physical arm, a broken connection should raise immediately at startup, not
silently on whatever request happens to be first.
"""

import logging
import threading
import time

import numpy as np

log = logging.getLogger(__name__)


class RobotController:
    """Owns the ROS node: the camera subscription and, when enabled, the arm."""

    def __init__(self, cfg: dict):
        self.rcfg = cfg["robot"]
        self.ccfg = cfg["capture"]
        self.enabled = bool(self.rcfg["enabled"])
        self.affine = np.array(self.rcfg["affine_matrix"], dtype=np.float64)
        if self.affine.shape != (2, 3):
            raise ValueError(f"robot.affine_matrix must be 2x3, got {self.affine.shape}")

        self._frame_lock = threading.Lock()
        self._latest_frame = None  # BGR np.ndarray, updated by the ROS callback

        self._ros_ready = False
        self._robot = None
        self._gripper = None

        needs_ros = self.ccfg["source"] == "ros_topic" or self.enabled
        if needs_ros:
            self._init_ros()
        if self.enabled:
            self._init_robot()
        else:
            log.warning("robot.enabled=false -- motions will be SIMULATED (logged, not executed).")

    # ---------------------------------------------------------------------
    # Setup
    # ---------------------------------------------------------------------

    def _init_ros(self):
        import rospy
        from cv_bridge import CvBridge
        from sensor_msgs.msg import Image

        self._bridge = CvBridge()

        # disable_signals: this node lives inside the Flask process, so let
        # Werkzeug/Flask keep handling Ctrl+C instead of rospy's own handler.
        rospy.init_node(self.rcfg["node_name"], anonymous=False, disable_signals=True)
        time.sleep(1.0)  # let the node register with the ROS master first

        if self.ccfg["source"] == "ros_topic":
            rospy.Subscriber(self.ccfg["image_topic"], Image, self._on_image, queue_size=1)
            log.info("Subscribed to %s", self.ccfg["image_topic"])
        self._ros_ready = True

    def _init_robot(self):
        from robotblockset.ros.franka_ros import panda_ros
        from robotblockset.ros.grippers_ros import PandaGripper

        log.info("Connecting to robot (namespace=%s) ...", self.rcfg["namespace"])
        self._robot = panda_ros(ns=self.rcfg["namespace"],
                                 control_strategy=self.rcfg["control_strategy"],
                                 init_node=False)
        self._gripper = PandaGripper(robot=self._robot, namespace=self.rcfg["namespace"])
        self._robot.ErrorRecovery()
        self._robot.Start()
        if self.rcfg["home_on_start"]:
            log.info("Moving to home pose ...")
            self._robot.JMove(self._robot.q_home, t=self.rcfg["home_time"])
        log.info("Robot ready.")

    # ---------------------------------------------------------------------
    # Camera
    # ---------------------------------------------------------------------

    def _on_image(self, msg):
        img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")
        with self._frame_lock:
            self._latest_frame = img

    def get_frame(self):
        """Return the latest ROS frame (BGR), waiting up to wait_timeout_s for
        the first one to arrive."""
        if not self._ros_ready:
            raise RuntimeError("capture.source is not 'ros_topic' -- no ROS image subscription.")
        deadline = time.time() + float(self.ccfg["wait_timeout_s"])
        while True:
            with self._frame_lock:
                if self._latest_frame is not None:
                    return self._latest_frame.copy()
            if time.time() > deadline:
                raise TimeoutError(
                    f"Timed out waiting for a frame on {self.ccfg['image_topic']}. "
                    f"Is the camera node running?")
            time.sleep(float(self.ccfg["poll_interval_s"]))

    # ---------------------------------------------------------------------
    # Motion
    # ---------------------------------------------------------------------

    def pixel_to_robot_xy(self, px):
        """Pixel (u, v) in the raw, un-cropped capture frame -> robot (X, Y) metres."""
        u, v = px
        xy = self.affine.dot(np.array([u, v, 1.0]))
        return float(xy[0]), float(xy[1])

    def execute_pick_place(self, pick_px, place_px):
        """
        Convert pick/place pixels to robot XY and run the grasp/pull sequence.
        Returns (pick_xy, place_xy) in robot metres.

        Simulated (logged only, no hardware calls) when robot.enabled=false,
        so the rest of the app (camera + dataset recording) can still be
        exercised end-to-end without moving the physical arm.
        """
        gx, gy = self.pixel_to_robot_xy(pick_px)
        plx, ply = self.pixel_to_robot_xy(place_px)

        if not self.enabled:
            log.info("[SIMULATED] pick=(%.4f, %.4f) place=(%.4f, %.4f) -- robot.enabled=false",
                      gx, gy, plx, ply)
            return (gx, gy), (plx, ply)

        r, g = self._robot, self._gripper
        z_above, z_grasp, z_pull = self.rcfg["z_above"], self.rcfg["z_grasp"], self.rcfg["z_pull"]
        gripper_open = self.rcfg["gripper_open"]
        move_t, grasp_t, home_t = self.rcfg["move_time"], self.rcfg["grasp_time"], self.rcfg["home_time"]

        log.info("[ACTION] pick=(%.4f, %.4f) place=(%.4f, %.4f)", gx, gy, plx, ply)

        log.info("[1] Opening gripper ...")
        g.Move(gripper_open)
        time.sleep(0.5)

        log.info("[2] Moving above pick, Z=%.3f ...", z_above)
        r.CMove([gx, gy, z_above], t=move_t)

        log.info("[3] Descending to Z=%.3f ...", z_grasp)
        r.CMove([gx, gy, z_grasp], t=grasp_t)

        log.info("[4] Closing gripper ...")
        g.Close()
        time.sleep(0.5)

        log.info("[5] Lifting to Z=%.3f ...", z_pull)
        r.CMove([gx, gy, z_pull], t=grasp_t)

        log.info("[6] Moving above place, Z=%.3f ...", z_pull)
        r.CMove([plx, ply, z_pull], t=move_t)

        log.info("[7] Releasing cloth ...")
        g.Move(gripper_open)
        time.sleep(0.5)

        log.info("[8] Returning home ...")
        r.JMove(r.q_home, t=home_t)

        log.info("[DONE] Action complete.")
        return (gx, gy), (plx, ply)

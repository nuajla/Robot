#!/usr/bin/env python3
"""
cloth_pick_place_direct.py
----------------------------
Vse v enem procesu - bere sliko, prikaze okno za izbiro pick/place tock,
transformira jih preko afine matrike, in NEPOSREDNO poklice robota
(panda_ros + PandaGripper) - brez vmesnega /cloth_action topica.

To odpravi problem "prvo sporocilo izgubljeno" (subscriber connection
race condition), ker ni vec locenega publisherja/subscriberja med dvema
procesoma - vse tece v enem node-u.

Zazeni:
    conda activate franka
    export PYTHONPATH=/opt/ros/noetic/lib/python3/dist-packages:/home/ajla/rbs_ws/devel/lib/python3/dist-packages:$PYTHONPATH
    export ROS_MASTER_URI=http://10.20.0.5:11311
    export ROS_IP=10.20.0.5
    export LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libffi.so.7
    python cloth_pick_place_direct.py

Tipke v oknu:
    LMB = grasp tocka (zelena)
    RMB = pull/place tocka (rdeca)
    s   = IZVEDI akcijo na robotu (blokira okno dokler robot ne konca)
    r   = reset izbire
    q   = izhod
"""

import time

import cv2
import numpy as np
import rospy
from cv_bridge import CvBridge
from sensor_msgs.msg import Image

from robotblockset.ros.franka_ros import panda_ros
from robotblockset.ros.grippers_ros import PandaGripper

# ----------------------------------------------------------------------
# NASTAVITVE
# ----------------------------------------------------------------------
IMAGE_TOPIC = "/rgb/image_raw"          # prilagodi, ce je drugace poimenovan
NS = "pingvin_1"

# afina matrika: pixel(u,v) -> robot(X,Y)
AFFINE_MATRIX = np.array([
    [7.16447629e-07, 1.13357811e-03, -3.02383482e-01],
    [1.13117136e-03, 6.03340945e-06, -1.05554366e+00],
], dtype=np.float64)

Z_ABOVE = 0.20
Z_GRASP = 0.11
Z_PULL = 0.13

MOVE_TIME = 3.0
GRASP_TIME = 1.0


class ClothPickPlaceDirect:
    WINDOW_NAME = "Pick & Place (LMB=grasp, RMB=pull, s=IZVEDI, r=reset, q=izhod)"

    def __init__(self):
        self.bridge = CvBridge()
        self.M = AFFINE_MATRIX  # oblika (2, 3)

        self.color_img = None
        self.grasp_px = None
        self.pull_px = None
        self.busy = False  # True med izvajanjem giba na robotu

        rospy.loginfo("Inicializacija robota...")
        self.r = panda_ros(ns=NS, control_strategy="JointImpedance", init_node=False)
        self.g = PandaGripper(robot=self.r, namespace=NS)
        self.r.ErrorRecovery()
        self.r.Start()

        rospy.loginfo("Premik v home pozo...")
        self.r.JMove(self.r.q_home, t=4)

        rospy.Subscriber(IMAGE_TOPIC, Image, self._image_cb, queue_size=1)

        cv2.namedWindow(self.WINDOW_NAME)
        cv2.setMouseCallback(self.WINDOW_NAME, self._on_mouse)

        rospy.loginfo("Cakam na prvo sliko ...")

    # -- callbacki ----------------------------------------------------
    def _image_cb(self, msg):
        self.color_img = self.bridge.imgmsg_to_cv2(msg, desired_encoding="bgr8")

    def _on_mouse(self, event, u, v, flags, param):
        if self.busy:
            return  # ne dovoli klika med izvajanjem giba
        if event == cv2.EVENT_LBUTTONDOWN:
            self.grasp_px = (u, v)
            rospy.loginfo(f"GRASP piksel: {self.grasp_px}")
        elif event == cv2.EVENT_RBUTTONDOWN:
            self.pull_px = (u, v)
            rospy.loginfo(f"PULL piksel: {self.pull_px}")

    # -- pomozno --------------------------------------------------------
    def _pixel_to_robot_xy(self, px):
        u, v = px
        point_h = np.array([u, v, 1.0])
        xy = self.M.dot(point_h)
        return float(xy[0]), float(xy[1])

    def _draw_overlay(self, img):
        disp = img.copy()
        if self.grasp_px:
            cv2.drawMarker(disp, self.grasp_px, (0, 255, 0), cv2.MARKER_CROSS, 20, 2)
            cv2.putText(disp, "GRASP", (self.grasp_px[0] + 10, self.grasp_px[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        if self.pull_px:
            cv2.drawMarker(disp, self.pull_px, (0, 0, 255), cv2.MARKER_CROSS, 20, 2)
            cv2.putText(disp, "PULL", (self.pull_px[0] + 10, self.pull_px[1] - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
        status = "ROBOT BUSY - izvaja gib..." if self.busy else "ROBOT READY"
        color = (0, 0, 200) if self.busy else (0, 200, 0)
        cv2.putText(disp, status, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)
        cv2.putText(disp, "LMB=grasp  RMB=pull  s=IZVEDI  r=reset  q=izhod",
                    (10, disp.shape[0] - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        return disp

    # -- izvedba giba na robotu (enako zaporedje kot execute_action.py) ------
    def _execute_cloth_action(self, gx, gy, px, py):
        rospy.loginfo(f"[ACTION] grasp=({gx:.4f}, {gy:.4f})  pull=({px:.4f}, {py:.4f})")

        rospy.loginfo("[1] Odpiranje gripperja...")
        self.g.Move(0.02)
        time.sleep(0.5)

        rospy.loginfo(f"[2] Premik nad grasp  Z={Z_ABOVE} m ...")
        self.r.CMove([gx, gy, Z_ABOVE], t=MOVE_TIME)

        rospy.loginfo(f"[3] Spust na Z={Z_GRASP} m ...")
        self.r.CMove([gx, gy, Z_GRASP], t=GRASP_TIME)

        rospy.loginfo("[4] Zapiranje gripperja...")
        self.g.Close()
        time.sleep(0.5)

        rospy.loginfo(f"[5] Dvig na Z={Z_PULL} m ...")
        self.r.CMove([gx, gy, Z_PULL], t=GRASP_TIME)

        rospy.loginfo(f"[6] Premik nad pull  Z={Z_PULL} m ...")
        self.r.CMove([px, py, Z_PULL], t=MOVE_TIME)

        rospy.loginfo("[7] Spust tkanine...")
        self.g.Move(0.02)
        time.sleep(0.5)

        rospy.loginfo("[8] Premik v home pozo...")
        self.r.JMove(self.r.q_home, t=4)

        rospy.loginfo("[DONE] Akcija zakljucena.\n")

    def _run_action(self):
        if self.grasp_px is None or self.pull_px is None:
            rospy.logwarn("Manjka grasp ali pull tocka - izberi obe.")
            return
        if self.busy:
            rospy.logwarn("Robot ze izvaja gib, pocakaj.")
            return

        gx, gy = self._pixel_to_robot_xy(self.grasp_px)
        px, py = self._pixel_to_robot_xy(self.pull_px)

        self.busy = True
        # Osvezi prikaz "BUSY" preden zablokiramo z izvajanjem giba
        if self.color_img is not None:
            cv2.imshow(self.WINDOW_NAME, self._draw_overlay(self.color_img))
            cv2.waitKey(1)

        try:
            self._execute_cloth_action(gx, gy, px, py)
        except Exception as e:
            rospy.logerr(f"[ERROR] Napaka med akcijo: {e}")
        finally:
            self.busy = False
            self.grasp_px = None
            self.pull_px = None

    # -- glavna zanka -----------------------------------------------------
    def spin(self):
        rate = rospy.Rate(30)
        while not rospy.is_shutdown():
            if self.color_img is not None:
                disp = self._draw_overlay(self.color_img)
                cv2.imshow(self.WINDOW_NAME, disp)

            key = cv2.waitKey(1) & 0xFF
            if key == ord("q"):
                break
            elif key == ord("r") and not self.busy:
                self.grasp_px = None
                self.pull_px = None
                rospy.loginfo("Izbira ponastavljena.")
            elif key == ord("s"):
                self._run_action()

            rate.sleep()

        cv2.destroyAllWindows()


def main():
    rospy.init_node("cloth_pick_place_direct", anonymous=False)
    time.sleep(1.0)
    node = ClothPickPlaceDirect()
    node.spin()


if __name__ == "__main__":
    main()
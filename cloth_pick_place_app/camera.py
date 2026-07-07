"""
Frame capture dispatch.

Two capture sources, selected by config `capture.source`:

  * ros_topic   -- delegate to the RobotController's latest ROS frame (see
                   robot.py; same /rgb/image_raw feed cloth_pick_place_selector.py
                   subscribes to).
  * static_file -- read a fixed image from disk. Lets the whole UI be tested
                   on a Windows laptop with no camera/ROS attached.

No silent fallbacks: if a configured file is missing or the camera times
out, this raises so the error is visible in the UI and the logs.
"""

import logging

import cv2

log = logging.getLogger(__name__)


def capture_frame(cfg, robot):
    """Return one BGR frame (np.ndarray) from the configured source."""
    source = cfg["capture"]["source"]
    if source == "ros_topic":
        return robot.get_frame()
    if source == "static_file":
        path = cfg["paths"]["static_rgb_path"]
        img = cv2.imread(path)
        if img is None:
            raise FileNotFoundError(f"Could not read static RGB image at {path}")
        return img
    raise ValueError(f"Unknown capture.source: {source!r} (use 'ros_topic' or 'static_file')")

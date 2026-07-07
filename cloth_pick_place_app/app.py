"""
Cloth Pick&Place Data-Collection web app.

Runs on the same PC as the robot/ROS stack (see cloth_pick_place_selector.py).
Flow: capture a frame, click a start (pick) point and an end (place) point,
click Execute -- the robot moves the cloth from start to end and the point
pair is recorded. Repeat any number of times on the same cloth; click Finish
to capture the final image and close the episode out.

Start with:  python app.py   (config.yaml in the same folder)
"""

import base64
import logging
import os
import random
import threading
import time
from datetime import datetime

import cv2
import numpy as np
import yaml
from flask import Flask, jsonify, render_template, request

import camera
import dataset_io
from robot import RobotController

APP_DIR = os.path.dirname(os.path.abspath(__file__))
CONFIG_PATH = os.path.join(APP_DIR, "config.yaml")

log = logging.getLogger("cloth_pickplace_app")

app = Flask(__name__)

# Cache-bust static files on every server restart so browsers always load fresh JS/CSS.
_STATIC_VERSION = int(time.time())


@app.context_processor
def inject_version():
    return {"version": _STATIC_VERSION}


# Single-operator server state, guarded by a lock (an active episode + the
# frame the operator is currently picking points on).
_LOCK = threading.Lock()
STATE = {
    "episode_id": None,
    "started_at": None,
    "step_index": 0,
    "frame": None,    # BGR np.ndarray currently on the operator's canvas
    "frame_w": None,
    "frame_h": None,
}

CFG = None
ROBOT = None
DATASET_DIR = None


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

def _load_config():
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def _setup_logging(cfg):
    log_dir = cfg["logging"]["log_dir"]  # already resolved to an absolute path
    os.makedirs(log_dir, exist_ok=True)
    import datetime as _dt
    log_file = os.path.join(log_dir, f"cloth_pickplace_{_dt.date.today().isoformat()}.log")
    handlers = [logging.StreamHandler(), logging.FileHandler(log_file, encoding="utf-8")]
    logging.basicConfig(
        level=getattr(logging, cfg["logging"]["level"].upper()),
        format="%(asctime)s  %(levelname)-7s  %(name)s  %(message)s",
        handlers=handlers,
        force=True,
    )
    log.info("Full logs -> %s", log_file)


def initialise():
    """Load config, seed RNGs, connect to the camera/robot, resolve dataset folder."""
    global CFG, ROBOT, DATASET_DIR
    CFG = _load_config()
    dataset_io.resolve_local_paths(CFG, APP_DIR)
    _setup_logging(CFG)

    seed = int(CFG["seed"])
    random.seed(seed)
    np.random.seed(seed)
    log.info("Seeded RNGs with %d", seed)

    ROBOT = RobotController(CFG)

    DATASET_DIR = dataset_io.resolve_dataset_dir(CFG)
    dataset_io.init_dataset_dir(DATASET_DIR, CFG, CONFIG_PATH)
    log.info("Active dataset folder: %s", DATASET_DIR)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _to_data_url(bgr):
    ok, buf = cv2.imencode(".png", bgr)
    if not ok:
        raise RuntimeError("Failed to PNG-encode image.")
    return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode("ascii")


def _reset_episode_state():
    STATE.update(episode_id=None, started_at=None, step_index=0,
                 frame=None, frame_w=None, frame_h=None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/bootstrap")
def bootstrap():
    return jsonify({
        "dataset_dir": os.path.basename(DATASET_DIR),
        "capture_source": CFG["capture"]["source"],
        "image_topic": CFG["capture"]["image_topic"],
        "robot_enabled": CFG["robot"]["enabled"],
        "namespace": CFG["robot"]["namespace"],
        "summary": dataset_io.dataset_summary(DATASET_DIR),
    })


@app.route("/api/capture", methods=["POST"])
def capture():
    """Capture a frame. Starts a new episode if none is active yet."""
    with _LOCK:
        try:
            frame = camera.capture_frame(CFG, ROBOT)
        except Exception as exc:
            log.exception("Capture failed")
            return jsonify({"error": str(exc)}), 502

        if STATE["episode_id"] is None:
            idx = dataset_io.next_episode_index(DATASET_DIR)
            STATE["episode_id"] = f"ep{idx:03d}"
            STATE["started_at"] = datetime.now()
            STATE["step_index"] = 0
            log.info("Started episode %s", STATE["episode_id"])

        h, w = frame.shape[:2]
        STATE["frame"], STATE["frame_w"], STATE["frame_h"] = frame, w, h
        return jsonify({
            "image": _to_data_url(frame),
            "width": w,
            "height": h,
            "episode_id": STATE["episode_id"],
            "step_index": STATE["step_index"],
        })


@app.route("/api/execute", methods=["POST"])
def execute():
    """Run the pick->place motion and record the step."""
    data = request.get_json(force=True)
    pick, place = data.get("pick"), data.get("place")
    if not pick or not place:
        return jsonify({"error": "Both a start (pick) and end (place) point are required."}), 400

    with _LOCK:
        if STATE["episode_id"] is None or STATE["frame"] is None:
            return jsonify({"error": "Capture a frame first."}), 400

        pick_px = (round(pick[0]), round(pick[1]))
        place_px = (round(place[0]), round(place[1]))
        frame = STATE["frame"]

        try:
            pick_xy, place_xy = ROBOT.execute_pick_place(pick_px, place_px)
        except Exception as exc:
            log.exception("Robot execution failed")
            return jsonify({"error": f"Robot execution failed: {exc}"}), 500

        row = dataset_io.save_step(
            DATASET_DIR,
            episode_id=STATE["episode_id"], step_index=STATE["step_index"],
            frame=frame, pick_px=pick_px, place_px=place_px,
            pick_xy=pick_xy, place_xy=place_xy,
        )
        STATE["step_index"] += 1
        STATE["frame"] = None  # force a fresh capture before the next execute

        return jsonify({
            "row": row,
            "episode_id": STATE["episode_id"],
            "step_index": STATE["step_index"],
            "pick_xy": pick_xy,
            "place_xy": place_xy,
            "robot_enabled": CFG["robot"]["enabled"],
        })


@app.route("/api/finish", methods=["POST"])
def finish():
    """Capture the final image and close the active episode out."""
    data = request.get_json(silent=True) or {}
    with _LOCK:
        if STATE["episode_id"] is None:
            return jsonify({"error": "No active episode."}), 400
        if STATE["step_index"] == 0:
            return jsonify({"error": "Execute at least one action before finishing."}), 400

        try:
            final_frame = camera.capture_frame(CFG, ROBOT)
        except Exception as exc:
            log.exception("Final capture failed")
            return jsonify({"error": str(exc)}), 502

        row = dataset_io.finish_episode(
            DATASET_DIR,
            episode_id=STATE["episode_id"], num_steps=STATE["step_index"],
            frame=final_frame, started_at=STATE["started_at"],
            notes=data.get("notes", ""),
        )
        summary = dataset_io.dataset_summary(DATASET_DIR)
        _reset_episode_state()
        return jsonify({"episode": row, "summary": summary})


if __name__ == "__main__":
    initialise()
    log.info("Serving on http://%s:%s", CFG["server"]["host"], CFG["server"]["port"])
    app.run(host=CFG["server"]["host"], port=int(CFG["server"]["port"]),
            debug=bool(CFG["server"]["debug"]), use_reloader=False)

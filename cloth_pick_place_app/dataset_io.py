"""
Dataset folder management + episode/step writing.

Layout produced:

    cloth_pickplace_YYYY-MM-DD/
        README.md            # idea, protocol, how to use
        config.yaml           # exact config snapshot used for this dataset
        steps.csv              # one row per executed pick/place action
        episodes.csv            # one row per finished episode
        images/
            ep000/step00.png step01.png ... final.png
            ep001/ ...

An "episode" is one continuous run: cloth placed in frame, one or more
pick/place actions executed in sequence, then Finish. `steps.csv` has every
picked point pair; `episodes.csv` points at the final (post-last-action)
image.

No silent fallbacks: missing inputs raise.
"""

import csv
import datetime as _dt
import logging
import os
import shutil

import cv2

log = logging.getLogger(__name__)

STEP_FIELDS = [
    "episode_id", "step_index", "image_file",
    "pick_x_px", "pick_y_px", "place_x_px", "place_y_px",
    "pick_x_m", "pick_y_m", "place_x_m", "place_y_m",
    "image_width", "image_height", "timestamp",
]

EPISODE_FIELDS = [
    "episode_id", "num_steps", "final_image",
    "image_width", "image_height",
    "started_at", "finished_at", "duration_s", "notes",
]

_DATASET_README = """\
# Cloth Pick&Place Dataset ({folder})

Human-in-the-loop cloth pick-and-place trajectories. Each episode is one
continuous run: the cloth is placed in the frame, the operator clicks a
start (pick) point and an end (place) point on the live camera image, clicks
Execute, and the robot moves the cloth from start to end (same affine
pixel->robot transform and grasp/pull motion as `cloth_pick_place_selector.py`).
This can repeat any number of times on the same piece of cloth; clicking
Finish closes the episode out.

## Files
- `steps.csv` -- one row per executed action: episode, step index, the frame
  the points were clicked on, pick/place in both pixel and robot (metre)
  space.
- `episodes.csv` -- one row per finished episode: episode id, number of
  steps, and the final (post-last-action) image.
- `config.yaml` -- exact settings used (affine matrix, Z heights, timings).
- `images/<episode_id>/stepNN.png` -- the frame clicked on for step NN (the
  state *before* that action ran).
- `images/<episode_id>/final.png` -- the frame captured when Finish was
  clicked (the state *after* the last action).

## Coordinate convention
`pick_x_px` / `place_x_px` etc. are pixel coordinates in the raw, un-cropped
capture frame (see `image_width` / `image_height` for that frame's size).
`pick_x_m` / `place_x_m` etc. are the same points transformed into robot
frame metres via `config.yaml -> robot.affine_matrix`.

## Channel-order convention
Images are written with OpenCV (`cv2.imwrite`) and are therefore in **BGR**
byte order on disk.
"""


# Local (this-machine) paths that should be resolved relative to the app
# folder, not the current working directory.
_LOCAL_PATH_KEYS = [
    ("paths", "dataset_root"),
    ("paths", "static_rgb_path"),
    ("logging", "log_dir"),
]


def resolve_local_paths(cfg: dict, base_dir: str) -> dict:
    """Rewrite the local relative paths in-place to absolute paths under base_dir."""
    for section, key in _LOCAL_PATH_KEYS:
        val = cfg.get(section, {}).get(key, "")
        if val and not os.path.isabs(val):
            cfg[section][key] = os.path.normpath(os.path.join(base_dir, val))
    return cfg


# ---------------------------------------------------------------------------
# Folder resolution + initialisation
# ---------------------------------------------------------------------------

def resolve_dataset_dir(cfg: dict) -> str:
    """
    Decide which dated dataset folder to use:
      1. config dataset.folder_name, if set;
      2. otherwise the most recent existing <prefix>_* folder under dataset_root;
      3. otherwise a new <prefix>_<today> folder.
    """
    root = cfg["paths"]["dataset_root"]
    prefix = cfg["dataset"]["dated_folder_prefix"]
    os.makedirs(root, exist_ok=True)

    explicit = cfg["dataset"].get("folder_name") or ""
    if explicit:
        return os.path.join(root, explicit)

    existing = sorted(
        d for d in os.listdir(root)
        if d.startswith(prefix + "_") and os.path.isdir(os.path.join(root, d))
    )
    if existing:
        chosen = existing[-1]
        log.info("Reusing existing dataset folder: %s", chosen)
        return os.path.join(root, chosen)

    today = _dt.date.today().isoformat()
    return os.path.join(root, f"{prefix}_{today}")


def init_dataset_dir(dataset_dir: str, cfg: dict, config_src_path: str):
    """Create the folder skeleton and write README / config snapshot."""
    os.makedirs(os.path.join(dataset_dir, "images"), exist_ok=True)

    cfg_dst = os.path.join(dataset_dir, "config.yaml")
    if not os.path.exists(cfg_dst) and os.path.exists(config_src_path):
        shutil.copyfile(config_src_path, cfg_dst)

    readme = os.path.join(dataset_dir, "README.md")
    if not os.path.exists(readme):
        with open(readme, "w", encoding="utf-8") as f:
            f.write(_DATASET_README.format(folder=os.path.basename(dataset_dir)))

    _ensure_header(_steps_path(dataset_dir), STEP_FIELDS)
    _ensure_header(_episodes_path(dataset_dir), EPISODE_FIELDS)
    log.info("Dataset folder ready: %s", dataset_dir)


def _steps_path(dataset_dir: str) -> str:
    return os.path.join(dataset_dir, "steps.csv")


def _episodes_path(dataset_dir: str) -> str:
    return os.path.join(dataset_dir, "episodes.csv")


def _ensure_header(path: str, fields: list):
    if not os.path.exists(path):
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()
        return
    with open(path, "r", newline="", encoding="utf-8") as f:
        existing_header = next(csv.reader(f), [])
    if existing_header != fields:
        raise RuntimeError(
            f"{path} has a header that doesn't match the current schema. "
            f"Point config.yaml -> dataset.folder_name at a new folder, or "
            f"migrate this CSV by hand."
        )


# ---------------------------------------------------------------------------
# Episode numbering
# ---------------------------------------------------------------------------

def next_episode_index(dataset_dir: str) -> int:
    """Next free episode index (max existing + 1, else 0)."""
    images_dir = os.path.join(dataset_dir, "images")
    if not os.path.isdir(images_dir):
        return 0
    nums = []
    for name in os.listdir(images_dir):
        if name.startswith("ep") and name[2:].isdigit():
            nums.append(int(name[2:]))
    return (max(nums) + 1) if nums else 0


def dataset_summary(dataset_dir: str) -> dict:
    """{num_episodes, num_steps} for the header display."""
    num_episodes = 0
    path = _episodes_path(dataset_dir)
    if os.path.exists(path):
        with open(path, "r", newline="", encoding="utf-8") as f:
            num_episodes = sum(1 for _ in csv.DictReader(f))
    num_steps = 0
    path = _steps_path(dataset_dir)
    if os.path.exists(path):
        with open(path, "r", newline="", encoding="utf-8") as f:
            num_steps = sum(1 for _ in csv.DictReader(f))
    return {"num_episodes": num_episodes, "num_steps": num_steps}


# ---------------------------------------------------------------------------
# Writing
# ---------------------------------------------------------------------------

def save_step(dataset_dir, *, episode_id, step_index, frame,
              pick_px, place_px, pick_xy, place_xy):
    """Write images/<episode_id>/stepNN.png and append a steps.csv row."""
    ep_dir = os.path.join(dataset_dir, "images", episode_id)
    os.makedirs(ep_dir, exist_ok=True)

    h, w = frame.shape[:2]
    name = f"step{step_index:02d}.png"
    cv2.imwrite(os.path.join(ep_dir, name), frame)
    image_rel = os.path.join("images", episode_id, name).replace("\\", "/")

    row = {
        "episode_id": episode_id,
        "step_index": step_index,
        "image_file": image_rel,
        "pick_x_px": pick_px[0], "pick_y_px": pick_px[1],
        "place_x_px": place_px[0], "place_y_px": place_px[1],
        "pick_x_m": round(pick_xy[0], 5), "pick_y_m": round(pick_xy[1], 5),
        "place_x_m": round(place_xy[0], 5), "place_y_m": round(place_xy[1], 5),
        "image_width": w, "image_height": h,
        "timestamp": _dt.datetime.now().isoformat(timespec="seconds"),
    }
    _ensure_header(_steps_path(dataset_dir), STEP_FIELDS)
    with open(_steps_path(dataset_dir), "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=STEP_FIELDS).writerow(row)
    log.info("Saved step %s/%d -> %s", episode_id, step_index, image_rel)
    return row


def finish_episode(dataset_dir, *, episode_id, num_steps, frame, started_at, notes=""):
    """Write images/<episode_id>/final.png and append an episodes.csv row."""
    ep_dir = os.path.join(dataset_dir, "images", episode_id)
    os.makedirs(ep_dir, exist_ok=True)

    h, w = frame.shape[:2]
    cv2.imwrite(os.path.join(ep_dir, "final.png"), frame)
    image_rel = os.path.join("images", episode_id, "final.png").replace("\\", "/")

    finished_at = _dt.datetime.now()
    row = {
        "episode_id": episode_id,
        "num_steps": num_steps,
        "final_image": image_rel,
        "image_width": w, "image_height": h,
        "started_at": started_at.isoformat(timespec="seconds"),
        "finished_at": finished_at.isoformat(timespec="seconds"),
        "duration_s": round((finished_at - started_at).total_seconds(), 1),
        "notes": notes or "",
    }
    _ensure_header(_episodes_path(dataset_dir), EPISODE_FIELDS)
    with open(_episodes_path(dataset_dir), "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=EPISODE_FIELDS).writerow(row)
    log.info("Finished episode %s (%d steps) -> %s", episode_id, num_steps, image_rel)
    return row

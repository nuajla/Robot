# Cloth Pick&Place Data-Collection App

A web GUI for collecting human-directed cloth pick-and-place trajectories
with the Franka arm. It wraps `cloth_pick_place_selector.py`'s click-to-move
workflow (the same affine pixel->robot transform and the same grasp/pull
motion sequence) in a browser UI instead of an OpenCV window, and records
every picked point pair into a dataset as it goes.

## The idea

1. Put the cloth in the frame and click **Capture frame**. This starts a new
   episode if none is active yet.
2. Click the **start point** (where the robot should grab) on the image,
   then the **end point** (where it should place it).
3. Click **Execute**. The robot moves the cloth from start to end; the point
   pair (pixel *and* robot-frame coordinates) is saved together with the
   image it was clicked on.
4. The robot returns home. Click **Capture frame** again to see the cloth's
   new position and repeat as many times as you like.
5. Click **Finish episode**. One more frame is captured as the final image
   and the whole episode -- every step plus the final image -- is written to
   the dataset.

## How it maps to the old code

| `cloth_pick_place_selector.py` | here |
|---|---|
| subscribe to `/rgb/image_raw` | `robot.py` (`RobotController._on_image`) |
| LMB = grasp point, RMB = pull point | click the start point, then the end point on the canvas |
| `AFFINE_MATRIX`, `_pixel_to_robot_xy` | `config.yaml -> robot.affine_matrix`, `robot.py` (`pixel_to_robot_xy`) |
| `s` = `_execute_cloth_action` | click **Execute** -> `robot.py` (`execute_pick_place`), same 8-step sequence and Z heights |
| (nothing -- the original script doesn't log a dataset) | `dataset_io.py` -> `steps.csv` / `episodes.csv` |

## Run it (on the robot-control PC)

This app must run where `cloth_pick_place_selector.py` runs -- the Linux PC
with ROS Noetic, the conda `franka` env, and the robot/camera reachable. From
the repo root `README`, the same environment variables apply:

```bash
conda activate franka
source /opt/ros/noetic/setup.bash
export PYTHONPATH=/opt/ros/noetic/lib/python3/dist-packages:$PYTHONPATH
export PYTHONPATH=/home/ajla/rbs_ws/devel/lib/python3/dist-packages:$PYTHONPATH
export ROS_MASTER_URI=http://10.20.0.5:11311
export ROS_IP=10.20.0.5

cd cloth_pick_place_app
./run_app.sh
```

Open <http://localhost:5001>. Capture, pick two points, execute. Repeat,
then finish.

Everything that can be tuned -- the affine matrix, grasp/pull Z heights,
timings, ROS topic/namespace, dataset location -- is in `config.yaml`,
nothing is hard-coded. **`robot.affine_matrix` and the Z heights are copied
unchanged from `cloth_pick_place_selector.py`; don't edit them without
recalibrating**, and don't crop or resize the captured frame anywhere in the
pipeline -- the affine matrix was calibrated against the raw, full-resolution
`/rgb/image_raw` frame.

### Dry-run on the real PC (camera live, arm not moved)

Set `robot.enabled: false` in `config.yaml` and keep `capture.source:
ros_topic`. The UI behaves identically and the dataset is still recorded,
but `execute_pick_place` only logs the motion it would have run -- no
`panda_ros` / `PandaGripper` calls are made. The header shows **Robot:
SIMULATED** and a banner reminds you the arm won't move.

## Try the UI on Windows (no ROS / robot / camera)

Edit `config.yaml`:

```yaml
capture:
  source: static_file    # read ../rgb.png instead of the ROS topic
robot:
  enabled: false          # never import rospy / robotblockset
```

then `./run_app.ps1`. Capture loads the bundled `rgb.png` every time (a
static test image), and Execute logs a simulated action instead of moving
anything, so you can click through the whole capture -> pick points ->
execute -> repeat -> finish flow and inspect the resulting `datasets/`
folder before ever touching the real rig.

## What gets written

A dated folder under `datasets/` (reused across days so episodes don't
scatter):

```
datasets/cloth_pickplace_YYYY-MM-DD/
  README.md            # auto-generated: protocol, conventions
  config.yaml           # snapshot of the settings used
  steps.csv              # one row per executed action (appended live)
  episodes.csv            # one row per finished episode
  images/ep000/step00.png step01.png ... final.png
  images/ep001/ ...
```

`steps.csv` has both pixel coordinates (in the raw capture frame) and robot
metres for `pick`/`place`. `episodes.csv -> final_image` points at the frame
captured when Finish was clicked. Images are written by OpenCV and are
therefore **BGR** on disk.

## Push to Hugging Face (optional)

```bash
cp .env.example .env        # add your HF_TOKEN
python push_to_hf.py        # -> vhasic/cloth_pickplace_dataset (private)
```

On HPC: `sbatch slurm_push_hf.sh`.

## Files

| file | role |
|---|---|
| `app.py` | Flask server + endpoints (capture / execute / finish) |
| `robot.py` | ROS image subscription + `panda_ros`/`PandaGripper` motion (lazy-imported) |
| `camera.py` | frame capture dispatch (ROS topic / static file) |
| `dataset_io.py` | dated folder, episode numbering, image + CSV writing |
| `templates/`, `static/` | the web UI |
| `config.yaml` | every parameter |
| `push_to_hf.py`, `slurm_push_hf.sh` | dataset upload |

## Notes / decisions

- **No silent fallbacks.** A missing frame, a camera timeout, or a failed
  motion raises a visible error instead of guessing.
- **The server connects to ROS/the robot at startup, not on first click.**
  For a physical arm, a broken connection should fail loudly immediately,
  not on whatever request happens to be first.
- **A fresh capture is required before every `Execute`.** The server clears
  the current frame after each action so a step can never be recorded
  against a stale (pre-move) image.
- **This app is not run via Slurm.** Like the sibling `anomaly_annotation_app`,
  it needs a browser, a live camera feed and a physically attached arm --
  only the offline `push_to_hf.py` upload step is Slurm-batchable.

#!/usr/bin/env bash
# Launch the cloth pick&place app on the robot-control PC (Linux, ROS Noetic +
# conda env "franka", with the environment variables from ../README already
# exported: PYTHONPATH, ROS_MASTER_URI, ROS_IP).
# Then open http://localhost:5001 in a browser.
set -euo pipefail
cd "$(dirname "$0")"

python -m pip install -r requirements.txt

# Same libffi workaround cloth_pick_place_selector.py needs for cv_bridge.
LD_PRELOAD=/usr/lib/x86_64-linux-gnu/libffi.so.7 python app.py

# Launch the app on Windows for UI testing (no ROS / robot / camera).
# Before running, set in config.yaml:
#     capture.source: static_file
#     robot.enabled: false
# Then open http://localhost:5001 in a browser.
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

python -m pip install -r requirements.txt
python app.py

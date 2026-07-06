# RobotBlockset for Python (RBS)

[TOC]



## Synopsis

RobotBlockset (RBS) is a comprehensive robotics framework for Python that unifies robot application design, simulation, testing, and execution on real systems. Its main goal is to bridge the gap between virtual and physical environments, so the same high-level workflow can be used from motion planning in simulation to deployment on a real robot with minimal additional coding.

The toolbox provides spatial representations based on homogeneous transformations and quaternions, together with the necessary conversion and quaternion operations. For robot manipulators, it includes tools for trajectory generation, forward and inverse kinematics, handling intrinsic and user-defined redundancy, and motion control. RBS uses an object-oriented design for robots, grippers, sensors, and other devices, and exposes a unified higher-level interface across different targets.

RBS can connect robot applications to simulators such as MuJoCo, Genesis, and CoppeliaSim, as well as to real robotic platforms. It includes models for common manipulators including Franka Robotics robots, Universal Robots, KUKA LWR and iiwa, and Yaskawa systems, enabling fast design iterations and a smoother transition from simulation to real-world execution.

## Installation

RBS is a normal Python package. You can install it either from a release wheel or directly from this repository.

Recommended Python version: **Python 3.10+**.

### Base installation

From a downloaded release wheel from [repo.ijs.si](https://repo.ijs.si/leon/robotblockset_python/-/releases):

```bash
pip install <downloaded-wheel>.whl
```

From this repository:

```bash
pip install .
```

The base package installs the dependencies used by the core tutorials and utilities:

- `numpy>=1.24`
- `quaternionic>=1.0.12`
- `matplotlib>=3.7.5`
- `scipy`
- `sympy`
- `pyyaml`

This is sufficient for the pure Python parts of RBS and most kinematics and transformation utilities

For  generation of kinematic models also install:

```bash
pip install yourdfpy
```

### Optional packages by backend

Install only the packages needed for the workflows you use.

#### MuJoCo

Official website and documentation:

- https://mujoco.org/

Required when MuJoCo is used as backend as in most of the general tutorials  and parts of the camera calibration tutorials:

```bash
pip install mujoco mediapy
```

For collision-free planning with OMPL:

```bash
pip install ompl
```

RBS uses the official `mujoco` Python package and also supports `simmujoco`, an extended build of MuJoCo `simulate` with a socket interface for external control. Build and usage instructions are in `robotblockset/mujoco/simmujoco/README.md`.

##### MJCF models

RBS provides a set of ready-to-use MJCF robot and scene models. They are included in the package under `robotblockset/mujoco/mjcf_models`, with related meshes and textures under `robotblockset/mujoco/mjcf_models/assets`.

Included models cover several robots and scenes such as Panda, FR3, iiwa14, UR10e, HC20, MiR100, TiagoBase, Unitree B2, grippers, camera models, calibration scenes, and example workcells.

#### Genesis

Official website and project pages:

- https://genesis-embodied-ai.github.io/
- https://github.com/Genesis-Embodied-AI/Genesis

Required by `tutorial_genesis`:

```bash
pip install genesis-world torch
```

RBS imports `genesis` from the `genesis-world` package, and the backend also requires PyTorch.

#### Franka Robotics via `panda_py`

Official project pages:

- https://github.com/JeanElsner/panda-py
- https://franka.de/

Required by `tutorial_franka_pandapy.ipynb` and the modules in `robotblockset.franka`:

```bash
pip install panda-python
```

This backend is intended for direct connection to Franka Panda / FR3 robots. In practice you also need:

- a robot with FCI enabled
- network access to the controller
- a `panda_py` / `libfranka` version compatible with your robot software

#### Universal Robots via RTDE

Official project pages:

- https://pypi.org/project/ur-rtde/
- https://www.universal-robots.com/

Required by `tutorial_ur_rtde.ipynb` and the modules in `robotblockset.ur`:

```bash
pip install ur_rtde
```

#### CoppeliaSim

Official website and documentation:

- https://www.coppeliarobotics.com/
- https://manual.coppeliarobotics.com/

Required by the modules in `robotblockset.coppelia`:

```bash
pip install coppeliasim-zmqremoteapi-client
```

You also need a local CoppeliaSim installation with the `zmqRemoteApi` server enabled.

#### Cameras and calibration

The camera modules are split by hardware. The image-processing utilities and calibration notebooks rely mainly on OpenCV, Pydantic, and often MuJoCo.

Common camera/calibration packages:

```bash
pip install opencv-contrib-python pydantic open3d
```

Additional packages by camera type:

- Intel RealSense: `pip install pyrealsense2`
  Official docs: https://dev.intelrealsense.com/docs/docs-get-started
- Basler: `pip install pypylon`
  Official docs: https://docs.baslerweb.com/pythonProgGuide.html
- ZED: install the ZED SDK first, then its Python bindings
  Official docs: https://www.stereolabs.com/docs/

The camera calibration tutorials also import:

```bash
pip install mujoco mediapy
```

#### ROS / ROS2

Official documentation:

- ROS1: https://wiki.ros.org/
- ROS2: https://docs.ros.org/en/jazzy/index.html

If you use the ROS or ROS2 backends, install the middleware through your ROS distribution rather than plain `pip`.

ROS1:

```bash
sudo apt install python3-rospy
```

ROS2:

```bash
sudo apt update
sudo apt install ros-<ros-distro>-rclpy
```

For ROS2 camera support you typically also need:

```bash
sudo apt install ros-<ros-distro>-cv-bridge
```

> ⚠️Important: if you use `cv_bridge`, prefer a NumPy 1.x environment for now, for example:

```bash
pip install "numpy<2"
```

The reason is that `cv_bridge` builds distributed through ROS packages are often compiled against NumPy 1.x and may fail to import with NumPy 2.x, typically with errors such as `_ARRAY_API not found`.

For Franka ROS2 support, RBS expects packages such as `franka_ros2` and `franka_msgs` to be available in the ROS workspace.

If you work with custom message packages or a preconfigured environment, using the institute Docker/workspace setup may be easier:

- https://repo.ijs.si/hcr/rbs-docker

### Optional devices and utilities

#### SpaceMouse

To use a 3Dconnexion SpaceMouse with RBS:

```bash
pip install pyspacemouse easyhid
```

On Windows, you may also need `hidapi.dll` available on `PATH`.

On Linux, if the device is detected but cannot be opened, create an appropriate `udev` rule, reload the rules, and ensure your user belongs to the `input` group.

#### Other useful packages

Depending on your workflow, these can also be useful:

```bash
pip install pynput
pip install pyformulas
pip install aiohttp aiofiles
```

## Documentation

RBS provides several tutorial notebooks in `robotblockset/tutorials`, which can help you to get started and explore specific backends and workflows:

- `tutorial_spatial_operations`
- `tutorial_motion_generation`
- `tutorial_robots`
- `tutorial_platforms`
- `tutorial_mobile_robots`
- `tutorial_multi_robots`
- `tutorial_kinematic_models`
- `tutorial_optimal_trajectory`
- `tutorial_generation_collision-free_trajectories`
- `tutorial_image_video_pymujoco`
- `tutorial_mujoco`
- `tutorial_generate_MJCF_scene`
- `tutorial_genesis`
- `tutorial_graphics`
- `tutorial_franka_pandapy`
- `tutorial_rbf`
- `tutorial_ur_rtde`
- `tutorial_calibrate_camera_charuco`
- `tutorial_calibrate_camera_checker`
- `tutorial_image_transform`

RBS also provides example notebooks and scripts in `robotblockset/examples`, which can be additional help when adapting the toolbox to your own robots, scenes, and applications.

## API documentation

The repository includes a Sphinx configuration under `docs` for generating API documentation directly from module, class, method, and function docstrings.

Install the package together with the documentation dependency:

```bash
pip install -e ".[docs]"
```

Then build the HTML documentation:

```bash
sphinx-build -b html docs docs/_build/html
```

Open `docs/_build/html/index.html` in a browser after the build completes.

The Sphinx setup mocks optional backend dependencies such as ROS, MuJoCo, camera SDKs, and vendor-specific drivers so the API reference can be built without installing every robotics stack.

## Troubleshooting

If you get on Windows following error:

```
tkinter.TclError: Can't find a usable init.tcl in the following directories: C:/Python313/lib/tcl8.6 C:/lib/tcl8.6 C:/lib/tcl8.6 C:/library C:/library C:/tcl8.6.14/library C:/tcl8.6.14/library 

This probably means that Tcl wasn't installed properly.  
```

the solution is to  set the environment variable manually:

1. Open **Control Panel** → **System** → **Advanced system settings**.
2. Go to **Environment Variables**.
3. Under **System Variables**, click **New**.
4. Set:
   - **Variable name:** `TCL_LIBRARY`
   - **Variable value:** `C:\Python313\tcl\tcl8.6` (adjust if your folder is different)

## Citation

Please cite the following article in your publications if it helps your research :

```latex
@InProceedings{10.1007/978-3-031-59257-7_44,
author="{\v{Z}}lajpah, Leon and Petri{\v{c}}, Tadej",
editor="Pisla, Doina and Carbone, Giuseppe and Condurache, Daniel and Vaida, Calin",
title="RobotBlockSet (RBS)---A Comprehensive Robotics Framework",
booktitle="Advances in Service and Industrial Robotics",
year="2024",
publisher="Springer Nature Switzerland",
address="Cham",
pages="439--450",
isbn="978-3-031-59257-7"
}
```

​                      

------



Copyright: Leon Žlajpah, Jožef Stefan Insitute


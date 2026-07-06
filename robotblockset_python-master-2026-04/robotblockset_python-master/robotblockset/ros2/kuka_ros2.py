"""ROS 2 KUKA iiwa robot interfaces.

This module defines ROS 2-backed interfaces for KUKA iiwa robots. It provides
support for Cartesian impedance control, joint-trajectory control, and wrench
feedback integration through ROS 2 controllers and topics.

Copyright (c) 2024- Jozef Stefan Institute

Authors: Mihael Simonic.
"""

from __future__ import annotations

import numpy as np

from geometry_msgs.msg import WrenchStamped
from rclpy.qos import qos_profile_sensor_data

from robotblockset.robot_spec import iiwa_spec
from robotblockset.ros2.controllers_ros2 import (
    CsfCartesianImpedanceControllerInterface,
    JointTrajectoryControllerInterface,
    controller_manager_helper,
)
from robotblockset.ros2.robots_ros2 import robot_ros2


class iiwa7(robot_ros2, iiwa_spec):
    def __init__(
        self,
        name: str = "iiwa7",
        ns: str = "lbr",
        control_strategy: str = "CartesianImpedance",
        cartesian_controller_name: str = "cartesian_impedance_controller",
        joint_trajectory_controller_name: str = "iiwa_arm_controller",
    ) -> None:
        """Initialize the ROS 2 iiwa7 robot wrapper."""
        # Initialize specification (kinematics, joint names, limits, ...)
        iiwa_spec.__init__(self)

        # Build the controller interfaces
        cartesian_impedance_controller = CsfCartesianImpedanceControllerInterface(
            ros_plugin_name=cartesian_controller_name,
            topic="cartesian_command",
            namespace=ns,
            Kp=np.array([200.0, 200.0, 200.0]),
            Kr=np.array([10.0, 10.0, 10.0]),
            R=np.eye(3),
            D=2.0,
        )

        joint_position_trajectory_controller = JointTrajectoryControllerInterface(
            ros_plugin_name=joint_trajectory_controller_name,
            topic="joint_trajectory",
            action="follow_joint_trajectory",
            namespace=ns,
        )

        strategy_mapping = {
            "CartesianImpedance": cartesian_impedance_controller,
            "JointPositionTrajectory": joint_position_trajectory_controller,
            "JointPosition": joint_position_trajectory_controller,
        }

        # Initialize robot base class WITHOUT a strategy mapping so that robot_ros2
        # does NOT create a controller_manager_helper pointing at the global
        # (un-namespaced) "controller_manager" service – which would block forever
        # when the robot runs under a namespace like /lbr.
        robot_ros2.__init__(
            self,
            name=name,
            namespace=ns,
            strategy_to_controller_interface_mapping=None,
            joint_states_topic="joint_states",
            control_strategy=None,  # applied manually below, after the helper is ready
        )

        # Now create the controller_manager_helper pointed at the correct
        # namespaced service, e.g. /lbr/controller_manager.
        _ns = str(ns).strip("/")
        cm_name = f"{_ns}/controller_manager" if _ns else "controller_manager"
        self._control_helper = controller_manager_helper(cm_name)

        # Wire up the strategy mapping and the desired strategy
        self._strategy_to_controller_interface_mapping = strategy_mapping
        self._control_strategy = control_strategy

        # Optional wrench state subscription
        self.force_state_subscription = self.create_subscription(
            msg_type=WrenchStamped,
            topic=f"{self._namespace}/force_torque_sensor_broadcaster/wrench",
            callback=self._force_state_callback,
            qos_profile=qos_profile_sensor_data,
        )

        # Start spinning only after all publishers/subscribers/clients are created.
        # _start_spinning will call SetStrategy(control_strategy) using the correct helper.
        self._start_spinning(wait_for_state=True)

        # Finalize robot state
        self.Init()

        self.Message("Initialized", 2)

    def Check(self, silent: bool = False) -> list:
        """Return the current list of detected robot issues."""
        return []

    def shutdown(self) -> None:
        """Shut down the ROS 2 robot wrapper and its background spinner."""
        self.Shutdown()

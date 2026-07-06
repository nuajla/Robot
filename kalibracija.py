import rospy
from robotblockset.ros.franka_ros import panda_ros
import time
from robotblockset.ros.grippers_ros import PandaGripper

ns = "pingvin_1"
rospy.init_node("pose_reader", anonymous=True)
time.sleep(1.0)
r = panda_ros(ns=ns, control_strategy="JointImpedance", init_node=False)
g = PandaGripper(namespace=ns,robot=r)
g.Close()

print(f"X: {r.x[0]:.4f}")
print(f"Y: {r.x[1]:.4f}")

rospy.signal_shutdown("done")
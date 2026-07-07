import rospy
from robotblockset.ros.franka_ros import panda_ros
import time
from robotblockset.ros.grippers_ros import PandaGripper


ns = "pingvin_1"
rospy.init_node("cloth_executor", anonymous=True)
time.sleep(1.0)
r = panda_ros(ns=ns, control_strategy="JointImpedance", init_node=False)
g = PandaGripper(namespace=ns,robot=r)


r.ErrorRecovery()
#r.Start()
# Vrni v home
r.JMove(r.q_home, t=3)
g.Open()
time.sleep(1.0)
#g.Close()

gx, gy = 0.6292584417578411, -0.01933367309415109
px, py = 0.6328349754067282, -0.040634899881255716
Z_ABOVE = 0.15
Z_GRASP = 0.10
Z_PULL  = 0.15

# Nad grasp točko
r.CMove([gx, gy, Z_ABOVE], t=3) 
g.Move(.02)
r.CMove([gx, gy, Z_GRASP], t=3) 
g.Close()
r.CMove([px, py, Z_GRASP], t=3) 
g.Move(.02)


r.JMove(r.q_home, t=3)
time.sleep(1.0) 
g.Homing()
g.Open()
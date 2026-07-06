#!/usr/bin/env python3
"""
execute_action.py — teče na hostu (conda env franka, Python 3.10)

Posluša na /cloth_action, izvede akcijo, potem objavi /robot_ready
da fabric_ros ve da lahko zajame novo sliko.

Zaženi:
    conda activate franka
    export PYTHONPATH=/opt/ros/noetic/lib/python3/dist-packages:/home/ajla/rbs_ws/devel/lib/python3/dist-packages:$PYTHONPATH
    export ROS_MASTER_URI=http://10.20.0.5:11311
    export ROS_IP=10.20.0.5
    python execute_action.py
"""

import rospy
from std_msgs.msg import Float32MultiArray, Bool
from robotblockset.ros.franka_ros import panda_ros
from robotblockset.ros.grippers_ros import PandaGripper
import time
import queue
import threading

# ── Parametri ─────────────────────────────────────────────────────────────────

NS             = "pingvin_1"
TOPIC_ACTION   = "/cloth_action"   # sprejema akcije iz fabric_ros
TOPIC_READY    = "/robot_ready"    # objavlja signal ko je robot v home

MAX_ACTIONS = 10

Z_ABOVE = 0.20
#Z_GRASP = 0.070
Z_GRASP = 0.11
Z_PULL  = 0.13

MOVE_TIME  = 3.0
GRASP_TIME = 1.0

# ── Globalne spremenljivke ─────────────────────────────────────────────────────

r = None
g = None
ready_pub = None
action_queue = queue.Queue()
action_count = 0

# ── Akcija ─────────────────────────────────────────────────────────────────────

def execute_cloth_action(gx, gy, px, py):
    rospy.loginfo(f"[ACTION] grasp=({gx:.4f}, {gy:.4f})  pull=({px:.4f}, {py:.4f})")

    # 1. Odpri gripper
    rospy.loginfo("[1] Odpiranje gripperja...")
    g.Move(0.02)
    time.sleep(0.5)

    # 2. Nad grasp točko
    rospy.loginfo(f"[2] Premik nad grasp  Z={Z_ABOVE} m ...")
    r.CMove([gx, gy, Z_ABOVE], t=MOVE_TIME)

    # 3. Spust
    rospy.loginfo(f"[3] Spust na Z={Z_GRASP} m ...")
    r.CMove([gx, gy, Z_GRASP], t=GRASP_TIME)

    # 4. Zapri gripper
    rospy.loginfo("[4] Zapiranje gripperja...")
    g.Close()
    time.sleep(0.5)

    # 5. Dvig
    rospy.loginfo(f"[5] Dvig na Z={Z_PULL} m ...")
    r.CMove([gx, gy, Z_PULL], t=GRASP_TIME)

    # 6. Pull točka
    rospy.loginfo(f"[6] Premik nad pull  Z={Z_PULL} m ...")
    r.CMove([px, py, Z_PULL], t=MOVE_TIME)

    # 7. Odpri gripper
    rospy.loginfo("[7] Spust tkanine...")
    g.Move(0.02)
    time.sleep(0.5)

    # 8. Vrni v home
    rospy.loginfo("[8] Premik v home pozo...")
    r.JMove(r.q_home, t=4)

    rospy.loginfo("[DONE] Akcija zaključena.\n")

# ── Worker thread ──────────────────────────────────────────────────────────────

def action_worker():
    while not rospy.is_shutdown():
        try:
            gx, gy, px, py = action_queue.get(timeout=1.0)
            try:
                execute_cloth_action(gx, gy, px, py)
            except Exception as e:
                rospy.logerr(f"[ERROR] Napaka med akcijo: {e}")
            finally:
                # Objavi /robot_ready ko je robot v home
                rospy.loginfo("[READY] Objavljam /robot_ready ...")
                ready_pub.publish(Bool(data=True))
                action_queue.task_done()
        except queue.Empty:
            continue

# ── ROS callback ───────────────────────────────────────────────────────────────

def action_callback(msg):
    global action_count
    if action_count >= MAX_ACTIONS:
        rospy.loginfo(f"[DONE] Doseženo {MAX_ACTIONS} akcij, zaključujem.")
        rospy.signal_shutdown("max actions reached")
        return
    if len(msg.data) != 4:
        rospy.logerr(f"[SUB] Napačna dolžina: {len(msg.data)}, pričakovano 4")
        return

    action_count += 1
    rospy.loginfo(f"[QUEUE] Akcija {action_count}/{MAX_ACTIONS} v vrsti.")
    action_queue.put(tuple(msg.data))

# ── Glavni program ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    rospy.init_node("cloth_executor", anonymous=True)
    time.sleep(1.0)

    rospy.loginfo("Inicializacija robota...")
    r = panda_ros(ns=NS, control_strategy="JointImpedance", init_node=False)
    g = PandaGripper(robot=r, namespace=NS)
    ready_pub = rospy.Publisher(TOPIC_READY, Bool, queue_size=1)

    r.ErrorRecovery()
    r.Start()

    rospy.loginfo("Premik v home pozo...")
    r.JMove(r.q_home, t=4)

    # Objavi /robot_ready ob zagonu da fabric_ros ve da lahko začne
    time.sleep(1.0)
    rospy.loginfo("[READY] Robot v home pozi, objavljam /robot_ready ...")
    ready_pub.publish(Bool(data=True))

    # Zaženi worker thread
    worker = threading.Thread(target=action_worker, daemon=True)
    worker.start()

    # Subscribiraj na akcije
    rospy.Subscriber(TOPIC_ACTION, Float32MultiArray, action_callback)
    rospy.loginfo(f"[READY] Poslušam na {TOPIC_ACTION} ...")

    rospy.spin()
#!/bin/bash
# ROS1->ROS2 scan bridge launcher
# Pipes ROS1 writer (stdout) into ROS2 reader (stdin)

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
BRIDGE_SCRIPT="$SCRIPT_DIR/ros1_scan_bridge.py"

# ROS1 writer: subscribes /tianracer/scan, writes binary to stdout
ROS1_CMD='source /opt/ros/noetic/setup.bash && export ROS_DISTRO=noetic && python3 '"$BRIDGE_SCRIPT"

# ROS2 reader: reads binary from stdin, publishes /scan
ROS2_CMD='source /opt/tros/humble/setup.bash && source ~/tianracer_ros2_ws/install/setup.bash && export ROS_DISTRO=humble && python3 '"$BRIDGE_SCRIPT"

# Pipe: ros1 writer stdout -> ros2 reader stdin
bash -c "$ROS1_CMD" | bash -c "$ROS2_CMD"

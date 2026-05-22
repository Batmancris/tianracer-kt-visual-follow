#!/usr/bin/env python3
"""
ROS1 WebRTC Bridge 入口脚本
"""
from webrtc_ros_bridge.ros1.ros1_publisher import ROS1PublisherNode
import sys
import os

# 添加模块路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))


if __name__ == '__main__':
    try:
        node = ROS1PublisherNode()
        node.run()
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

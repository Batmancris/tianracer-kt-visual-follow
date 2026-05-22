#!/usr/bin/env python3
"""
ROS1->ROS2 LaserScan bridge.

Architecture:
  - Writer process (ROS1 env): subscribes /tianracer/scan, writes binary to stdout
  - Reader process (ROS2 env): reads binary from stdin, publishes /scan

Launch via the companion shell wrapper that pipes them together.
This script auto-detects which role to play based on ROS_DISTRO env.
"""

import sys
import os
import struct
import time

DISTRO = os.environ.get('ROS_DISTRO', '')

if DISTRO == 'noetic':
    # ---- ROS1 writer ----
    import rospy
    from sensor_msgs.msg import LaserScan

    def callback(msg):
        # Pack: header stamp secs/nsecs, frame_id, then all float fields + arrays
        frame = msg.header.frame_id.encode('utf-8')
        data = struct.pack('<ii', msg.header.stamp.secs, msg.header.stamp.nsecs)
        data += struct.pack('<I', len(frame)) + frame
        data += struct.pack('<7f', msg.angle_min, msg.angle_max, msg.angle_increment,
                            msg.time_increment, msg.scan_time, msg.range_min, msg.range_max)
        ranges = list(msg.ranges)
        intensities = list(msg.intensities)
        data += struct.pack('<I', len(ranges))
        data += struct.pack(f'<{len(ranges)}f', *ranges)
        data += struct.pack('<I', len(intensities))
        data += struct.pack(f'<{len(intensities)}f', *intensities)
        # Write length-prefixed frame
        sys.stdout.buffer.write(struct.pack('<I', len(data)))
        sys.stdout.buffer.write(data)
        sys.stdout.buffer.flush()

    rospy.init_node('scan_bridge_writer', anonymous=True, disable_signals=True)
    rospy.Subscriber('/tianracer/scan', LaserScan, callback, queue_size=1)
    rospy.loginfo('ros1_scan_bridge: writer subscribed to /tianracer/scan')
    rospy.spin()

elif DISTRO == 'humble':
    # ---- ROS2 reader ----
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
    from sensor_msgs.msg import LaserScan
    import threading

    class ScanBridgeReader(Node):
        def __init__(self):
            super().__init__('ros1_scan_bridge')
            self.pub = self.create_publisher(
                LaserScan, '/scan',
                QoSProfile(
                    reliability=ReliabilityPolicy.BEST_EFFORT,
                    durability=DurabilityPolicy.VOLATILE,
                    depth=1))
            self.count = 0
            self.get_logger().info('ros1_scan_bridge: publishing /scan (ROS2)')

        def read_loop(self):
            buf = sys.stdin.buffer
            while True:
                hdr = buf.read(4)
                if len(hdr) < 4:
                    break
                msg_len = struct.unpack('<I', hdr)[0]
                data = buf.read(msg_len)
                if len(data) < msg_len:
                    break
                off = 0
                secs, nsecs = struct.unpack_from('<ii', data, off); off += 8
                slen = struct.unpack_from('<I', data, off)[0]; off += 4
                frame_id = data[off:off+slen].decode('utf-8'); off += slen
                angle_min, angle_max, angle_inc, time_inc, scan_time, range_min, range_max = \
                    struct.unpack_from('<7f', data, off); off += 28
                n_ranges = struct.unpack_from('<I', data, off)[0]; off += 4
                ranges = list(struct.unpack_from(f'<{n_ranges}f', data, off)); off += 4 * n_ranges
                n_int = struct.unpack_from('<I', data, off)[0]; off += 4
                intensities = list(struct.unpack_from(f'<{n_int}f', data, off)); off += 4 * n_int

                msg = LaserScan()
                msg.header.stamp.sec = secs
                msg.header.stamp.nanosec = nsecs
                msg.header.frame_id = frame_id
                msg.angle_min = angle_min
                msg.angle_max = angle_max
                msg.angle_increment = angle_inc
                msg.time_increment = time_inc
                msg.scan_time = scan_time
                msg.range_min = range_min
                msg.range_max = range_max
                msg.ranges = ranges
                msg.intensities = intensities
                self.pub.publish(msg)
                self.count += 1
                if self.count % 50 == 1:
                    self.get_logger().info(f'Forwarded {self.count} scans to /scan')

    rclpy.init()
    node = ScanBridgeReader()
    t = threading.Thread(target=node.read_loop, daemon=True)
    t.start()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        rclpy.shutdown()

else:
    print(f"ERROR: Unknown ROS_DISTRO '{DISTRO}'", file=sys.stderr)
    sys.exit(1)

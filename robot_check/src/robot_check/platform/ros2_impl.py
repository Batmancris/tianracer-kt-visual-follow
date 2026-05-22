
import os
import time
import threading
import numpy as np

try:
    import rclpy
    from rclpy.node import Node
    from rclpy.duration import Duration
    from rclpy.qos import QoSProfile
    from rclpy.time import Time
    from builtin_interfaces.msg import Time as TimeMsg
    from geometry_msgs.msg import Twist, PointStamped
    from nav_msgs.msg import Odometry
    from sensor_msgs.msg import LaserScan, Imu, Image, CompressedImage
    from ament_index_python.packages import get_package_share_directory
    from tf2_ros import Buffer, TransformListener, TransformException
    from rosidl_runtime_py.utilities import get_message
except ImportError:
    pass # Handle environment where ROS2 is not sourced

from .base import BasePlatform

def euler_from_quaternion(x, y, z, w):
    """
    Converts quaternion (w in last place) to euler roll, pitch, yaw
    quaternion = [x, y, z, w]
    Bellow should be replaced when porting for ROS 2 Python which doesn't include transformations.py
    """
    import math
    t0 = +2.0 * (w * x + y * z)
    t1 = +1.0 - 2.0 * (x * x + y * y)
    roll_x = math.atan2(t0, t1)
    
    t2 = +2.0 * (w * y - z * x)
    t2 = +1.0 if t2 > +1.0 else t2
    t2 = -1.0 if t2 < -1.0 else t2
    pitch_y = math.asin(t2)
    
    t3 = +2.0 * (w * z + x * y)
    t4 = +1.0 - 2.0 * (y * y + z * z)
    yaw_z = math.atan2(t3, t4)
    
    return roll_x, pitch_y, yaw_z

class ROS2Platform(BasePlatform):
    def __init__(self):
        super(ROS2Platform, self).__init__()
        self.node = None
        self.executor = None
        self.tf_buffer = None
        self.tf_listener = None
        self._thread = None
        self._lock = threading.Lock()
        
        self.latest_odom = None
        self.latest_scan = None
        self.latest_imu = None

    def init_node(self, name):
        if not rclpy.ok():
            rclpy.init()
        self.node = rclpy.create_node(name)
        
        # Init TF
        self.tf_buffer = Buffer()
        self.tf_listener = TransformListener(self.tf_buffer, self.node)

        # Start a spinning thread
        self._thread = threading.Thread(target=self._spin_thread)
        self._thread.daemon = True
        self._thread.start()
        
        # Init Pub/Sub
        self.cmd_pub = self.node.create_publisher(Twist, '/tianracer/cmd_vel', 10) # Standard Twist in ROS2
        
        qos = QoSProfile(depth=10)
        self.odom_sub = self.node.create_subscription(Odometry, '/tianracer/odom', self._odom_cb, qos)
        self.scan_sub = self.node.create_subscription(LaserScan, '/tianracer/scan', self._scan_cb, qos)
        self.imu_sub = self.node.create_subscription(Imu, '/tianracer/imu', self._imu_cb, qos)

    def _spin_thread(self):
        rclpy.spin(self.node)

    def _odom_cb(self, msg):
        with self._lock:
            self.latest_odom = msg

    def _scan_cb(self, msg):
        with self._lock:
            self.latest_scan = msg

    def _imu_cb(self, msg):
        with self._lock:
            self.latest_imu = msg

    def get_time(self):
        if self.node:
            return self.node.get_clock().now().nanoseconds / 1e9
        return time.time()

    def sleep(self, seconds):
        time.sleep(seconds) # rclpy sleep is async, simple blocking sleep is fine for check scripts

    def shutdown(self):
        if self.node:
            self.node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    def get_param(self, name, default=None):
        # Align ROS2 parameter naming with ROS1-style "~" by stripping it
        param_name = name[1:] if name.startswith('~') else name
        if not self.node.has_parameter(param_name):
            self.node.declare_parameter(param_name, default)
        return self.node.get_parameter(param_name).value

    def get_package_path(self, package_name):
        try:
            return get_package_share_directory(package_name)
        except Exception:
            return None

    def measure_topic_frequency(self, topic_name, topic_type_str, duration=5.0):
        if self.node is None:
            return {'error': 'Node not initialized'}

        # Lazy dependency guard for environments without ROS 2 setup
        if 'get_message' not in globals():
            return {'error': 'ROS2 message utilities not available'}

        def _normalize_ros2_type(type_str):
            # Accept both ROS1-style "pkg/Msg" and ROS2-style "pkg/msg/Msg"
            if '/msg/' in type_str:
                return type_str
            if type_str.count('/') == 1:
                pkg, msg = type_str.split('/')
                return f"{pkg}/msg/{msg}"
            return type_str

        try:
            msg_cls = get_message(_normalize_ros2_type(topic_type_str))
        except Exception as e:
            return {'error': f"Failed to load message type: {e}"}

        stats_lock = threading.Lock()
        recv_times = []
        last_msg = {'msg': None}

        def _cb(msg):
            now_sec = self.node.get_clock().now().nanoseconds / 1e9
            with stats_lock:
                recv_times.append(now_sec)
                last_msg['msg'] = msg

        sub = self.node.create_subscription(msg_cls, topic_name, _cb, 10)

        # Collect for duration seconds; spin thread is already running
        end_t = time.time() + duration
        while time.time() < end_t:
            time.sleep(0.05)

        self.node.destroy_subscription(sub)

        with stats_lock:
            n = len(recv_times)
            if n < 2:
                return {'count': n, 'hz': 0.0, 'std_dev': 0.0, 'frame_id': '', 'error': 'Not enough messages'}

            diffs = np.diff(recv_times)
            mean_hz = 1.0 / np.mean(diffs) if np.mean(diffs) > 0 else 0.0
            std_dev = float(np.std(diffs))

            msg = last_msg['msg']
            frame_id = ''
            if hasattr(msg, 'header'):
                frame_id = msg.header.frame_id

            data_valid, sample_value = self._analyze_msg(msg)

            return {
                'count': n,
                'hz': round(mean_hz, 2),
                'std_dev': round(std_dev, 4),
                'frame_id': frame_id,
                'data_valid': data_valid,
                'sample_value': sample_value,
                'error': None
            }

    def check_tf(self, parent_frame, child_frame, timeout=1.0):
        try:
           # Check if transform is available
           # ROS 2 can_transform(target, source, time, timeout)
           # We want to know if 'child' exists in 'parent' frame => child w.r.t parent
           return self.tf_buffer.can_transform(parent_frame, child_frame, rclpy.time.Time(), timeout=Duration(seconds=timeout))
        except Exception:
           return False
        
    def get_odom_pose(self):
        with self._lock:
            if not self.latest_odom:
                return None
            msg = self.latest_odom
        
        # Extract yaw
        q = msg.pose.pose.orientation
        _, _, yaw = euler_from_quaternion(q.x, q.y, q.z, q.w)
        return (msg.pose.pose.position.x, msg.pose.pose.position.y, yaw)

    def get_lidar_range(self, angle_deg, target_frame="tianracer/base_link"):
        with self._lock:
            if not self.latest_scan:
                return None
            data = self.latest_scan

        # Step 1: determine target angle in laser frame via TF
        try:
            trans = self.tf_buffer.lookup_transform(
                data.header.frame_id,
                target_frame,
                rclpy.time.Time(),
                timeout=Duration(seconds=0.1)
            )

            q = trans.transform.rotation
            _, _, yaw_base_in_laser = euler_from_quaternion(q.x, q.y, q.z, q.w)
            desired_angle_base = np.deg2rad(angle_deg)
            target_angle_laser = desired_angle_base + yaw_base_in_laser
        except Exception:
            target_angle_laser = np.deg2rad(angle_deg)
            trans = None

        # Step 2: windowed range extraction around target angle
        diff_angle = (target_angle_laser - data.angle_min) % (2 * np.pi)
        center_idx = int(round(diff_angle / data.angle_increment))
        if center_idx >= len(data.ranges):
            center_idx = 0

        window_size = 5
        half_window = window_size // 2
        valid_ranges = []
        for i in range(-half_window, half_window + 1):
            idx = (center_idx + i) % len(data.ranges)
            r = data.ranges[idx]
            if data.range_min <= r <= data.range_max:
                valid_ranges.append(r)

        if not valid_ranges:
            range_val = data.ranges[center_idx] if 0 <= center_idx < len(data.ranges) else float('inf')
        else:
            range_val = float(np.median(valid_ranges))

        if range_val < data.range_min or range_val > data.range_max:
            return float('inf')

        # Step 3: transform point to base frame if TF available
        if trans is None:
            return range_val

        p_laser = PointStamped()
        p_laser.header = data.header
        p_laser.point.x = range_val * np.cos(target_angle_laser)
        p_laser.point.y = range_val * np.sin(target_angle_laser)
        p_laser.point.z = 0.0

        try:
            p_base = self.tf_buffer.transform(p_laser, target_frame, timeout=Duration(seconds=0.1))
            return float(np.hypot(p_base.point.x, p_base.point.y))
        except Exception:
            return range_val
    
    def get_odom_twist(self):
        with self._lock:
            if not self.latest_odom:
                return None
            msg = self.latest_odom
        return (msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def get_imu_yaw(self):
        with self._lock:
            if not self.latest_imu:
                return None
            msg = self.latest_imu
        q = msg.orientation
        _, _, yaw = euler_from_quaternion(q.x, q.y, q.z, q.w)
        return yaw

    def _analyze_msg(self, msg):
        """Lightweight data sanity checks for passive topics."""
        if msg is None:
            return False, None

        sample_value = getattr(msg, 'data', None)

        try:
            if isinstance(msg, LaserScan):
                ranges = np.array(msg.ranges, dtype=float)
                finite = ranges[np.isfinite(ranges)]
                return (finite.size > 0, None)

            if isinstance(msg, Imu):
                o = msg.orientation
                quat = np.array([o.x, o.y, o.z, o.w], dtype=float)
                finite = np.isfinite(quat)
                return (bool(finite.all() and np.any(np.abs(quat) > 1e-6)), None)

            if isinstance(msg, Odometry):
                p = msg.pose.pose.position
                vals = np.array([p.x, p.y], dtype=float)
                finite = np.isfinite(vals)
                return (bool(finite.all()), None)

            if isinstance(msg, Image):
                valid = (msg.height > 0 and msg.width > 0 and msg.step > 0)
                return (valid, None)

            if isinstance(msg, CompressedImage):
                valid = bool(msg.format and len(msg.data) > 0)
                return (valid, None)

            # Generic numeric message with .data
            if sample_value is not None:
                if isinstance(sample_value, (bytes, bytearray)):
                    return (True, None)
                try:
                    val = float(sample_value)
                    return (np.isfinite(val), val)
                except Exception:
                    return (True, None)

        except Exception:
            return (True, sample_value)

        return (True, sample_value)

    def pub_cmd_vel(self, v, w):
        msg = Twist()
        msg.linear.x = float(v)
        msg.angular.z = float(w)
        self.cmd_pub.publish(msg)


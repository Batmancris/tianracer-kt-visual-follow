import threading
import time
import numpy as np

# ROS1 imports
import rospy
import rostopic
import rospkg
import tf2_ros
import tf2_geometry_msgs # Import this to enable transform of geometry_msgs
from ackermann_msgs.msg import AckermannDrive
from nav_msgs.msg import Odometry
from sensor_msgs.msg import LaserScan, Imu, Image, CompressedImage
from geometry_msgs.msg import PointStamped # Need this for point transformation
from tf.transformations import euler_from_quaternion

from .base import BasePlatform

class ROS1Platform(BasePlatform):
    def __init__(self):
        super(ROS1Platform, self).__init__()
        self.tf_buffer = None
        self.tf_listener = None
        self.cmd_pub = None
        self.odom_sub = None
        self.scan_sub = None

        # Cache for latest sensor data
        self.latest_odom = None
        self.latest_scan = None
        self.latest_imu = None
        self._lock = threading.Lock()

    def init_node(self, name):
        rospy.init_node(name, anonymous=True)
        # Init TF
        self.tf_buffer = tf2_ros.Buffer()
        self.tf_listener = tf2_ros.TransformListener(self.tf_buffer)

        # Init Pub/Sub
        self.cmd_pub = rospy.Publisher('/tianracer/ackermann_cmd', AckermannDrive, queue_size=1)
        self.odom_sub = rospy.Subscriber('/tianracer/odom', Odometry, self._odom_cb)
        self.scan_sub = rospy.Subscriber('/tianracer/scan', LaserScan, self._scan_cb)
        self.imu_sub = rospy.Subscriber('/tianracer/imu', Imu, self._imu_cb)

    def _odom_cb(self, msg):
        with self._lock:
            self.latest_odom = msg

    def _scan_cb(self, msg):
        with self._lock:
            self.latest_scan = msg
            if not hasattr(self, '_scan_received_once'):
                rospy.loginfo(f"DEBUG: First scan received on topic {msg.header.frame_id}, ranges: {len(msg.ranges)}")
                self._scan_received_once = True

    def _imu_cb(self, msg):
        with self._lock:
            self.latest_imu = msg

    def get_time(self):
        return rospy.Time.now().to_sec()

    def sleep(self, seconds):
        rospy.sleep(seconds)

    def shutdown(self):
        rospy.signal_shutdown("Check finished")

    def get_param(self, name, default=None):
        return rospy.get_param(name, default)

    def get_package_path(self, package_name):
        try:
            rospack = rospkg.RosPack()
            return rospack.get_path(package_name)
        except Exception:
            return None

    def measure_topic_frequency(self, topic_name, topic_type_str, duration=5.0):
        """
        使用 ROSTopicHz 类似的逻辑，但非阻塞式监听
        """
        class HzStats:
            def __init__(self):
                self.times = []
                self.last_msg = None
                self.lock = threading.Lock()

            def callback(self, msg):
                with self.lock:
                    self.times.append(rospy.get_time())
                    self.last_msg = msg

        stats = HzStats()

        # 动态导入消息类型
        # 简单起见，这里假设常见类型，或者使用 AnyMsg (rospy.AnyMsg 不直接支持)
        # 为了通用性，使用 rostopic.get_topic_class
        try:
            msg_class, _, _ = rostopic.get_topic_class(topic_name)
            if msg_class is None:
                return {'error': f"Topic {topic_name} not found or type unknown"}
        except Exception as e:
            return {'error': f"Failed to get topic type: {e}"}

        sub = rospy.Subscriber(topic_name, msg_class, stats.callback)

        rospy.sleep(duration)
        sub.unregister()

        with stats.lock:
            n = len(stats.times)
            if n < 2:
                return {'count': n, 'hz': 0.0, 'std_dev': 0.0, 'frame_id': '', 'data_valid': False, 'sample_value': None, 'error': "Not enough messages"}

            diffs = np.diff(stats.times)
            mean_hz = 1.0 / np.mean(diffs) if np.mean(diffs) > 0 else 0.0
            std_dev = np.std(diffs)

            frame_id = ""
            if hasattr(stats.last_msg, 'header'):
                frame_id = stats.last_msg.header.frame_id

            data_valid, sample_value = self._analyze_msg(stats.last_msg)

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
            self.tf_buffer.lookup_transform(parent_frame, child_frame, rospy.Time(0), rospy.Duration(timeout))
            return True
        except (tf2_ros.LookupException, tf2_ros.ConnectivityException, tf2_ros.ExtrapolationException):
            return False

    def get_odom_pose(self):
        with self._lock:
            if self.latest_odom is None:
                return None
            msg = self.latest_odom

        p = msg.pose.pose.position
        o = msg.pose.pose.orientation
        quat = [o.x, o.y, o.z, o.w]
        _, _, yaw = euler_from_quaternion(quat)
        return (p.x, p.y, yaw)

    def get_imu_yaw(self):
        with self._lock:
            if self.latest_imu is None:
                return None
            msg = self.latest_imu

        o = msg.orientation
        quat = [o.x, o.y, o.z, o.w]
        _, _, yaw = euler_from_quaternion(quat)
        return yaw

    def get_odom_twist(self):
        with self._lock:
            if self.latest_odom is None:
                return None
            msg = self.latest_odom

        # linear x, angular z
        return (msg.twist.twist.linear.x, msg.twist.twist.angular.z)

    def pub_cmd_vel(self, v_x, w_z):
        # TianRacer uses AckermannDriveStamped
        # v_x -> speed
        # w_z -> steering_angle (approx)
        msg = AckermannDrive()
        # msg.header.stamp = rospy.Time.now()  # AckermannDrive has no header
        # msg.header.frame_id = "base_link"  # AckermannDrive has no header

        msg.speed = v_x
        # 简单映射：角速度 -> 转向角。
        # 实际阿克曼模型中: tan(delta) = L * w / v
        # 这里仅用于自检，直接作为转向角控制输入，假设 w_z 即为 steering_angle (rad)
        msg.steering_angle = w_z

        self.cmd_pub.publish(msg)

    def get_scan_dist(self, angle_deg, fov_deg=10.0):
        with self._lock:
            if self.latest_scan is None:
                return None
            scan = self.latest_scan

        angle_rad = np.deg2rad(angle_deg)
        fov_rad = np.deg2rad(fov_deg)

        # 计算索引
        # 假设 angle_min, angle_increment
        min_angle = scan.angle_min
        inc = scan.angle_increment

        target_idx_center = int((angle_rad - min_angle) / inc)
        width_idxs = int(fov_rad / inc)

        start_idx = max(0, target_idx_center - width_idxs // 2)
        end_idx = min(len(scan.ranges), target_idx_center + width_idxs // 2)

        if start_idx >= end_idx:
            return None

        ranges = np.array(scan.ranges[start_idx:end_idx])
        # 过滤无效值
        valid = ranges[(ranges >= scan.range_min) & (ranges <= scan.range_max)]

        if len(valid) == 0:
            return float('inf')

        return np.mean(valid)

    def get_lidar_range(self, angle_deg, target_frame="tianracer/base_link"):
        """
        Get distance from robot center (base_link) in specific direction.

        This accounts for the offset between the lidar and the robot center.
        Logic:
        1. Find the laser ray corresponding to the requested angle (in base_link frame).
           But since we only have laser data in laser frame, it's easier to:
           - Iterate over laser points or find the one that transforms to the target angle.

        Simplified approach for logging:
        1. Get the range at the requested angle in LIDAR frame.
        2. Transform that point to base_link to get actual distance from robot center.

        NOTE: This assumes the requested angle_deg is relative to ROBOT heading (base_link),
        but simply taking the range at that angle from LIDAR frame is only correct if LIDAR
        is mounted at (0,0,0) and aligned.

        If Lidar has offset (x,y), range at 0 deg in Lidar frame is distance from Lidar, not Robot Center.

        Correct Logic for "Distance in direction theta relative to base_link":
        We want to measure obstacle distance along a ray from base_link.

        However, for the specific request "Front Value" and "Left Value", usually it implies
        Scan data index matching the robot's front/left.

        If we assume the user just wants the range value of the ray that points forward/left relative to Robot:
        1. Transform (0,0,0) of base_link to laser_link? No.
        2. We need the laser ray that is parallel to the robot's X-axis (for Front) or Y-axis (for Left).

        Let's do this:
        1. Lookup transform base_link -> laser_link.
        2. Calculate the angle in laser_link that corresponds to the desired angle in base_link.
           angle_laser = angle_base - yaw_offset
        3. Get range at angle_laser.
        4. (Optional) If we want distance from base_link origin, we take that point and transform back.
           But usually "laser distance" implies "reading from the sensor".
           The user asked: "convert data to base_link frame".

        Let's interpret "Front Value" as: The X-coordinate of the obstacle detected in front of the robot (in base_link).
        """
        with self._lock:
            if self.latest_scan is None:
                return None
            data = self.latest_scan

        # 1. Get Transform from base_link to laser_link to find the correct ray angle
        try:
            # We need laser_frame -> base_link to know how laser is mounted
            # or base_link -> laser_frame to project vectors
            # Usually: look up transform from target_frame to data.header.frame_id
            trans = self.tf_buffer.lookup_transform(
                data.header.frame_id, # Source (Lidar)
                target_frame, # Target (Base) - wait, we want angle IN LIDAR FRAME that corresponds to angle IN BASE FRAME
                rospy.Time(0),
                rospy.Duration(0.1)
            )
            # But simpler: Transform (1,0,0) from base to lidar, see what angle it is.
            # actually we can just use the yaw component of the transform if 2D

            # Quat to Euler
            q = trans.transform.rotation
            _, _, yaw_base_in_laser = euler_from_quaternion([q.x, q.y, q.z, q.w])

            # The angle we want to probe in base_link (e.g., 0.0 for front)
            desired_angle_base = np.deg2rad(angle_deg)

            # The corresponding angle in laser frame
            # If base is rotated by yaw relative to laser, then vector v_base is v_laser rotated by -yaw?
            # Geometry:
            # angle_in_laser = angle_in_base + yaw_offset_base_to_laser
            # Wait, trans is base->laser (target=data.frame, source=base)
            # So trans describes base frame expressed in laser frame.
            # So angle_in_laser = angle_in_base + yaw_of_base_in_laser

            target_angle_laser = desired_angle_base + yaw_base_in_laser

        except Exception as e:
            # Fallback if TF fails: assume aligned
            rospy.logwarn_throttle(2.0, f"DEBUG: TF lookup failed: {e}")
            target_angle_laser = np.deg2rad(angle_deg)
            # Default to no transform if failed
            trans = None

        # 2. Extract Range
        # Robust index calculation for circular lidar
        # Calculate angle difference relative to angle_min, normalize to [0, 2*pi)
        diff_angle = (target_angle_laser - data.angle_min) % (2 * np.pi)

        # Calculate center index
        center_idx = int(round(diff_angle / data.angle_increment))

        # Handle wrap around for index
        if center_idx >= len(data.ranges):
            center_idx = 0

        # Get a small window of points to robustly determine distance
        # e.g. 5 points around the target index
        window_size = 5
        half_window = window_size // 2

        valid_ranges = []
        for i in range(-half_window, half_window + 1):
            idx = (center_idx + i) % len(data.ranges)
            r = data.ranges[idx]
            if data.range_min <= r <= data.range_max:
                valid_ranges.append(r)

        if not valid_ranges:
            # If all points in window are invalid, try return raw center (it will be inf)
            range_val = data.ranges[center_idx]
        else:
            # Use the median or min of the valid ranges to filter out sparkles
            # For obstacle avoidance check, Min is safer. For general distance, Median is stable.
            # Using Median here to match general expectations
            range_val = np.median(valid_ranges)

        # Check validity
        if range_val < data.range_min or range_val > data.range_max:
             # rospy.logwarn(f"DEBUG: Range invalid: {range_val}")
             return float('inf') # Return inf to indicate clear/out of range, or None? Wall follower used filter value.

        # 3. Transform Point to Base Link (Coordinate Transformation)
        # We have range r at angle theta (in laser frame).
        # Point in Laser Frame: (r*cos(theta), r*sin(theta), 0)
        # We want Point in Base Link.

        # If we failed to get TF earlier, just return the raw range (best effort)
        if trans is None:
             return range_val

        # Construct PointStamped in Laser Frame
        p_laser = PointStamped()
        p_laser.header = data.header # Use laser timestamp and frame
        p_laser.point.x = range_val * np.cos(target_angle_laser)
        p_laser.point.y = range_val * np.sin(target_angle_laser)
        p_laser.point.z = 0.0

        try:
            # Transform to target_frame (base_link)
            p_base = self.tf_buffer.transform(p_laser, target_frame, timeout=rospy.Duration(0.1))

            # Return the distance from origin of base_link, or just the X/Y component?
            # "The laser distance value ... in base_link"
            # Usually means the norm, or the projected distance?
            # If we are looking Forward (0 deg), we probably care about X in base_link.
            # If we are looking Left (90 deg), we care about Y in base_link.

            # Simple Euclidean distance from robot center
            dist_from_center = np.hypot(p_base.point.x, p_base.point.y)
            return dist_from_center

        except Exception as e:
            # rospy.logwarn_throttle(2.0, f"DEBUG: Point transform failed: {e}")
            return range_val

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
                # Avoid logging raw image bytes; just validate dimensions
                valid = (msg.height > 0 and msg.width > 0 and msg.step > 0)
                return (valid, None)

            if isinstance(msg, CompressedImage):
                valid = bool(msg.format and len(msg.data) > 0)
                return (valid, None)

            if sample_value is not None:
                # Avoid dumping large byte arrays
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

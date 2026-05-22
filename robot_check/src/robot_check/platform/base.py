class BasePlatform(object):
    """
    Abstract Interface for Robot Middleware (ROS1/ROS2)
    """
    def __init__(self):
        pass

    def init_node(self, name):
        raise NotImplementedError

    def get_time(self):
        raise NotImplementedError

    def sleep(self, seconds):
        raise NotImplementedError

    def shutdown(self):
        raise NotImplementedError

    def get_param(self, name, default=None):
        raise NotImplementedError

    def get_package_path(self, package_name):
        """
        获取包的路径
        Returns: str or None
        """
        raise NotImplementedError

    def measure_topic_frequency(self, topic_name, topic_type_str, duration=5.0):
        """
        监听话题一段时间，返回统计信息
        Returns:
            dict: {
                'count': int,
                'hz': float,
                'std_dev': float,
                'frame_id': str,
                'error': str
            }
        """
        raise NotImplementedError

    def check_tf(self, parent_frame, child_frame, timeout=1.0):
        """
        检查 TF 变换是否存在
        Returns: bool
        """
        raise NotImplementedError

    def get_odom_pose(self):
        """
        获取当前里程计位姿
        Returns: (x, y, yaw) or None
        """
        raise NotImplementedError

    def get_odom_twist(self):
        """
        获取当前里程计速度
        Returns: (linear_x, angular_z) or None
        """
        raise NotImplementedError

    def get_imu_yaw(self):
        """
        获取当前 IMU 偏航角
        Returns: yaw (rad) or None
        """
        raise NotImplementedError

    def get_lidar_range(self, angle_deg, fov_deg=5.0):
        """
        获取指定角度（车体坐标系）的激光距离
        """
        raise NotImplementedError

    def pub_cmd_vel(self, v_x, w_z):
        """
        发布速度指令
        """
        raise NotImplementedError

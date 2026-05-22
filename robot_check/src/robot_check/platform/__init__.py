import os
import platform as _stdlib_platform
import sys

# Guard against shadowing stdlib platform module by this package path
sys.modules['platform'] = _stdlib_platform

def get_platform():
    ros_version = os.environ.get('ROS_VERSION', '1')
    
    if ros_version == '2':
        try:
            from .ros2_impl import ROS2Platform
            return ROS2Platform()
        except ImportError as e:
            print(f"Failed to load ROS2 Platform: {e}")
            raise
    else:
        from .ros1_impl import ROS1Platform
        return ROS1Platform()

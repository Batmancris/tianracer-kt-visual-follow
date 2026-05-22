"""ROS2 Launch File for Live777 Bridge"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare

def generate_launch_description():
    """生成启动描述"""
    
    # 配置文件路径
    config_file = PathJoinSubstitution([
        FindPackageShare('webrtc_ros_bridge'),
        'config',
        'stream_config.yaml'
    ])
    
    # 声明启动参数
    declare_config_arg = DeclareLaunchArgument(
        'config_file',
        default_value=config_file,
        description='Path to config file'
    )

    config_params_file = LaunchConfiguration('config_file')

    # Live777 Bridge 节点
    live777_bridge_node = Node(
        package='webrtc_ros_bridge',
        executable='bridge_node',  # 对应 setup.py 中的 entry_point
        name='webrtc_ros_bridge',
        parameters=[
            {'config_path': config_params_file}
        ],
        output='screen'
    )

    # 可选：图像查看器
    image_view_node = Node(
        package='image_view',
        executable='image_view',
        name='image_view',
        remappings=[('image', '/live777/image')],
        output='screen'
    )
    
    return LaunchDescription([
        declare_config_arg,
        live777_bridge_node,
        # image_view_node,  # 取消注释以启用
    ])
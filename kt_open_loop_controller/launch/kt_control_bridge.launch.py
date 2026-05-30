from launch import LaunchDescription
from launch_ros.actions import Node


def generate_launch_description():
    return LaunchDescription([
        Node(
            package="kt_open_loop_controller",
            executable="kt_control_bridge",
            name="kt_control_bridge",
            output="screen",
        ),
    ])

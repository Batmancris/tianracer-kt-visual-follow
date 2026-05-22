#!/usr/bin/env python3
"""
ROS2 launch file for TianRacer robot_check auto checks.
Runs the unified run_all_checks.py entrypoint with configurable auto_close.
"""

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, SetEnvironmentVariable
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    auto_close_arg = DeclareLaunchArgument(
        'auto_close',
        default_value='true',
        description='Exit after checks complete'
    )

    # Force ROS_VERSION=2 in case both environments are sourced
    set_ros_version = SetEnvironmentVariable('ROS_VERSION', '2')

    checker_node = Node(
        package='robot_check',
        executable='run_checks',
        name='robot_checker',
        output='screen',
        emulate_tty=True,
        parameters=[{'auto_close': LaunchConfiguration('auto_close')}]
    )

    return LaunchDescription([
        auto_close_arg,
        set_ros_version,
        checker_node,
    ])

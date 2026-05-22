#!/usr/bin/env python3

import os
from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('kt_visual_lidar_follow')
    default_config = os.path.join(pkg_share, 'config', 'kt_visual_lidar_follow.yaml')

    return LaunchDescription([
        DeclareLaunchArgument(
            'config',
            default_value=default_config,
            description='Path to kt_visual_lidar_follow parameter file'),
        DeclareLaunchArgument(
            'dry_run',
            default_value='true',
            description='Dry-run mode (true = no /cmd_vel published)'),
        Node(
            package='kt_visual_lidar_follow',
            executable='kt_visual_lidar_follow_node',
            name='kt_visual_lidar_follow_node',
            output='screen',
            parameters=[
                LaunchConfiguration('config'),
                {'dry_run': LaunchConfiguration('dry_run')},
            ],
        ),
    ])

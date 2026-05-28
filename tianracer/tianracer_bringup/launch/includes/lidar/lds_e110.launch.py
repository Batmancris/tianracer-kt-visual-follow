#!/usr/bin/env python3
import os
from launch import LaunchDescription
from launch.substitutions import PathJoinSubstitution, LaunchConfiguration
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from ament_index_python.packages import get_package_share_directory

default_namespace = os.environ.get("TIANBOT_NAME", "")
default_serial_port = os.environ.get("TIANRACER_LIDAR_PORT", "/dev/tianbot_lidar")
default_namespace = f"" if default_namespace == '' or default_namespace == '/' else default_namespace
default_laser_frame_id = f"laser" if default_namespace == '' else f"{default_namespace}/laser"


def generate_launch_description():
    namespace = LaunchConfiguration('namespace')
    serial_port = LaunchConfiguration('serial_port')
    frame_id = LaunchConfiguration('frame_id')

    declare_namespace_cmd = DeclareLaunchArgument(
        "namespace", default_value=default_namespace, description="Top-level namespace"
    )

    declare_serial_port_cmd = DeclareLaunchArgument(
        'serial_port',
        default_value=default_serial_port,
        description='Specifying usb port to connected lidar')

    declare_frame_id_cmd = DeclareLaunchArgument(
        'frame_id',
        default_value=default_laser_frame_id,
        description='Specifying frame_id of lidar')

    bluesea_node = Node(
        package='bluesea2',
        executable='bluesea2_node',
        name='lds_e110',
        namespace=namespace,
        output='screen',
        parameters=[{
            'scan_topic': 'scan_raw',
            'cloud_topic': 'cloud',
            'frame_id': frame_id,
            'min_dist': 0.05,
            'max_dist': 50.0,
            'output_scan': True,
            'output_cloud': False,
            'output_cloud2': False,
            'output_360': True,
            'inverted': False,
            'reversed': True,
            'hard_resample': False,
            'soft_resample': False,
            'with_angle_filter': False,
            'min_angle': -3.1415926,
            'max_angle': 3.1415926,
            'type': 'uart',
            'port': serial_port,
            'baud_rate': 230400,
            'uuid': -1,
            'rpm': -1,
            'resample_res': -1.0,
            'unit_is_mm': -1,
            'with_smooth': -1,
            'with_deshadow': -1,
            'with_confidence': -1,
            'direction': -1,
            'error_circle': 3,
            'error_scale': 0.9,
        }]
    )

    laser_filters_node = Node(
        package="laser_filters",
        executable="scan_to_scan_filter_chain",
        namespace=namespace,
        parameters=[
            PathJoinSubstitution([
                get_package_share_directory("tianracer_bringup"),
                "param", "tianbot_laser_config.yaml",
            ])],
        remappings=[('scan', 'scan_raw'),
                    ('scan_filtered', 'scan'), ]
    )

    ld = LaunchDescription()
    ld.add_action(declare_namespace_cmd)
    ld.add_action(declare_serial_port_cmd)
    ld.add_action(declare_frame_id_cmd)
    ld.add_action(bluesea_node)
    ld.add_action(laser_filters_node)

    return ld

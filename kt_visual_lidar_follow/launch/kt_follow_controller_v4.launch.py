#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def declare_arg(name, default_value, description):
    return DeclareLaunchArgument(name, default_value=default_value, description=description)


def arg(name):
    return LaunchConfiguration(name)


def generate_launch_description():
    launch_args = [
        declare_arg("enable_control", "false", "Publish /ackermann_cmd only in formal FOLLOW mode"),
        declare_arg("target_distance_m", "1.0", "Reserved target distance parameter"),
        declare_arg("stop_distance_m", "1.0", "Distance threshold for zero speed"),
        declare_arg("full_speed_distance_m", "1.6", "Distance threshold for max speed"),
        declare_arg("max_speed", "0.25", "Maximum forward speed"),
        declare_arg("max_steering_angle", "0.18", "Maximum steering angle"),
        declare_arg("max_accel", "0.60", "Acceleration limit"),
        declare_arg("max_decel", "1.20", "Deceleration limit"),
        declare_arg("max_steer_rate", "0.60", "Steering rate limit"),
        declare_arg("theta_deadband", "0.025", "Theta deadband"),
        declare_arg("theta_filter_alpha", "0.35", "Theta EMA alpha"),
        declare_arg("dist_filter_alpha", "0.30", "Distance EMA alpha"),
        declare_arg("target_grace_sec", "0.25", "Target grace period"),
        declare_arg("stale_stop_sec", "0.45", "Stale stop timeout"),
        declare_arg("angle_window_deg", "8.0", "Lidar association window"),
    ]

    controller = Node(
        package="kt_visual_lidar_follow",
        executable="kt_follow_controller_v4.py",
        name="kt_follow_controller_v4",
        output="screen",
        arguments=[
            "--enable-control", arg("enable_control"),
            "--target-distance-m", arg("target_distance_m"),
            "--stop-distance-m", arg("stop_distance_m"),
            "--full-speed-distance-m", arg("full_speed_distance_m"),
            "--max-speed", arg("max_speed"),
            "--max-steering-angle", arg("max_steering_angle"),
            "--max-accel", arg("max_accel"),
            "--max-decel", arg("max_decel"),
            "--max-steer-rate", arg("max_steer_rate"),
            "--theta-deadband", arg("theta_deadband"),
            "--theta-filter-alpha", arg("theta_filter_alpha"),
            "--dist-filter-alpha", arg("dist_filter_alpha"),
            "--target-grace-sec", arg("target_grace_sec"),
            "--stale-stop-sec", arg("stale_stop_sec"),
            "--angle-window-deg", arg("angle_window_deg"),
        ],
    )

    return LaunchDescription(launch_args + [controller])

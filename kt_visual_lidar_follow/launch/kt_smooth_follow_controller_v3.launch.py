#!/usr/bin/env python3

from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def declare_arg(name, default_value, description):
    return DeclareLaunchArgument(
        name,
        default_value=default_value,
        description=description,
    )


def arg(name):
    return LaunchConfiguration(name)


def generate_launch_description():
    launch_args = [
        declare_arg("enable_control", "true", "Publish /ackermann_cmd while mode is FOLLOW"),
        declare_arg("max_test_seconds", "0.0", "Maximum runtime in seconds; 0 means run forever"),
        declare_arg("target_distance_m", "1.00", "Reserved target distance parameter"),
        declare_arg("stop_distance_m", "1.00", "Distance at or below which speed target is zero"),
        declare_arg("full_speed_distance_m", "1.60", "Distance at or above which speed target is max_speed"),
        declare_arg("max_speed", "0.15", "Launch default for low-speed ground testing"),
        declare_arg("max_steering_angle", "0.18", "Steering angle clamp in radians"),
        declare_arg("k_steer", "0.85", "Proportional gain from theta to steering"),
        declare_arg("steer_sign", "-1.0", "Steering sign correction"),
        declare_arg("theta_deadband", "0.025", "Theta deadband in radians"),
        declare_arg("theta_filter_alpha", "0.35", "Theta EMA alpha"),
        declare_arg("dist_filter_alpha", "0.30", "Distance EMA alpha"),
        declare_arg("target_grace_sec", "0.25", "Fresh target grace period"),
        declare_arg("stale_stop_sec", "0.45", "Target staleness stop timeout"),
        declare_arg("max_accel", "0.60", "Acceleration limit in m/s^2"),
        declare_arg("max_decel", "1.20", "Deceleration limit in m/s^2"),
        declare_arg("max_steer_rate", "0.60", "Steering rate limit in rad/s"),
    ]

    controller = Node(
        package="kt_visual_lidar_follow",
        executable="kt_smooth_follow_controller_v3.py",
        name="smooth_follow_controller",
        output="screen",
        arguments=[
            "--enable-control",
            arg("enable_control"),
            "--max-test-seconds",
            arg("max_test_seconds"),
            "--target-distance-m",
            arg("target_distance_m"),
            "--stop-distance-m",
            arg("stop_distance_m"),
            "--full-speed-distance-m",
            arg("full_speed_distance_m"),
            "--max-speed",
            arg("max_speed"),
            "--max-steering-angle",
            arg("max_steering_angle"),
            "--k-steer",
            arg("k_steer"),
            "--steer-sign",
            arg("steer_sign"),
            "--theta-deadband",
            arg("theta_deadband"),
            "--theta-filter-alpha",
            arg("theta_filter_alpha"),
            "--dist-filter-alpha",
            arg("dist_filter_alpha"),
            "--target-grace-sec",
            arg("target_grace_sec"),
            "--stale-stop-sec",
            arg("stale_stop_sec"),
            "--max-accel",
            arg("max_accel"),
            "--max-decel",
            arg("max_decel"),
            "--max-steer-rate",
            arg("max_steer_rate"),
        ],
    )

    return LaunchDescription(launch_args + [controller])

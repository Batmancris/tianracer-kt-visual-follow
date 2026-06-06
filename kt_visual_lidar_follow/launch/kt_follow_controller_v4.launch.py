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
        declare_arg("scan_topic", "/tianracer/scan", "LaserScan topic for direct distance reads"),
        declare_arg("odom_topic", "/odom", "Odometry topic for braking guard"),
        declare_arg("target_distance_m", "0.5", "Target following distance"),
        declare_arg("restart_distance_m", "0.7", "Distance required to leave HOLD"),
        declare_arg("stop_distance_m", "0.5", "Distance threshold for zero speed"),
        declare_arg("full_speed_distance_m", "1.0", "Distance threshold for max speed"),
        declare_arg("max_speed", "0.25", "Maximum forward speed"),
        declare_arg("min_effective_speed_mps", "0.30", "Minimum effective positive speed"),
        declare_arg("slow_speed_mps", "0.35", "Slow approach speed"),
        declare_arg("fast_speed_mps", "0.50", "Fast approach speed"),
        declare_arg("stop_decel_mps2", "0.80", "Braking deceleration estimate"),
        declare_arg("stop_margin_m", "0.08", "Extra stop margin"),
        declare_arg("max_valid_odom_age_ms", "200", "Maximum odom age"),
        declare_arg("max_valid_range_age_ms", "200", "Maximum range age"),
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
        declare_arg("ackermann_cmd_topic", "/ackermann_cmd", "AckermannDrive command topic"),
        declare_arg("targets_topic", "/bear_detection/targets", "Bear detection targets topic"),
    ]

    controller = Node(
        package="kt_visual_lidar_follow",
        executable="kt_follow_controller_v4.py",
        name="kt_follow_controller_v4",
        output="screen",
        arguments=[
            "--enable-control", arg("enable_control"),
            "--scan-topic", arg("scan_topic"),
            "--odom-topic", arg("odom_topic"),
            "--target-distance-m", arg("target_distance_m"),
            "--restart-distance-m", arg("restart_distance_m"),
            "--stop-distance-m", arg("stop_distance_m"),
            "--full-speed-distance-m", arg("full_speed_distance_m"),
            "--max-speed", arg("max_speed"),
            "--min-effective-speed-mps", arg("min_effective_speed_mps"),
            "--slow-speed-mps", arg("slow_speed_mps"),
            "--fast-speed-mps", arg("fast_speed_mps"),
            "--stop-decel-mps2", arg("stop_decel_mps2"),
            "--stop-margin-m", arg("stop_margin_m"),
            "--max-valid-odom-age-ms", arg("max_valid_odom_age_ms"),
            "--max-valid-range-age-ms", arg("max_valid_range_age_ms"),
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
            "--ackermann-cmd-topic", arg("ackermann_cmd_topic"),
            "--targets-topic", arg("targets_topic"),
        ],
    )

    return LaunchDescription(launch_args + [controller])

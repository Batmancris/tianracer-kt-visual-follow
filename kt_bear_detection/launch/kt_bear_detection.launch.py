import os

from ament_index_python.packages import get_package_prefix, get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    share_dir = get_package_share_directory("kt_bear_detection")
    package_prefix = get_package_prefix("kt_bear_detection")
    default_config = os.path.join(share_dir, "config", "kt_bear_detection.yaml")
    default_model_path = os.path.join(
        package_prefix,
        "lib",
        "kt_bear_detection",
        "config",
        "bear_yolov8n_x5_640_nv12.bin",
    )

    config_arg = DeclareLaunchArgument("config_file", default_value=default_config)
    image_topic_arg = DeclareLaunchArgument(
        "image_topic", default_value="/tianracer/camera/image_raw"
    )
    output_topic_arg = DeclareLaunchArgument(
        "output_topic", default_value="/bear_detection/targets"
    )
    model_path_arg = DeclareLaunchArgument("model_path", default_value=default_model_path)
    box_format_arg = DeclareLaunchArgument("box_format", default_value="cxcywh")

    node = Node(
        package="kt_bear_detection",
        executable="kt_bear_detection_node",
        name="kt_bear_detection",
        output="screen",
        parameters=[
            LaunchConfiguration("config_file"),
            {
                "image_topic": LaunchConfiguration("image_topic"),
                "output_topic": LaunchConfiguration("output_topic"),
                "model_path": LaunchConfiguration("model_path"),
                "box_format": LaunchConfiguration("box_format"),
            },
        ],
    )

    return LaunchDescription([
        config_arg,
        image_topic_arg,
        output_topic_arg,
        model_path_arg,
        box_format_arg,
        node,
    ])

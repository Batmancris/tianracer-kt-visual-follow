# Copyright (c) 2024，D-Robotics.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import os

from launch import LaunchDescription
from launch_ros.actions import Node

from launch.substitutions import TextSubstitution
from launch.substitutions import LaunchConfiguration
from launch.actions import DeclareLaunchArgument
from launch.actions import IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from ament_index_python import get_package_share_directory

def generate_launch_description():
    # gesture control
    gesture_control_node = Node(
        package='gesture_control',
        executable='gesture_control',
        output='screen',
        parameters=[
            {"ai_msg_sub_topic_name": "/hobot_hand_gesture_detection"},
            {"twist_pub_topic_name": "/tianracer/cmd_vel"},
            {"activate_wakeup_gesture": 0},
            {"track_serial_lost_num_thr": 100},
            {"move_step": 0.5},
            {"rotate_step": 0.5}
        ],
        arguments=['--ros-args', '--log-level', 'warn']
    )

    # web
    # web_smart_topic_arg = DeclareLaunchArgument(
    #     'smart_topic',
    #     default_value='/hobot_mono2d_body_detection',
    #     description='websocket smart topic')
    # web_node = IncludeLaunchDescription(
    #     PythonLaunchDescriptionSource(
    #         os.path.join(
    #             get_package_share_directory('websocket'),
    #             'launch/websocket.launch.py')),
    #     launch_arguments={
    #         'websocket_image_topic': '/image',
    #         'websocket_smart_topic': LaunchConfiguration('smart_topic')
    #     }.items()
    # )

    # mono2d body detection
    model_file_name_launch_arg = DeclareLaunchArgument(
        "kps_model_file_name", default_value=TextSubstitution(text="config/multitask_body_head_face_hand_kps_960x544.hbm")
    )
    model_type_launch_arg = DeclareLaunchArgument(
        "kps_model_type", default_value=TextSubstitution(text="0")
    )
    track_mode_launch_arg = DeclareLaunchArgument(
        "kps_track_mode", default_value=TextSubstitution(text="1")
    )

    mono2d_body_pub_topic_arg = DeclareLaunchArgument(
        'mono2d_body_pub_topic',
        default_value='/hobot_mono2d_body_detection',
        description='mono2d body ai message publish topic')
        
    mono2d_body_det_node = Node(
        package='mono2d_body_detection',
        executable='mono2d_body_detection',
        output='screen',
        parameters=[
            {"model_file_name": LaunchConfiguration('kps_model_file_name')},
            {"model_type": LaunchConfiguration('kps_model_type')},
            {"track_mode": LaunchConfiguration('kps_track_mode')},
            {"ai_msg_pub_topic_name": LaunchConfiguration(
                'mono2d_body_pub_topic')}
        ],
        arguments=['--ros-args', '--log-level', 'warn'],
        remappings=[('/hbmem_img', '/tianracer/camera/image_raw')]
    )

    # 人手关键点检测
    hand_lmk_pub_topic_arg = DeclareLaunchArgument(
        'hand_lmk_pub_topic',
        default_value='/hobot_hand_lmk_detection',
        description='hand landmark ai message publish topic')

    hand_lmk_det_node = Node(
        package='hand_lmk_detection',
        executable='hand_lmk_detection',
        output='screen',
        parameters=[
            {"ai_msg_pub_topic_name": LaunchConfiguration(
                'hand_lmk_pub_topic')},
            {"ai_msg_sub_topic_name": "/hobot_mono2d_body_detection"}
        ],
        arguments=['--ros-args', '--log-level', 'warn']
    )

    # 手势识别算法
    web_smart_topic_arg = DeclareLaunchArgument(
        'smart_topic',
        default_value='/hobot_hand_gesture_detection',
        description='websocket smart topic')
    is_dynamic_gesture_arg = DeclareLaunchArgument(
        'is_dynamic_gesture',
        default_value='false',
        description='true is dynamic gesture, false is static gesture')
    log_level_arg = DeclareLaunchArgument(
        'log_level',
        default_value='warn',
        description='log level')
    time_interval_sec_arg = DeclareLaunchArgument(
        'time_interval_sec',
        default_value='0.25',
        description='time interval for hand gesture voting')

    hand_gesture_det_node = Node(
        package='hand_gesture_detection',
        executable='hand_gesture_detection',
        output='screen',
        parameters=[
            {"ai_msg_pub_topic_name": "/hobot_hand_gesture_detection"},
            {"ai_msg_sub_topic_name": "/hobot_hand_lmk_detection"},
            {"is_dynamic_gesture": LaunchConfiguration('is_dynamic_gesture')},
            {"time_interval_sec": LaunchConfiguration('time_interval_sec')}
        ],
        arguments=['--ros-args', '--log-level', LaunchConfiguration('log_level')]
    )

    return LaunchDescription([
        # body detection
        model_file_name_launch_arg,
        model_type_launch_arg,
        track_mode_launch_arg,
        mono2d_body_pub_topic_arg,
        mono2d_body_det_node,
        # hand landmark detection
        hand_lmk_pub_topic_arg,
        hand_lmk_det_node,
        # web display
        # web_smart_topic_arg,
        # web_node,
        # hand gesture detection
        web_smart_topic_arg,
        is_dynamic_gesture_arg,
        log_level_arg,
        time_interval_sec_arg,
        hand_gesture_det_node,
        gesture_control_node
    ])

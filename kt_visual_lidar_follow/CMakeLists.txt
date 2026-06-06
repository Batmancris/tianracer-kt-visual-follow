cmake_minimum_required(VERSION 3.8)
project(kt_visual_lidar_follow)

find_package(ament_cmake REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(ai_msgs REQUIRED)

install(PROGRAMS
  scripts/kt_follow_controller_v4.py
  scripts/kt_camera_control_bridge.py
  scripts/kt_mjpeg_bridge.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)

ament_package()

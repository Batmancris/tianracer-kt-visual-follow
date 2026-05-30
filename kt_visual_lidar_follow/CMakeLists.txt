cmake_minimum_required(VERSION 3.8)
project(kt_visual_lidar_follow)

if(CMAKE_COMPILER_IS_GNUCXX OR CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  add_compile_options(-Wall -Wextra -Wpedantic)
endif()

find_package(ament_cmake REQUIRED)
find_package(rclcpp REQUIRED)
find_package(std_msgs REQUIRED)
find_package(sensor_msgs REQUIRED)
find_package(geometry_msgs REQUIRED)
find_package(ai_msgs REQUIRED)
find_package(tf2 REQUIRED)
find_package(tf2_ros REQUIRED)
find_package(tf2_geometry_msgs REQUIRED)

set(dependencies
  rclcpp
  std_msgs
  sensor_msgs
  geometry_msgs
  ai_msgs
  tf2
  tf2_ros
  tf2_geometry_msgs
)

add_executable(kt_visual_lidar_follow_node
  src/kt_visual_lidar_follow_node.cpp
  src/target_parser.cpp
  src/lidar_associator.cpp
  src/follow_fsm.cpp
)

target_include_directories(kt_visual_lidar_follow_node PUBLIC
  "$<BUILD_INTERFACE:${CMAKE_CURRENT_SOURCE_DIR}/include>"
  "$<INSTALL_INTERFACE:include>"
)

ament_target_dependencies(kt_visual_lidar_follow_node ${dependencies})

install(TARGETS kt_visual_lidar_follow_node
  DESTINATION lib/${PROJECT_NAME}
)

install(PROGRAMS
  scripts/kt_smooth_follow_controller_v3.py
  scripts/kt_follow_controller_v4.py
  scripts/kt_camera_control_bridge.py
  scripts/kt_mjpeg_bridge.py
  DESTINATION lib/${PROJECT_NAME}
)

install(DIRECTORY include/
  DESTINATION include/${PROJECT_NAME}
)

install(DIRECTORY config launch
  DESTINATION share/${PROJECT_NAME}/
)

if(BUILD_TESTING)
  find_package(ament_lint_auto REQUIRED)
  set(ament_cmake_copyright_FOUND TRUE)
  set(ament_cmake_cpplint_FOUND TRUE)
  ament_lint_auto_find_test_dependencies()
endif()

ament_package()

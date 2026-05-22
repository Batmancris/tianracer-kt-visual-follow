cmake_minimum_required(VERSION 3.0.2)
project(robot_check)

if(DEFINED ENV{ROS_VERSION} AND "$ENV{ROS_VERSION}" STREQUAL "2")
  return()
endif()

find_package(catkin REQUIRED COMPONENTS
  ackermann_msgs
  geometry_msgs
  nav_msgs
  sensor_msgs
  rospy
  tf2
  tf2_ros
  tf2_geometry_msgs
)

catkin_python_setup()

catkin_package(
  CATKIN_DEPENDS
    rospy
    std_msgs
    sensor_msgs
    cv_bridge
    ackermann_msgs
    geometry_msgs
    nav_msgs
    sensor_msgs
    rospy
    tf2
    tf2_ros
    tf2_geometry_msgs
)

# 安装Python脚本
catkin_install_python(PROGRAMS
  scripts/run_all_checks.py
  DESTINATION ${CATKIN_PACKAGE_BIN_DESTINATION}
)

# 安装launch文件
install(DIRECTORY launch/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/launch
  PATTERN ". svn" EXCLUDE
)

# 安装配置文件
install(DIRECTORY config/
  DESTINATION ${CATKIN_PACKAGE_SHARE_DESTINATION}/config
)
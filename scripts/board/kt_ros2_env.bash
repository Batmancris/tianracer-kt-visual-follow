#!/usr/bin/env bash

KT_WS="${KT_WS:-/home/sunrise/tianracer_ros2_ws}"
ROS_SETUP="/opt/ros/humble/setup.bash"
KT_LOCAL_SETUP="${KT_WS}/install/local_setup.bash"

kt_ros2_env_fail() {
  echo "[FAIL] $1" >&2
  return 1 2>/dev/null || exit 1
}

if [[ ! -f "$ROS_SETUP" ]]; then
  kt_ros2_env_fail "Missing $ROS_SETUP"
fi

if [[ ! -f "$KT_LOCAL_SETUP" ]]; then
  kt_ros2_env_fail "Missing $KT_LOCAL_SETUP"
fi

# Temporarily disable nounset — /opt/ros/humble/setup.bash uses unbound vars
set +u
source "$ROS_SETUP" || kt_ros2_env_fail "Failed to source $ROS_SETUP"
source "$KT_LOCAL_SETUP" || kt_ros2_env_fail "Failed to source $KT_LOCAL_SETUP"
set -u

echo "[OK] KT_ROS2_ENV_OK $KT_WS"

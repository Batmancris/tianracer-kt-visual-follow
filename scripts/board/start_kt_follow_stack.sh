#!/usr/bin/env bash
set -euo pipefail

SESSION="kt_follow_stack"
ENV_SCRIPT="/home/sunrise/kt_scripts/kt_ros2_env.bash"
WORKSPACE="/home/sunrise/tianracer_ros2_ws"
LOG_CORE="/tmp/kt_core.log"
LOG_CAMERA="/tmp/kt_camera.log"
LOG_BEAR_DET="/tmp/kt_bear_det.log"
LOG_LIDAR="/tmp/kt_lidar.log"
LOG_MJPEG="/tmp/kt_mjpeg.log"
LOG_CAMERA_CTRL="/tmp/kt_camera_ctrl.log"
LOG_ROSBRIDGE="/tmp/kt_rosbridge.log"
LOG_FOLLOW="/tmp/kt_follow_v4.log"
LOG_CHECK="/tmp/kt_check.log"
NO_WEB=0
NO_FOLLOW=0
FORCE_CAMERA_RELEASE=0
MJPEG_PORT="${MJPEG_PORT:-8080}"
ROSBRIDGE_PORT="${ROSBRIDGE_PORT:-9090}"
VIDEO_DEVICE="${VIDEO_DEVICE:-/dev/video0}"
LIDAR_DEVICE="${LIDAR_DEVICE:-/dev/tianbot_lidar}"

usage() {
  cat <<'EOF'
Usage: start_kt_follow_stack.sh [--no-web] [--no-follow] [--force-camera-release] [--help]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --no-web)
      NO_WEB=1
      ;;
    --no-follow)
      NO_FOLLOW=1
      ;;
    --force-camera-release)
      FORCE_CAMERA_RELEASE=1
      ;;
    --help)
      usage
      exit 0
      ;;
    *)
      echo "[ERROR] unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
  shift
done

require_cmd() {
  local name="$1"
  if ! command -v "$name" >/dev/null 2>&1; then
    echo "[ERROR] missing command: $name" >&2
    exit 1
  fi
}

source_env_snippet() {
  cat <<EOF
source "$ENV_SCRIPT"
EOF
}

run_in_window() {
  local window_name="$1"
  local body="$2"
  tmux new-window -t "$SESSION" -n "$window_name" >/dev/null
  tmux send-keys -t "$SESSION:$window_name" "$body" C-m
}

require_cmd tmux

if [[ ! -f "$ENV_SCRIPT" ]]; then
  echo "[ERROR] missing env script: $ENV_SCRIPT" >&2
  exit 1
fi

if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[ERROR] tmux session already exists: $SESSION" >&2
  echo "Run: bash /home/sunrise/kt_scripts/stop_kt_follow_stack.sh" >&2
  exit 1
fi

if [[ ! -e "$VIDEO_DEVICE" ]]; then
  echo "[ERROR] missing video device: $VIDEO_DEVICE" >&2
  exit 1
fi

if fuser "$VIDEO_DEVICE" >/dev/null 2>&1; then
  echo "[WARN] $VIDEO_DEVICE is currently in use"
  fuser "$VIDEO_DEVICE" 2>/dev/null || true
  if [[ "$FORCE_CAMERA_RELEASE" -eq 1 ]]; then
    echo "[WARN] force releasing $VIDEO_DEVICE via fuser -k"
    fuser -k "$VIDEO_DEVICE" || true
    sleep 1
  fi
fi

ENV_PREFIX="$(source_env_snippet)"

CORE_CMD="$ENV_PREFIX
ros2 launch tianracer_core tianracer_core.launch.py 2>&1 | tee \"$LOG_CORE\"
echo \"[INFO] core exited\"
exec bash"

CAMERA_CMD="$ENV_PREFIX
ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=camera -r __ns:=/tianracer -p video_device:=$VIDEO_DEVICE -p pixel_format:=mjpeg2rgb -p image_width:=640 -p image_height:=480 -p framerate:=30.0 -p io_method:=mmap -p camera_name:=tianracer_camera -p frame_id:=tianracer/camera_link -r image_raw:=camera/image_raw -r image_raw/compressed:=camera/image_compressed -r camera_info:=camera/camera_info 2>&1 | tee \"$LOG_CAMERA\"
echo \"[INFO] camera exited\"
exec bash"

BEAR_DET_CMD="$ENV_PREFIX
ros2 launch kt_bear_detection kt_bear_detection.launch.py 2>&1 | tee \"$LOG_BEAR_DET\"
echo \"[INFO] bear_det exited\"
exec bash"

LIDAR_CMD="$ENV_PREFIX
export TIANRACER_LIDAR=LDS_E110
export TIANRACER_LIDAR_PORT=$LIDAR_DEVICE
ros2 launch tianracer_bringup lidar.launch.py namespace:=tianracer 2>&1 | tee \"$LOG_LIDAR\"
echo \"[INFO] lidar exited\"
exec bash"

if [[ "$NO_WEB" -eq 1 ]]; then
  WEB_CMD="echo \"[INFO] web stack disabled by --no-web\" | tee \"$LOG_MJPEG\"
echo \"[INFO] web stack disabled by --no-web\" | tee \"$LOG_CAMERA_CTRL\"
echo \"[INFO] web stack disabled by --no-web\" | tee \"$LOG_ROSBRIDGE\"
exec bash"
else
  WEB_CMD="$ENV_PREFIX
python3 \"$WORKSPACE/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py\" --port \"$MJPEG_PORT\" --fps 8 2>&1 | tee \"$LOG_MJPEG\" &
MJPEG_PID=\$!
python3 \"$WORKSPACE/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py\" 2>&1 | tee \"$LOG_CAMERA_CTRL\" &
CAMERA_CTRL_PID=\$!
ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=$ROSBRIDGE_PORT 2>&1 | tee \"$LOG_ROSBRIDGE\" &
ROSBRIDGE_PID=\$!
echo \"[INFO] web pids: mjpeg=\$MJPEG_PID camera_ctrl=\$CAMERA_CTRL_PID rosbridge=\$ROSBRIDGE_PID\"
wait
echo \"[INFO] web exited\"
exec bash"
fi

if [[ "$NO_FOLLOW" -eq 1 ]]; then
  FOLLOW_CMD="echo \"[INFO] follow_v4 disabled by --no-follow\" | tee \"$LOG_FOLLOW\"
exec bash"
else
  FOLLOW_CMD="$ENV_PREFIX
ros2 launch kt_visual_lidar_follow kt_follow_controller_v4.launch.py \
  enable_control:=false \
  odom_topic:=/tianracer/odom \
  scan_topic:=/tianracer/scan \
  targets_topic:=/bear_detection/targets \
  ackermann_cmd_topic:=/tianracer/ackermann_cmd 2>&1 | tee \"$LOG_FOLLOW\"
echo \"[INFO] follow_v4 exited\"
exec bash"
fi

CHECK_CMD="$ENV_PREFIX
bash /home/sunrise/kt_scripts/check_kt_follow_stack.sh 2>&1 | tee \"$LOG_CHECK\"
echo \"[INFO] check finished\"
exec bash"

tmux new-session -d -s "$SESSION" -n core >/dev/null
tmux send-keys -t "$SESSION:core" "$CORE_CMD" C-m
run_in_window camera "$CAMERA_CMD"
run_in_window bear_det "$BEAR_DET_CMD"
run_in_window lidar "$LIDAR_CMD"
run_in_window web "$WEB_CMD"
run_in_window follow_v4 "$FOLLOW_CMD"
run_in_window check "$CHECK_CMD"

echo "[INFO] started tmux session: $SESSION"
echo "[INFO] attach: tmux attach -t $SESSION"
echo "[INFO] check:  bash /home/sunrise/kt_scripts/check_kt_follow_stack.sh"
echo "[INFO] stop:   bash /home/sunrise/kt_scripts/stop_kt_follow_stack.sh"

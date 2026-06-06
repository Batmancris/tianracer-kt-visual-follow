#!/usr/bin/env bash
set -euo pipefail

SESSION="kt_follow_stack"
ENV_SCRIPT="/home/sunrise/kt_scripts/kt_ros2_env.bash"
FORCE_CAMERA_RELEASE=0

usage() {
  cat <<'EOF'
Usage: stop_kt_follow_stack.sh [--force-camera-release] [--help]
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
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

if [[ -f "$ENV_SCRIPT" ]]; then
  source "$ENV_SCRIPT" || echo "[WARN] failed to load env script"
else
  echo "[WARN] env script missing: $ENV_SCRIPT"
fi

echo "=== safe stop publish ==="
if timeout 3 ros2 topic list 2>/dev/null | grep -Fx "/kt_follow/mode" >/dev/null 2>&1; then
  timeout -k 0.2s 2s ros2 topic pub --qos-durability volatile --once /kt_follow/mode std_msgs/msg/String '{data: "OFF"}' || true
else
  echo "[INFO] /kt_follow/mode not present"
fi

for ack_topic in /ackermann_cmd /tianracer/ackermann_cmd; do
  if timeout 3 ros2 topic list 2>/dev/null | grep -Fx "$ack_topic" >/dev/null 2>&1; then
    ACK_TYPE="$(timeout 3 ros2 topic type "$ack_topic" 2>/dev/null || true)"
    if [[ "$ACK_TYPE" == "ackermann_msgs/msg/AckermannDrive" ]]; then
      echo "[INFO] publishing zero AckermannDrive on $ack_topic"
      timeout -k 0.2s 2s ros2 topic pub --qos-durability volatile --once "$ack_topic" ackermann_msgs/msg/AckermannDrive '{speed: 0.0, steering_angle: 0.0}' || true
    elif [[ "$ACK_TYPE" == "ackermann_msgs/msg/AckermannDriveStamped" ]]; then
      echo "[INFO] publishing zero AckermannDriveStamped on $ack_topic"
      timeout -k 0.2s 2s ros2 topic pub --qos-durability volatile --once "$ack_topic" ackermann_msgs/msg/AckermannDriveStamped '{drive: {speed: 0.0, steering_angle: 0.0}}' || true
    elif [[ -n "$ACK_TYPE" ]]; then
      echo "[INFO] skip $ack_topic with unsupported type: $ACK_TYPE"
    else
      echo "[INFO] unable to resolve $ack_topic type"
    fi
  else
    echo "[INFO] $ack_topic not present"
  fi
done

echo "=== tmux ==="
if tmux has-session -t "$SESSION" 2>/dev/null; then
  tmux kill-session -t "$SESSION"
  echo "[INFO] killed session: $SESSION"
else
  echo "[INFO] session not running: $SESSION"
fi

echo "=== remaining ros nodes ==="
timeout 5 ros2 node list 2>/dev/null || true

echo "=== remaining related processes ==="
ps -ef | grep -E 'ros2|python|usb_cam|ffmpeg|mjpeg|rosbridge|follow|lidar' | grep -v grep || true

echo "=== /dev/video0 ==="
fuser /dev/video0 2>/dev/null || true
if [[ "$FORCE_CAMERA_RELEASE" -eq 1 ]]; then
  echo "[WARN] force releasing /dev/video0 via fuser -k"
  fuser -k /dev/video0 || true
fi

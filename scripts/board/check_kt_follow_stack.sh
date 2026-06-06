#!/usr/bin/env bash
set -uo pipefail

SESSION="kt_follow_stack"
ENV_SCRIPT="/home/sunrise/kt_scripts/kt_ros2_env.bash"
WORKSPACE="/home/sunrise/tianracer_ros2_ws"
RESULT="PASS_SAFE_DRY_RUN"
DRY_RUN_CONFIRMED=0
WEB_OK=1
ODOM_TOPIC=""
IMU_TOPIC=""
SCAN_TOPIC=""
IMAGE_TOPIC=""
CAMERA_INFO_TOPIC=""
ACK_TOPIC=""
ACK_MISMATCH=0

fail_missing() {
  echo "[FAIL_MISSING] $1"
  if [[ "$RESULT" != "FAIL_UNSAFE" ]]; then
    RESULT="FAIL_MISSING"
  fi
}

fail_unsafe() {
  echo "[FAIL_UNSAFE] $1"
  RESULT="FAIL_UNSAFE"
}

warn_partial() {
  echo "[WARN_PARTIAL] $1"
  if [[ "$RESULT" != "FAIL_UNSAFE" && "$RESULT" != "FAIL_MISSING" ]]; then
    RESULT="WARN_PARTIAL"
  fi
}

print_section() {
  echo
  echo "=== $1 ==="
}

topic_info_block() {
  timeout 5 ros2 topic info "$1" -v 2>/dev/null || true
}

topic_exists() {
  timeout 5 ros2 topic list 2>/dev/null | grep -Fx "$1" >/dev/null 2>&1
}

resolve_topic() {
  local preferred="$1"
  local fallback="$2"
  local selected=""
  if topic_exists "$preferred"; then
    selected="$preferred"
  elif [[ -n "$fallback" ]] && topic_exists "$fallback"; then
    selected="$fallback"
    echo "[WARN] legacy topic in use: $fallback (preferred: $preferred)"
  fi
  printf '%s' "$selected"
}

measure_hz() {
  local topic="$1"
  local timeout_secs="$2"
  timeout "$timeout_secs" stdbuf -oL ros2 topic hz "$topic" 2>/dev/null || true
}

if [[ ! -f "$ENV_SCRIPT" ]]; then
  echo "[INFO] env script: missing ($ENV_SCRIPT)"
  fail_missing "missing env script"
  echo "$RESULT"
  exit 0
fi
echo "[INFO] env script: $ENV_SCRIPT"
if ! source "$ENV_SCRIPT"; then
  fail_missing "failed to load env script"
  echo "$RESULT"
  exit 0
fi

print_section "pkg executables"
PKG_EXECUTABLES="$(timeout 5 ros2 pkg executables kt_visual_lidar_follow 2>/dev/null || true)"
printf '%s\n' "$PKG_EXECUTABLES"
if ! printf '%s\n' "$PKG_EXECUTABLES" | grep -F "kt_follow_controller_v4.py" >/dev/null 2>&1; then
  fail_missing "kt_follow_controller_v4.py not installed as package executable"
fi

print_section "tmux"
if tmux has-session -t "$SESSION" 2>/dev/null; then
  echo "[INFO] session present: $SESSION"
else
  fail_missing "tmux session missing: $SESSION"
fi
WINDOWS="$(tmux list-windows -t "$SESSION" -F '#W' 2>/dev/null || true)"
printf '%s\n' "$WINDOWS"
for required_window in core camera bear_det lidar web follow_v4; do
  if ! printf '%s\n' "$WINDOWS" | grep -Fx "$required_window" >/dev/null 2>&1; then
    if [[ "$required_window" == "web" ]]; then
      WEB_OK=0
      warn_partial "tmux window missing: web"
    else
      fail_missing "tmux window missing: $required_window"
    fi
  fi
done

print_section "nodes"
NODE_LIST="$(timeout 5 ros2 node list 2>/dev/null || true)"
printf '%s\n' "$NODE_LIST"

print_section "topics"
TOPIC_LIST="$(timeout 5 ros2 topic list 2>/dev/null || true)"
printf '%s\n' "$TOPIC_LIST"

ODOM_TOPIC="$(resolve_topic /odom /tianracer/odom)"
IMU_TOPIC="$(resolve_topic /imu /tianracer/imu)"
SCAN_TOPIC="$(resolve_topic /tianracer/scan /scan)"
IMAGE_TOPIC="$(resolve_topic /tianracer/camera/image_raw /image_raw)"
CAMERA_INFO_TOPIC="$(resolve_topic /tianracer/camera/camera_info /camera_info)"
ACK_TOPIC="$(resolve_topic /ackermann_cmd /tianracer/ackermann_cmd)"

print_section "resolved topics"
echo "[INFO] selected odom topic: ${ODOM_TOPIC:-missing}"
echo "[INFO] selected imu topic: ${IMU_TOPIC:-missing}"
echo "[INFO] selected scan topic: ${SCAN_TOPIC:-missing}"
echo "[INFO] selected image topic: ${IMAGE_TOPIC:-missing}"
echo "[INFO] selected camera_info topic: ${CAMERA_INFO_TOPIC:-missing}"
echo "[INFO] selected ackermann topic: ${ACK_TOPIC:-missing}"
if [[ -n "$ODOM_TOPIC" && "$ODOM_TOPIC" != "/odom" ]]; then
  echo "[WARN] using namespaced odom topic: $ODOM_TOPIC (preferred: /odom)"
fi
if [[ -n "$IMU_TOPIC" && "$IMU_TOPIC" != "/imu" ]]; then
  echo "[WARN] using namespaced imu topic: $IMU_TOPIC (preferred: /imu)"
fi
if [[ -n "$SCAN_TOPIC" && "$SCAN_TOPIC" != "/tianracer/scan" ]]; then
  echo "[WARN] using root scan topic: $SCAN_TOPIC (preferred: /tianracer/scan)"
fi
if [[ -n "$IMAGE_TOPIC" && "$IMAGE_TOPIC" != "/tianracer/camera/image_raw" ]]; then
  echo "[WARN] using root image topic: $IMAGE_TOPIC (preferred: /tianracer/camera/image_raw)"
fi
if [[ -n "$CAMERA_INFO_TOPIC" && "$CAMERA_INFO_TOPIC" != "/tianracer/camera/camera_info" ]]; then
  echo "[WARN] using root camera_info topic: $CAMERA_INFO_TOPIC (preferred: /tianracer/camera/camera_info)"
fi
if [[ -n "$ACK_TOPIC" && "$ACK_TOPIC" != "/ackermann_cmd" ]]; then
  echo "[WARN] using namespaced ackermann topic: $ACK_TOPIC (preferred: /ackermann_cmd)"
fi

print_section "topic info"
for topic_name in \
  /tianracer/odom /odom \
  /tianracer/imu /imu \
  /tianracer/scan /scan \
  /tianracer/camera/image_raw /image_raw \
  /tianracer/camera/camera_info /camera_info \
  /tianracer/ackermann_cmd /ackermann_cmd \
  /bear_detection/targets; do
  echo "--- $topic_name ---"
  BLOCK="$(topic_info_block "$topic_name")"
  if [[ -n "$BLOCK" ]]; then
    printf '%s\n' "$BLOCK"
  else
    echo "missing: $topic_name"
  fi
done

if [[ -z "$ODOM_TOPIC" ]]; then
  fail_missing "missing required topic: /odom (or /tianracer/odom)"
fi
if [[ -z "$IMU_TOPIC" ]]; then
  echo "[WARN] missing preferred IMU topic contract"
fi
if [[ -z "$SCAN_TOPIC" ]]; then
  fail_missing "missing required topic: /tianracer/scan (or /scan)"
fi
if ! topic_exists /bear_detection/targets; then
  fail_missing "missing required topic: /bear_detection/targets"
fi

if [[ -z "$IMAGE_TOPIC" ]]; then
  WEB_OK=0
  warn_partial "missing web topic: /tianracer/camera/image_raw"
fi
if [[ -z "$CAMERA_INFO_TOPIC" ]]; then
  WEB_OK=0
  warn_partial "missing web topic: /tianracer/camera/camera_info"
fi

print_section "topic hz"
for pair in \
  "${ODOM_TOPIC:-/odom} 8 required" \
  "${IMU_TOPIC:-/imu} 8 imu" \
  "${SCAN_TOPIC:-/tianracer/scan} 8 required" \
  "/bear_detection/targets 8 required" \
  "${IMAGE_TOPIC:-/tianracer/camera/image_raw} 8 web"; do
  set -- $pair
  echo "--- $1 ---"
  if ! topic_exists "$1"; then
    printf '%s\n' "missing: $1"
    if [[ "$3" == "required" ]]; then
      fail_missing "missing required topic for hz: $1"
    elif [[ "$3" == "imu" ]]; then
      echo "[WARN] imu topic missing for hz: $1"
    else
      WEB_OK=0
      warn_partial "missing web topic for hz: $1"
    fi
    continue
  fi
  HZ_OUTPUT="$(measure_hz "$1" "$2")"
  printf '%s\n' "$HZ_OUTPUT"
  if [[ "$3" == "required" && "$HZ_OUTPUT" != *"average rate:"* ]]; then
    fail_missing "no measurable rate for $1"
  fi
  if [[ "$3" == "imu" && "$HZ_OUTPUT" != *"average rate:"* ]]; then
    echo "[WARN] no measurable rate for $1"
  fi
  if [[ "$3" == "web" && "$HZ_OUTPUT" != *"average rate:"* ]]; then
    WEB_OK=0
    warn_partial "no measurable rate for $1"
  fi
done

print_section "ackermann contract"
ACK_BLOCK_ROOT="$(topic_info_block /ackermann_cmd)"
ACK_BLOCK_NS="$(topic_info_block /tianracer/ackermann_cmd)"
echo "--- /ackermann_cmd ---"
printf '%s\n' "${ACK_BLOCK_ROOT:-missing: /ackermann_cmd}"
echo "--- /tianracer/ackermann_cmd ---"
printf '%s\n' "${ACK_BLOCK_NS:-missing: /tianracer/ackermann_cmd}"

if [[ -z "$ACK_BLOCK_ROOT" && -z "$ACK_BLOCK_NS" ]]; then
  echo "[WARN] both ackermann topics absent — stack may not be running"
else
  ACK_ROOT_TYPE="$(timeout 3 ros2 topic type /ackermann_cmd 2>/dev/null || true)"
  ACK_NS_TYPE="$(timeout 3 ros2 topic type /tianracer/ackermann_cmd 2>/dev/null || true)"
  echo "[INFO] /ackermann_cmd type: ${ACK_ROOT_TYPE:-absent}"
  echo "[INFO] /tianracer/ackermann_cmd type: ${ACK_NS_TYPE:-absent}"
  if [[ -n "$ACK_ROOT_TYPE" && "$ACK_ROOT_TYPE" == "ackermann_msgs/msg/AckermannDrive" ]]; then
    echo "[INFO] base uses AckermannDrive (not AckermannDriveStamped)"
  fi

  ACK_ROOT_PUB_COUNT="$(printf '%s\n' "$ACK_BLOCK_ROOT" | awk -F: '/^Publisher count:/ {gsub(/ /,"",$2); print $2; exit}')"
  ACK_ROOT_SUB_COUNT="$(printf '%s\n' "$ACK_BLOCK_ROOT" | awk -F: '/^Subscription count:/ {gsub(/ /,"",$2); print $2; exit}')"
  ACK_NS_PUB_COUNT="$(printf '%s\n' "$ACK_BLOCK_NS" | awk -F: '/^Publisher count:/ {gsub(/ /,"",$2); print $2; exit}')"
  ACK_NS_SUB_COUNT="$(printf '%s\n' "$ACK_BLOCK_NS" | awk -F: '/^Subscription count:/ {gsub(/ /,"",$2); print $2; exit}')"
  echo "[INFO] /ackermann_cmd publisher count: ${ACK_ROOT_PUB_COUNT:-0}"
  echo "[INFO] /ackermann_cmd subscriber count: ${ACK_ROOT_SUB_COUNT:-0}"
  echo "[INFO] /tianracer/ackermann_cmd publisher count: ${ACK_NS_PUB_COUNT:-0}"
  echo "[INFO] /tianracer/ackermann_cmd subscriber count: ${ACK_NS_SUB_COUNT:-0}"

  if [[ -n "${ACK_ROOT_PUB_COUNT:-}" && "${ACK_ROOT_PUB_COUNT:-0}" != "0" ]]; then
    if printf '%s\n' "$ACK_BLOCK_ROOT" | grep -Eq 'Node name: /?kt_follow_controller_v4'; then
      echo "[INFO] /ackermann_cmd publisher includes kt_follow_controller_v4"
    else
      fail_unsafe "unknown /ackermann_cmd publisher"
    fi
  fi

  if [[ -n "${ACK_NS_PUB_COUNT:-}" && "${ACK_NS_PUB_COUNT:-0}" != "0" ]]; then
    if printf '%s\n' "$ACK_BLOCK_NS" | grep -Eq 'Node name: /?kt_follow_controller_v4'; then
      echo "[INFO] /tianracer/ackermann_cmd publisher includes kt_follow_controller_v4"
    else
      fail_unsafe "unknown /tianracer/ackermann_cmd publisher"
    fi
  fi

  if [[ -n "${ACK_ROOT_PUB_COUNT:-}" && "${ACK_ROOT_PUB_COUNT:-0}" != "0" ]] && \
     [[ -n "${ACK_NS_SUB_COUNT:-}" && "${ACK_NS_SUB_COUNT:-0}" != "0" ]]; then
    ACK_MISMATCH=1
    echo "[WARN] Ackermann topic contract mismatch: follow publishes on /ackermann_cmd but base subscribes on /tianracer/ackermann_cmd"
  fi
  if [[ -n "${ACK_NS_PUB_COUNT:-}" && "${ACK_NS_PUB_COUNT:-0}" != "0" ]] && \
     [[ -n "${ACK_ROOT_SUB_COUNT:-}" && "${ACK_ROOT_SUB_COUNT:-0}" != "0" ]]; then
    ACK_MISMATCH=1
    echo "[WARN] Ackermann topic contract mismatch: follow publishes on /tianracer/ackermann_cmd but base subscribes on /ackermann_cmd"
  fi
fi

print_section "legacy conflict checks"
if printf '%s\n' "$NODE_LIST" | grep -Eq '/(smooth_follow_controller|kt_smooth_follow_controller_v3)'; then
  fail_unsafe "legacy v3 node detected in ros2 node list"
fi
if printf '%s\n' "$NODE_LIST" | grep -Eq '/kt_visual_lidar_follow_node'; then
  fail_unsafe "legacy C++ node detected in ros2 node list"
fi
PS_OUTPUT="$(ps -ef | grep -E 'kt_smooth_follow_controller_v3|kt_visual_lidar_follow_node' | grep -v grep || true)"
printf '%s\n' "$PS_OUTPUT"
if [[ -n "$PS_OUTPUT" ]]; then
  if printf '%s\n' "$PS_OUTPUT" | grep -q 'kt_smooth_follow_controller_v3'; then
    fail_unsafe "legacy v3 process detected"
  fi
  if printf '%s\n' "$PS_OUTPUT" | grep -q 'kt_visual_lidar_follow_node'; then
    fail_unsafe "legacy C++ process detected"
  fi
fi

print_section "camera processes"
ps aux | grep -E 'usb_cam|ffmpeg|webrtc|camera' | grep -v grep || true

print_section "video device"
fuser /dev/video0 2>/dev/null || true

print_section "logs"
for log_file in /tmp/kt_core.log /tmp/kt_lidar.log /tmp/kt_follow_v4.log /tmp/kt_camera.log /tmp/kt_bear_det.log; do
  echo "--- tail $log_file ---"
  tail -n 20 "$log_file" 2>/dev/null || echo "missing log: $log_file"
done

FOLLOW_LOG_TEXT="$(tail -n 120 /tmp/kt_follow_v4.log 2>/dev/null || true)"
if printf '%s\n' "$FOLLOW_LOG_TEXT" | grep -Eiq 'enable_control[^[:alnum:]]*false|enable_control:=false|dry[- ]?run'; then
  DRY_RUN_CONFIRMED=1
  echo "[INFO] dry-run evidence found in /tmp/kt_follow_v4.log"
else
  warn_partial "unable to confirm follow_v4 dry-run from log"
fi

if [[ "$RESULT" == "PASS_SAFE_DRY_RUN" && "$DRY_RUN_CONFIRMED" -eq 0 ]]; then
  RESULT="WARN_PARTIAL"
fi

if [[ "$RESULT" == "PASS_SAFE_DRY_RUN" && "$WEB_OK" -eq 0 ]]; then
  RESULT="WARN_PARTIAL"
fi

print_section "summary"
echo "[INFO] ackermann mismatch detected: $ACK_MISMATCH"
echo "$RESULT"

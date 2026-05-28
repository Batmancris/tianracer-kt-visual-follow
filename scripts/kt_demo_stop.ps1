param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @'
run_pub_with_timeout() {
  local label="$1"
  shift
  echo "--- $label ---"
  if ! timeout -k 0.2s 1s "$@"; then
    echo "ignored: $label publish failed or timed out"
  fi
}

run_cmd_with_timeout() {
  local timeout_secs="$1"
  local label="$2"
  shift 2
  echo "--- $label ---"
  if ! timeout -k 0.2s "${timeout_secs}s" "$@"; then
    echo "ignored: $label check failed or timed out"
  fi
}

run_shell_check_with_timeout() {
  local timeout_secs="$1"
  local label="$2"
  shift 2
  echo "--- $label ---"
  if ! timeout -k 0.2s "${timeout_secs}s" bash -lc "$*"; then
    echo "ignored: $label check failed or timed out"
  fi
}

run_pub_with_timeout 'publish /kt_follow/mode OFF' \
  ros2 topic pub --qos-durability volatile --once /kt_follow/mode std_msgs/msg/String '{data: "OFF"}'

run_pub_with_timeout 'publish /ackermann_cmd stop' \
  ros2 topic pub --qos-durability volatile --once /ackermann_cmd ackermann_msgs/msg/AckermannDrive '{speed: 0.0, steering_angle: 0.0}'

tmux kill-session -t follow_v4 2>/dev/null || true;
tmux kill-session -t smooth_follow 2>/dev/null || true;
tmux kill-session -t kt_vlf 2>/dev/null || true;
tmux kill-session -t rosbridge 2>/dev/null || true;
tmux kill-session -t usb_cam 2>/dev/null || true;
tmux kill-session -t bear_det 2>/dev/null || true;
tmux kill-session -t ros2_lidar 2>/dev/null || true;
tmux kill-session -t core 2>/dev/null || true;
pkill -INT -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
sleep 0.2;
pkill -TERM -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -TERM -f 'python3 .*kt_follow_controller_v4.py' 2>/dev/null || true;
sleep 0.2;
pkill -KILL -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -KILL -f 'python3 .*kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -f kt_smooth_follow_controller 2>/dev/null || true;
pkill -f kt_visual_lidar_follow_node 2>/dev/null || true;
echo '--- remaining tmux ---'
tmux ls 2>/dev/null || true
run_shell_check_with_timeout 1 'remaining follow nodes' "ros2 node list | grep -E 'smooth_follow|kt_visual_lidar_follow|kt_follow_controller_v4' || true"
run_cmd_with_timeout 2 'ackermann' ros2 topic info /ackermann_cmd -v
'@

Write-Host "KT Demo Stop/Cleanup  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

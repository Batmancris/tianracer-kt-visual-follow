param(
    [string]$RobotIp = "10.217.185.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @'
READY_TO_FOLLOW=YES
BLOCKERS=()

topic_info() {
  local topic_name="$1"
  echo "--- $topic_name ---"
  ros2 topic info "$topic_name" -v 2>/dev/null || echo "missing: $topic_name"
}

topic_info_capture() {
  ros2 topic info "$1" -v 2>/dev/null || true
}

topic_count() {
  local topic_name="$1"
  local label="$2"
  local source_label="$label"
  local value
  if [ "$source_label" = "Subscriber" ]; then
    source_label="Subscription"
  fi
  value="$(ros2 topic info "$topic_name" -v 2>/dev/null | grep -m1 "^${source_label} count:" | cut -d: -f2- | xargs)"
  if [ -n "$value" ]; then
    echo "$topic_name $label count=$value"
  else
    echo "$topic_name $label count=missing"
  fi
}

topic_count_value() {
  local topic_name="$1"
  local label="$2"
  local source_label="$label"
  local block
  if [ "$source_label" = "Subscriber" ]; then
    source_label="Subscription"
  fi
  block="$(topic_info_capture "$topic_name")"
  echo "$block" | grep -m1 "^${source_label} count:" | cut -d: -f2- | xargs
}

topic_has_node() {
  local topic_name="$1"
  local direction="$2"
  local node_name="$3"
  local block
  local alt_name="$node_name"
  if [ "${node_name#/}" = "$node_name" ]; then
    alt_name="/$node_name"
  else
    alt_name="${node_name#/}"
  fi
  block="$(ros2 topic info "$topic_name" -v 2>/dev/null || true)"
  if echo "$block" | grep -Fq "Node name: $node_name" || echo "$block" | grep -Fq "Node name: $alt_name"; then
    echo "$topic_name $direction includes $node_name"
  else
    echo "$topic_name $direction missing $node_name"
  fi
}

topic_block_has_node() {
  local block="$1"
  local node_name="$2"
  local alt_name="$node_name"
  if [ "${node_name#/}" = "$node_name" ]; then
    alt_name="/$node_name"
  else
    alt_name="${node_name#/}"
  fi
  if echo "$block" | grep -Fq "Node name: $node_name" || echo "$block" | grep -Fq "Node name: $alt_name"; then
    return 0
  fi
  return 1
}

mark_ready_check() {
  local key="$1"
  local value="$2"
  local blocker="$3"
  echo "READY_CHECK ${key}=${value}"
  if [ "$value" != "YES" ]; then
    READY_TO_FOLLOW=NO
    BLOCKERS+=("$blocker")
  fi
}

measure_topic_hz() {
  local topic_name="$1"
  local log_file="$2"
  timeout 7 stdbuf -oL ros2 topic hz "$topic_name" 2>/dev/null | tee "$log_file" || true
}

hz_rate_value() {
  local log_file="$1"
  grep 'average rate:' "$log_file" | tail -n1 | sed -E 's/.*average rate:[[:space:]]*([0-9.]+).*/\1/'
}

hz_has_rate() {
  local log_file="$1"
  grep -q 'average rate:' "$log_file"
}

echo '--- tmux ---' &&
tmux ls 2>/dev/null || true
echo '--- nodes ---'
NODE_LIST="$(ros2 node list 2>/dev/null || true)"
printf '%s\n' "$NODE_LIST"
echo '--- readiness ---'
if tmux has-session -t core 2>/dev/null; then
  echo 'core tmux: running'
  mark_ready_check CORE_TMUX YES 'core tmux session missing'
else
  echo 'core tmux: missing'
  mark_ready_check CORE_TMUX NO 'core tmux session missing'
fi
if echo "$NODE_LIST" | grep -Fx '/tianracer_core' >/dev/null; then
  echo '/tianracer_core: present'
  mark_ready_check CORE_NODE YES '/tianracer_core node missing'
else
  echo '/tianracer_core: missing'
  mark_ready_check CORE_NODE NO '/tianracer_core node missing'
fi
echo '--- follow_v4 tmux ---'
if tmux has-session -t follow_v4 2>/dev/null; then
  echo 'follow_v4: running'
else
  echo 'follow_v4: missing'
fi
echo '--- follow_v4 node ---'
if ros2 node list 2>/dev/null | grep -Fx '/kt_follow_controller_v4' >/dev/null; then
  echo 'kt_follow_controller_v4: present'
else
  echo 'kt_follow_controller_v4: missing'
fi
echo '--- camera_ctrl tmux ---'
if tmux has-session -t camera_ctrl 2>/dev/null; then
  echo 'camera_ctrl: running'
else
  echo 'camera_ctrl: missing'
fi
echo '--- mjpeg_bridge tmux ---'
if tmux has-session -t mjpeg_bridge 2>/dev/null; then
  echo 'mjpeg_bridge: running'
else
  echo 'mjpeg_bridge: missing'
fi
echo '--- listeners ---'
ss -ltn '( sport = :8080 or sport = :9090 )' 2>/dev/null || netstat -ltn 2>/dev/null | grep -E ':8080|:9090' || true
echo '--- mjpeg url ---'
echo 'http://10.217.185.241:8080/stream.mjpg'
echo '--- mjpeg status ---'
echo 'http://10.217.185.241:8080/status.json'
curl -fsS http://10.217.185.241:8080/status.json || true
echo '--- ackermann ---'
topic_info /ackermann_cmd
ackermann_block="$(topic_info_capture /ackermann_cmd)"
topic_has_node /ackermann_cmd publishers 'kt_follow_controller_v4'
ackermann_pub_count="$(echo "$ackermann_block" | grep -m1 '^Publisher count:' | cut -d: -f2- | xargs)"
ackermann_sub_count="$(echo "$ackermann_block" | grep -m1 '^Subscription count:' | cut -d: -f2- | xargs)"
if [ "$ackermann_pub_count" = "1" ] && topic_block_has_node "$ackermann_block" 'kt_follow_controller_v4'; then
  echo '/ackermann_cmd publisher: kt_follow_controller_v4'
  mark_ready_check ACKERMANN_PUBLISHER YES "/ackermann_cmd publisher mismatch (count=${ackermann_pub_count:-missing})"
else
  echo "/ackermann_cmd publisher mismatch: count=${ackermann_pub_count:-missing}"
  mark_ready_check ACKERMANN_PUBLISHER NO "/ackermann_cmd publisher mismatch (count=${ackermann_pub_count:-missing})"
fi
if [ "$ackermann_sub_count" = "1" ] && topic_block_has_node "$ackermann_block" 'tianracer_core'; then
  echo '/ackermann_cmd subscriber: tianracer_core'
  mark_ready_check ACKERMANN_SUBSCRIBER YES "/ackermann_cmd subscriber mismatch (count=${ackermann_sub_count:-missing})"
else
  echo "/ackermann_cmd subscriber mismatch: count=${ackermann_sub_count:-missing}"
  mark_ready_check ACKERMANN_SUBSCRIBER NO "/ackermann_cmd subscriber mismatch (count=${ackermann_sub_count:-missing})"
fi
echo '--- camera control ---'
ros2 topic info /kt_camera/control -v || true
echo '--- camera status ---'
ros2 topic info /kt_camera/status -v || true
echo '--- follow status ---'
topic_info /kt_follow/status
topic_count /kt_follow/status Publisher
follow_status_pub_count="$(topic_count_value /kt_follow/status Publisher)"
if [ "$follow_status_pub_count" = "1" ]; then
  mark_ready_check FOLLOW_STATUS_PUBLISHER YES '/kt_follow/status publisher count is not 1'
else
  mark_ready_check FOLLOW_STATUS_PUBLISHER NO "/kt_follow/status publisher count is ${follow_status_pub_count:-missing}"
fi
echo '--- follow mode ---'
topic_info /kt_follow/mode
topic_count /kt_follow/mode Subscriber
follow_mode_sub_count="$(topic_count_value /kt_follow/mode Subscriber)"
if [ "$follow_mode_sub_count" = "1" ]; then
  mark_ready_check FOLLOW_MODE_SUBSCRIBER YES '/kt_follow/mode subscriber count is not 1'
else
  mark_ready_check FOLLOW_MODE_SUBSCRIBER NO "/kt_follow/mode subscriber count is ${follow_mode_sub_count:-missing}"
fi
echo '--- follow tuning ---'
topic_info /kt_follow/tuning
topic_count /kt_follow/tuning Subscriber
echo '--- scan ---'
topic_info /tianracer/scan
topic_has_node /tianracer/scan subscribers 'kt_follow_controller_v4'
measure_topic_hz /tianracer/scan /tmp/kt_status_scan_hz.log
if hz_has_rate /tmp/kt_status_scan_hz.log; then
  echo "/tianracer/scan hz=$(hz_rate_value /tmp/kt_status_scan_hz.log)"
  mark_ready_check SCAN_HZ YES '/tianracer/scan has no measurable frequency'
else
  mark_ready_check SCAN_HZ NO '/tianracer/scan has no measurable frequency'
fi
echo '--- targets ---'
topic_info /bear_detection/targets
topic_has_node /bear_detection/targets subscribers 'kt_follow_controller_v4'
topic_has_node /bear_detection/targets subscribers 'rosbridge_websocket'
measure_topic_hz /bear_detection/targets /tmp/kt_status_targets_hz.log
if hz_has_rate /tmp/kt_status_targets_hz.log; then
  echo "/bear_detection/targets hz=$(hz_rate_value /tmp/kt_status_targets_hz.log)"
  mark_ready_check TARGETS_HZ YES '/bear_detection/targets has no measurable frequency'
else
  mark_ready_check TARGETS_HZ NO '/bear_detection/targets has no measurable frequency'
fi
measure_topic_hz /kt_follow/status /tmp/kt_status_follow_status_hz.log
echo '--- ready summary ---'
echo "READY_TO_FOLLOW: $READY_TO_FOLLOW"
if [ "$READY_TO_FOLLOW" = "NO" ]; then
  for blocker in "${BLOCKERS[@]}"; do
    echo "READY_BLOCKER: $blocker"
  done
fi
'@

Write-Host "KT Demo Status  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

param(
    [string]$RobotIp = "10.217.185.241"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
echo '--- tmux ---' &&
tmux ls 2>/dev/null || true &&
echo '--- nodes ---' &&
ros2 node list || true &&
echo '--- topics ---' &&
ros2 topic list | grep -E 'camera|image|bear|scan|ackermann|mode|odom|imu' || true &&
echo '--- ackermann ---' &&
ros2 topic info /ackermann_cmd -v || true &&
echo '--- follow_v4 file ---' &&
echo 'board deployment target only; not a repo-local path' &&
if [ -f ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py ]; then
  ls -l ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py
else
  echo 'MISSING deployment target: ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py'
fi &&
echo '--- scan ---' &&
ros2 topic info /tianracer/scan -v || true &&
timeout 5 ros2 topic hz /tianracer/scan || true &&
echo '--- targets ---' &&
ros2 topic info /bear_detection/targets -v || true &&
timeout 5 ros2 topic hz /bear_detection/targets || true &&
echo '--- forbidden ---' &&
ros2 node list | grep -E 'joy|teleop|navigation|nav2|smooth_follow|kt_visual_lidar_follow' || true
"@

Write-Host "KT Demo Preflight  sunrise@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote

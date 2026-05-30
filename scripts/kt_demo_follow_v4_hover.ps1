param(
    [string]$RobotIp = "10.217.185.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
tmux kill-session -t follow_v4 2>/dev/null || true;
tmux new-session -d -s follow_v4 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py --enable-control true --target-distance-m 1.0 --stop-distance-m 1.0 --full-speed-distance-m 1.6 --max-speed 0.25 --max-steering-angle 0.18 2>&1 | tee /tmp/follow_v4.log; sleep 3600"' &&
sleep 3 &&
tail -80 /tmp/follow_v4.log
"@

Write-Host "KT Demo Start follow_v4 hover profile  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

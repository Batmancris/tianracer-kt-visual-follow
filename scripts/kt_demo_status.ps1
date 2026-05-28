param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
echo '--- tmux ---' &&
tmux ls 2>/dev/null || true &&
echo '--- nodes ---' &&
ros2 node list || true &&
echo '--- ackermann ---' &&
ros2 topic info /ackermann_cmd -v || true &&
echo '--- scan ---' &&
ros2 topic info /tianracer/scan -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/scan 2>/dev/null || true &&
echo '--- targets ---' &&
ros2 topic info /bear_detection/targets -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /bear_detection/targets 2>/dev/null || true
"@

Write-Host "KT Demo Status  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

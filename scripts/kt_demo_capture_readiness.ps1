param(
    [string]$RobotIp = "10.217.185.241"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-readiness-$timestamp.txt"
$outDir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$remote = @"
echo '--- core ---' &&
ros2 node list | grep -E 'tianracer_core|tianbot_core' || true &&
echo '--- ackermann ---' &&
ros2 topic info /ackermann_cmd -v || true &&
echo '--- camera ---' &&
ros2 topic list | grep image || true &&
ros2 topic info /tianracer/camera/image_compressed -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/camera/image_compressed 2>/dev/null || true &&
echo '--- targets ---' &&
ros2 topic info /bear_detection/targets -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /bear_detection/targets 2>/dev/null || true &&
echo '--- scan_raw ---' &&
ros2 topic info /tianracer/scan_raw -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/scan_raw 2>/dev/null || true &&
echo '--- scan ---' &&
ros2 topic info /tianracer/scan -v || true &&
timeout 7 stdbuf -oL ros2 topic hz /tianracer/scan 2>/dev/null || true &&
echo '--- forbidden ---' &&
ros2 node list | grep -E 'joy|teleop|navigation|nav2|smooth_follow|kt_visual_lidar_follow' || true &&
echo '--- follow logs ---' &&
tail -40 /tmp/follow_v4.log 2>/dev/null || true &&
tail -40 /tmp/follow_v4_ground.log 2>/dev/null || true
"@

Write-Host "KT Demo Capture Readiness  sunrise@$RobotIp" -ForegroundColor Cyan
$result = Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote
$result | Tee-Object -FilePath $outFile
Write-Host "Saved readiness evidence to $outFile" -ForegroundColor Green

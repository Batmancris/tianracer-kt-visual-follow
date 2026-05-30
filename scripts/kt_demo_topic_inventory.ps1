param(
    [string]$RobotIp = "10.217.185.241"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
echo '--- nodes ---' &&
ros2 node list | sort || true &&
echo '--- topic list ---' &&
ros2 topic list | sort || true &&
echo '--- image topics ---' &&
ros2 topic list | grep image || true &&
echo '--- scan topics ---' &&
ros2 topic list | grep scan || true &&
echo '--- mode topics ---' &&
ros2 topic list | grep kt_follow || true &&
echo '--- camera node info ---' &&
ros2 node info /tianracer/camera || true &&
echo '--- bear_detection topic info ---' &&
ros2 topic info /bear_detection/targets -v || true &&
echo '--- scan topic info ---' &&
ros2 topic info /tianracer/scan -v || true &&
echo '--- scan_raw topic info ---' &&
ros2 topic info /tianracer/scan_raw -v || true
"@

Write-Host "KT Demo Topic Inventory  sunrise@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote

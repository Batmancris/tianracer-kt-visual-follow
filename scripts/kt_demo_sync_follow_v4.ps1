param(
    [string]$RobotIp = "10.217.185.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$localController = Join-Path $RepoRoot "kt_visual_lidar_follow\scripts\kt_follow_controller_v4.py"
$localCameraBridge = Join-Path $RepoRoot "kt_visual_lidar_follow\scripts\kt_camera_control_bridge.py"
$localMjpegBridge = Join-Path $RepoRoot "kt_visual_lidar_follow\scripts\kt_mjpeg_bridge.py"
$localLaunch = Join-Path $RepoRoot "kt_visual_lidar_follow\launch\kt_follow_controller_v4.launch.py"

if (-not (Test-Path -LiteralPath $localController)) {
    throw "Missing local controller: $localController"
}

if (-not (Test-Path -LiteralPath $localLaunch)) {
    throw "Missing local launch file: $localLaunch"
}

if (-not (Test-Path -LiteralPath $localCameraBridge)) {
    throw "Missing local camera bridge: $localCameraBridge"
}

if (-not (Test-Path -LiteralPath $localMjpegBridge)) {
    throw "Missing local MJPEG bridge: $localMjpegBridge"
}

Write-Host "KT Demo Sync follow_v4 assets  $RobotUser@$RobotIp" -ForegroundColor Cyan
ssh "$RobotUser@$RobotIp" "mkdir -p ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch"
scp $localController "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py"
scp $localCameraBridge "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py"
scp $localMjpegBridge "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py"
scp $localLaunch "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"
Write-Host "Synced files:" -ForegroundColor Yellow
Write-Host "  kt_follow_controller_v4.py"
Write-Host "  kt_camera_control_bridge.py"
Write-Host "  kt_mjpeg_bridge.py"
Write-Host "  kt_follow_controller_v4.launch.py"
ssh "$RobotUser@$RobotIp" "chmod +x ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py && ls -l ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"

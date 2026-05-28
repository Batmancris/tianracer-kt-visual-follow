param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$localController = Join-Path $RepoRoot "kt_visual_lidar_follow\scripts\kt_follow_controller_v4.py"
$localLaunch = Join-Path $RepoRoot "kt_visual_lidar_follow\launch\kt_follow_controller_v4.launch.py"

if (-not (Test-Path -LiteralPath $localController)) {
    throw "Missing local controller: $localController"
}

if (-not (Test-Path -LiteralPath $localLaunch)) {
    throw "Missing local launch file: $localLaunch"
}

Write-Host "KT Demo Sync follow_v4 assets  $RobotUser@$RobotIp" -ForegroundColor Cyan
ssh "$RobotUser@$RobotIp" "mkdir -p ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch"
scp $localController "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py"
scp $localLaunch "${RobotUser}@${RobotIp}:~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"
ssh "$RobotUser@$RobotIp" "chmod +x ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py && ls -l ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"

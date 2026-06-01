param(
    [string]$RobotIp,
    [string]$RobotUser,
    [int]$RosbridgePort,
    [int]$MjpegPort,
    [string]$RemoteWorkspace,
    [string]$VideoDevice,
    [string]$LidarDevice
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_config.ps1"
$config = Get-KtRobotConfig -RobotIp $RobotIp -RobotUser $RobotUser -RosbridgePort $RosbridgePort -MjpegPort $MjpegPort -RemoteWorkspace $RemoteWorkspace -VideoDevice $VideoDevice -LidarDevice $LidarDevice

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

$remoteWorkspace = $config.RemoteWorkspace

Write-Host "KT Demo Sync follow_v4 assets  $($config.RobotUser)@$($config.RobotIp)" -ForegroundColor Cyan
ssh "$($config.RobotUser)@$($config.RobotIp)" "mkdir -p $remoteWorkspace/src/kt_visual_lidar_follow/scripts $remoteWorkspace/src/kt_visual_lidar_follow/launch"
scp $localController "$($config.RobotUser)@$($config.RobotIp):$remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py"
scp $localCameraBridge "$($config.RobotUser)@$($config.RobotIp):$remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py"
scp $localMjpegBridge "$($config.RobotUser)@$($config.RobotIp):$remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py"
scp $localLaunch "$($config.RobotUser)@$($config.RobotIp):$remoteWorkspace/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"
Write-Host "Synced files:" -ForegroundColor Yellow
Write-Host "  kt_follow_controller_v4.py"
Write-Host "  kt_camera_control_bridge.py"
Write-Host "  kt_mjpeg_bridge.py"
Write-Host "  kt_follow_controller_v4.launch.py"
ssh "$($config.RobotUser)@$($config.RobotIp)" "chmod +x $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py && ls -l $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py $remoteWorkspace/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py $remoteWorkspace/src/kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py"

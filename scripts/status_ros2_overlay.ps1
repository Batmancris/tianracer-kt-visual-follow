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

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KT Demo Prod Status" -ForegroundColor Cyan
Write-Host "  Robot: $($config.RobotUser)@$($config.RobotIp)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kt_demo_status.ps1" -RobotIp $config.RobotIp -RobotUser $config.RobotUser -RosbridgePort $config.RosbridgePort -MjpegPort $config.MjpegPort -RemoteWorkspace $config.RemoteWorkspace -VideoDevice $config.VideoDevice -LidarDevice $config.LidarDevice

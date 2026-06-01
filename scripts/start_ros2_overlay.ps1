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
Write-Host "  KT Demo Prod Bringup" -ForegroundColor Cyan
Write-Host "  Robot: $($config.RobotUser)@$($config.RobotIp)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kt_demo_bringup.ps1" -RobotIp $config.RobotIp -RobotUser $config.RobotUser -RosbridgePort $config.RosbridgePort -MjpegPort $config.MjpegPort -RemoteWorkspace $config.RemoteWorkspace -VideoDevice $config.VideoDevice -LidarDevice $config.LidarDevice

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Recommended next steps:" -ForegroundColor Green
Write-Host "  1. Run .\scripts\kt_demo_preflight.ps1" -ForegroundColor Yellow
Write-Host "  2. Open .\tools\bear_overlay_prod.html in browser" -ForegroundColor Yellow
Write-Host "  Rosbridge: ws://$($config.RobotIp):$($config.RosbridgePort)" -ForegroundColor Yellow
Write-Host "  Image Topic: /tianracer/camera/image_compressed" -ForegroundColor Yellow
Write-Host "  Target Topic: /bear_detection/targets" -ForegroundColor Yellow
Write-Host "  Mode Topic: /kt_follow/mode" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

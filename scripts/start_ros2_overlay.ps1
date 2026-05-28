param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KT Demo Prod Bringup" -ForegroundColor Cyan
Write-Host "  Robot: $RobotUser@$RobotIp" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kt_demo_bringup.ps1" -RobotIp $RobotIp -RobotUser $RobotUser

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Recommended next steps:" -ForegroundColor Green
Write-Host "  1. Open .\tools\bear_overlay_prod.html in browser" -ForegroundColor Yellow
Write-Host "  Rosbridge: ws://$RobotIp`:9090" -ForegroundColor Yellow
Write-Host "  Image Topic: /tianracer/camera/image_compressed" -ForegroundColor Yellow
Write-Host "  Target Topic: /bear_detection/targets" -ForegroundColor Yellow
Write-Host "  Mode Topic: /kt_follow/mode" -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

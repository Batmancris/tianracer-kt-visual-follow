param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KT Demo Prod Status" -ForegroundColor Cyan
Write-Host "  Robot: $RobotUser@$RobotIp" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kt_demo_status.ps1" -RobotIp $RobotIp -RobotUser $RobotUser

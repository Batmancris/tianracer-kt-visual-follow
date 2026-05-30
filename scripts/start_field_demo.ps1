param(
    [string]$RobotIp = "10.217.185.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  KT Field Demo Bringup" -ForegroundColor Cyan
Write-Host "  Robot: $RobotUser@$RobotIp" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

& "$PSScriptRoot\kt_demo_bringup.ps1" `
    -RobotIp $RobotIp `
    -RobotUser $RobotUser `
    -StartFollowV4 `
    -TargetDistanceM 0.50 `
    -StopDistanceM 0.45 `
    -FullSpeedDistanceM 1.20 `
    -MaxSpeed 0.35 `
    -MaxSteeringAngle 0.30

$statusLines = @(& "$PSScriptRoot\kt_demo_status.ps1" -RobotIp $RobotIp -RobotUser $RobotUser 2>&1 | Tee-Object -Variable rawStatusLines)
$ready = Get-KtReadySummary -Lines $statusLines

Write-Host ""
if (-not $ready.Ready) {
    Write-Host "========================================" -ForegroundColor Red
    Write-Host "  FAIL: chain is not READY_TO_FOLLOW." -ForegroundColor Red
    foreach ($blocker in $ready.Blockers) {
        Write-Host "  BLOCKER: $blocker" -ForegroundColor Yellow
    }
    Write-Host "  follow_v4 may be running, but it must remain OFF." -ForegroundColor Yellow
    Write-Host "========================================" -ForegroundColor Red
    throw "READY_TO_FOLLOW=NO"
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Field demo chain started." -ForegroundColor Green
Write-Host "  READY_TO_FOLLOW: YES" -ForegroundColor Green
Write-Host "  follow_v4 is included and forced back to OFF at bringup." -ForegroundColor Yellow
Write-Host "  Open .\tools\bear_overlay_prod.html for auto-connect UI." -ForegroundColor Yellow
Write-Host "========================================" -ForegroundColor Green

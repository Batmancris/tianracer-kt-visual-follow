param(
    [string]$RobotIp = "10.217.185.241",
    [ValidateRange(3, 5)]
    [int]$FollowSeconds = 5,
    [switch]$ExecuteGroundRun
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

if (-not $ExecuteGroundRun) {
    throw "Refusing to run ground FOLLOW->OFF cycle without -ExecuteGroundRun. Confirm hover passed, ground gate passed, and a human spotter is ready."
}

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-ground-$timestamp.txt"
$outDir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$remote = @"
echo '--- send FOLLOW ---' &&
timeout 10 ros2 topic pub --once /kt_follow/mode std_msgs/msg/String "{data: 'FOLLOW'}" &&
sleep $FollowSeconds &&
echo '--- send OFF ---' &&
timeout 10 ros2 topic pub --once /kt_follow/mode std_msgs/msg/String "{data: 'OFF'}" &&
sleep 1 &&
echo '--- follow_v4_ground.log ---' &&
tail -100 /tmp/follow_v4_ground.log || true
"@

Write-Host "KT Demo Ground Cycle  sunrise@$RobotIp" -ForegroundColor Cyan
$result = Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote
$result | Tee-Object -FilePath $outFile
Write-Host "Saved ground evidence to $outFile" -ForegroundColor Green

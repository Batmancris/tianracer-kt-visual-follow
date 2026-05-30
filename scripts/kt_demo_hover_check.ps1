param(
    [string]$RobotIp = "10.217.185.241"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$timestamp = Get-Date -Format "yyyyMMdd-HHmmss"
$outFile = Join-Path $PSScriptRoot "..\reports\artifacts\kt-demo-hover-$timestamp.txt"
$outDir = Split-Path -Parent $outFile
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

$remote = @"
echo '--- send FOLLOW ---' &&
timeout 10 ros2 topic pub --once /kt_follow/mode std_msgs/msg/String "{data: 'FOLLOW'}" &&
sleep 3 &&
echo '--- follow log after FOLLOW ---' &&
tail -80 /tmp/follow_v4.log || true &&
echo '--- ackermann info ---' &&
ros2 topic info /ackermann_cmd -v || true &&
echo '--- send MANUAL ---' &&
timeout 10 ros2 topic pub --once /kt_follow/mode std_msgs/msg/String "{data: 'MANUAL'}" &&
sleep 2 &&
tail -40 /tmp/follow_v4.log || true &&
echo '--- send OFF ---' &&
timeout 10 ros2 topic pub --once /kt_follow/mode std_msgs/msg/String "{data: 'OFF'}" &&
sleep 2 &&
tail -40 /tmp/follow_v4.log || true
"@

Write-Host "KT Demo Hover Check  sunrise@$RobotIp" -ForegroundColor Cyan
$result = Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote
$result | Tee-Object -FilePath $outFile
Write-Host "Saved hover evidence to $outFile" -ForegroundColor Green

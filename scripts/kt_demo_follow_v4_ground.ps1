param(
    [string]$RobotIp = "10.217.185.241",
    [switch]$Armed
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

if (-not $Armed) {
    throw "Refusing to start ground profile without -Armed. Run kt_demo_ground_gate.ps1 first, confirm clear ground and a human spotter, then retry with -Armed."
}

$remote = @"
tmux kill-session -t follow_v4 2>/dev/null || true;
tmux new-session -d -s follow_v4 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py --enable-control true --scan-topic /tianracer/scan --target-distance-m 0.5 --restart-distance-m 0.7 --stop-distance-m 0.5 --full-speed-distance-m 1.0 --max-speed 0.50 --slow-speed-mps 0.35 --fast-speed-mps 0.50 --min-effective-speed-mps 0.30 --stop-decel-mps2 0.80 --stop-margin-m 0.08 --max-steering-angle 0.12 --max-accel 0.25 --max-decel 0.80 2>&1 | tee /tmp/follow_v4_ground.log; sleep 3600"' &&
sleep 3 &&
tail -80 /tmp/follow_v4_ground.log
"@

Write-Host "KT Demo Start follow_v4 ground profile  sunrise@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RemoteBody $remote

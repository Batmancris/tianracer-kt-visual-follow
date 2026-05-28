param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
tmux kill-session -t follow_v4 2>/dev/null || true;
tmux kill-session -t smooth_follow 2>/dev/null || true;
tmux kill-session -t kt_vlf 2>/dev/null || true;
tmux kill-session -t rosbridge 2>/dev/null || true;
tmux kill-session -t usb_cam 2>/dev/null || true;
tmux kill-session -t bear_det 2>/dev/null || true;
tmux kill-session -t ros2_lidar 2>/dev/null || true;
tmux kill-session -t core 2>/dev/null || true;
pkill -INT -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
sleep 1;
pkill -TERM -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -TERM -f 'python3 .*kt_follow_controller_v4.py' 2>/dev/null || true;
sleep 1;
pkill -KILL -f 'kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -KILL -f 'python3 .*kt_follow_controller_v4.py' 2>/dev/null || true;
pkill -f kt_smooth_follow_controller 2>/dev/null || true;
pkill -f kt_visual_lidar_follow_node 2>/dev/null || true;
ros2 topic pub --qos-durability volatile --times 20 /ackermann_cmd ackermann_msgs/msg/AckermannDrive '{speed: 0.0, steering_angle: 0.0}' --rate 20 &&
sleep 2 &&
echo '--- remaining tmux ---' &&
tmux ls 2>/dev/null || true &&
echo '--- remaining follow nodes ---' &&
ros2 node list | grep -E 'smooth_follow|kt_visual_lidar_follow|kt_follow_controller_v4' || true &&
echo '--- ackermann ---' &&
ros2 topic info /ackermann_cmd -v || true
"@

Write-Host "KT Demo Stop/Cleanup  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

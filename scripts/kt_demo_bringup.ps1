param(
    [string]$RobotIp = "10.129.90.241",
    [string]$RobotUser = "sunrise"
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_demo_lib.ps1"

$remote = @"
tmux kill-session -t core 2>/dev/null || true;
tmux kill-session -t usb_cam 2>/dev/null || true;
tmux kill-session -t camera_ctrl 2>/dev/null || true;
tmux kill-session -t bear_det 2>/dev/null || true;
tmux kill-session -t ros2_lidar 2>/dev/null || true;
tmux kill-session -t rosbridge 2>/dev/null || true;
tmux new-session -d -s core 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; ros2 launch tianracer_core tianracer_core.launch.py 2>&1 | tee /tmp/core.log; sleep 3600"' &&
sleep 5 &&
tmux new-session -d -s usb_cam 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=camera -r __ns:=/tianracer -p video_device:=/dev/video0 -p pixel_format:=mjpeg2rgb -p image_width:=640 -p image_height:=480 -p framerate:=30.0 -p io_method:=mmap -p camera_name:=tianracer_camera -p frame_id:=tianracer/camera_link -r image_raw:=camera/image_raw -r image_raw/compressed:=camera/image_compressed -r camera_info:=camera/camera_info 2>&1 | tee /tmp/usb_cam.log; sleep 3600"' &&
sleep 5 &&
tmux new-session -d -s camera_ctrl 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py 2>&1 | tee /tmp/camera_ctrl.log; sleep 3600"' &&
sleep 3 &&
tmux new-session -d -s bear_det 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; ros2 launch kt_bear_detection kt_bear_detection.launch.py 2>&1 | tee /tmp/bear_det.log; sleep 3600"' &&
sleep 8 &&
tmux new-session -d -s ros2_lidar 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; export TIANRACER_LIDAR=LDS_E110; export TIANRACER_LIDAR_PORT=/dev/tianbot_lidar; ros2 launch tianracer_bringup lidar.launch.py namespace:=tianracer 2>&1 | tee /tmp/ros2_lidar.log; sleep 3600"' &&
sleep 8 &&
tmux new-session -d -s rosbridge 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source ~/tianracer_ros2_ws/install/setup.bash >/dev/null 2>&1 || true; ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=9090 2>&1 | tee /tmp/rosbridge.log; sleep 3600"' &&
sleep 5 &&
echo '--- core ---' && tail -40 /tmp/core.log &&
echo '--- usb_cam ---' && tail -20 /tmp/usb_cam.log &&
echo '--- camera_ctrl ---' && tail -20 /tmp/camera_ctrl.log &&
echo '--- bear_det ---' && tail -20 /tmp/bear_det.log &&
echo '--- lidar ---' && tail -20 /tmp/ros2_lidar.log &&
echo '--- rosbridge ---' && tail -20 /tmp/rosbridge.log
"@

Write-Host "KT Demo Bringup  $RobotUser@$RobotIp" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $RobotIp -RobotUser $RobotUser -RemoteBody $remote

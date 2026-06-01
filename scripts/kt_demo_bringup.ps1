param(
    [string]$RobotIp,
    [string]$RobotUser,
    [int]$RosbridgePort,
    [int]$MjpegPort,
    [string]$RemoteWorkspace,
    [string]$VideoDevice,
    [string]$LidarDevice,
    [switch]$StartFollowV4,
    [double]$TargetDistanceM = 0.50,
    [double]$StopDistanceM = 0.45,
    [double]$FullSpeedDistanceM = 1.20,
    [double]$MaxSpeed = 0.35,
    [double]$MaxSteeringAngle = 0.30
)

$ErrorActionPreference = "Stop"
. "$PSScriptRoot\kt_config.ps1"
. "$PSScriptRoot\kt_demo_lib.ps1"
$config = Get-KtRobotConfig -RobotIp $RobotIp -RobotUser $RobotUser -RosbridgePort $RosbridgePort -MjpegPort $MjpegPort -RemoteWorkspace $RemoteWorkspace -VideoDevice $VideoDevice -LidarDevice $LidarDevice

$followRemote = "true"
if ($StartFollowV4) {
    $followRemote = @"
tmux kill-session -t follow_v4 2>/dev/null || true;
tmux new-session -d -s follow_v4 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; python3 $($config.RemoteWorkspace)/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py --enable-control true --target-distance-m $TargetDistanceM --stop-distance-m $StopDistanceM --full-speed-distance-m $FullSpeedDistanceM --max-speed $MaxSpeed --max-steering-angle $MaxSteeringAngle 2>&1 | tee /tmp/follow_v4.log; sleep 3600"' &&
sleep 3 &&
echo '--- follow_v4 ---' && tail -40 /tmp/follow_v4.log &&
echo '--- follow_v4 mode guard ---' &&
timeout -k 0.2s 1.5s ros2 topic pub --qos-durability volatile --once /kt_follow/mode std_msgs/msg/String '{data: "OFF"}' || true &&
sleep 1
"@
}

$remote = @"
tmux kill-session -t core 2>/dev/null || true;
tmux kill-session -t usb_cam 2>/dev/null || true;
tmux kill-session -t camera_ctrl 2>/dev/null || true;
tmux kill-session -t bear_det 2>/dev/null || true;
tmux kill-session -t ros2_lidar 2>/dev/null || true;
tmux kill-session -t rosbridge 2>/dev/null || true;
tmux kill-session -t mjpeg_bridge 2>/dev/null || true;
tmux kill-session -t follow_v4 2>/dev/null || true;
tmux new-session -d -s core 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; ros2 launch tianracer_core tianracer_core.launch.py 2>&1 | tee /tmp/core.log; sleep 3600"' &&
sleep 5 &&
tmux new-session -d -s usb_cam 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; ros2 run usb_cam usb_cam_node_exe --ros-args -r __node:=camera -r __ns:=/tianracer -p video_device:=$($config.VideoDevice) -p pixel_format:=mjpeg2rgb -p image_width:=640 -p image_height:=480 -p framerate:=30.0 -p io_method:=mmap -p camera_name:=tianracer_camera -p frame_id:=tianracer/camera_link -r image_raw:=camera/image_raw -r image_raw/compressed:=camera/image_compressed -r camera_info:=camera/camera_info 2>&1 | tee /tmp/usb_cam.log; sleep 3600"' &&
sleep 3 &&
tmux new-session -d -s mjpeg_bridge 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; python3 $($config.RemoteWorkspace)/src/kt_visual_lidar_follow/scripts/kt_mjpeg_bridge.py --port $($config.MjpegPort) --fps 8 2>&1 | tee /tmp/mjpeg_bridge.log; sleep 3600"' &&
sleep 5 &&
tmux new-session -d -s camera_ctrl 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; python3 $($config.RemoteWorkspace)/src/kt_visual_lidar_follow/scripts/kt_camera_control_bridge.py 2>&1 | tee /tmp/camera_ctrl.log; sleep 3600"' &&
sleep 3 &&
tmux new-session -d -s bear_det 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; ros2 launch kt_bear_detection kt_bear_detection.launch.py 2>&1 | tee /tmp/bear_det.log; sleep 3600"' &&
sleep 8 &&
tmux new-session -d -s ros2_lidar 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; export TIANRACER_LIDAR=LDS_E110; export TIANRACER_LIDAR_PORT=$($config.LidarDevice); ros2 launch tianracer_bringup lidar.launch.py namespace:=tianracer 2>&1 | tee /tmp/ros2_lidar.log; sleep 3600"' &&
sleep 8 &&
tmux new-session -d -s rosbridge 'bash -lc "source ~/.bashrc >/dev/null 2>&1 || true; command -v ros2_setup >/dev/null 2>&1 && ros2_setup >/dev/null 2>&1 || true; source $($config.RemoteWorkspace)/install/setup.bash >/dev/null 2>&1 || true; ros2 launch rosbridge_server rosbridge_websocket_launch.xml port:=$($config.RosbridgePort) 2>&1 | tee /tmp/rosbridge.log; sleep 3600"' &&
sleep 5 &&
echo '--- core ---' && tail -40 /tmp/core.log &&
echo '--- usb_cam ---' && tail -20 /tmp/usb_cam.log &&
echo '--- mjpeg_bridge ---' && tail -20 /tmp/mjpeg_bridge.log &&
echo '--- camera_ctrl ---' && tail -20 /tmp/camera_ctrl.log &&
echo '--- bear_det ---' && tail -20 /tmp/bear_det.log &&
echo '--- lidar ---' && tail -20 /tmp/ros2_lidar.log &&
echo '--- rosbridge ---' && tail -20 /tmp/rosbridge.log &&
$followRemote
"@

Write-Host "KT Demo Bringup  $($config.RobotUser)@$($config.RobotIp)" -ForegroundColor Cyan
Invoke-KtRobotBash -RobotIp $config.RobotIp -RobotUser $config.RobotUser -RemoteWorkspace $config.RemoteWorkspace -RemoteBody $remote

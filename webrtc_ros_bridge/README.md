# WebRTC ROS Bridge

高性能WebRTC媒体流到ROS1/ROS2的桥接功能包。

## 功能特性

- ✅ 支持ROS1 (Noetic) 和 ROS2 (Foxy/Humble/Iron)
- ✅ 通过WHEP协议订阅WebRTC媒体流
- ✅ 视频流发布到 `sensor_msgs/Image` 和 `sensor_msgs/CompressedImage`
- ✅ 音频流发布支持
- ✅ 高内聚、低耦合的模块化设计
- ✅ 异步处理，低延迟
- ✅ 灵活的配置系统

## 系统架构

```
WebRTC Server (WHEP) → WebRTC Client → Media Decoder → ROS Publisher
```

### 模块说明

- **core/webrtc_client.py**: WebRTC客户端封装，处理WHEP协议
- **core/media_decoder.py**: 媒体解码器，转换帧格式
- **core/stream_manager.py**: 流管理器，协调各组件
- **ros1/ros1_publisher.py**: ROS1发布节点
- **ros2/ros2_publisher.py**: ROS2发布节点

## 依赖安装

### 系统依赖

```bash
# Ubuntu 20.04/22.04
sudo apt-get update
sudo apt-get install -y \
    python3-pip \
    python3-opencv \
    libavformat-dev \
    libavcodec-dev \
    libavdevice-dev \
    libavutil-dev \
    libswscale-dev \
    libswresample-dev
```

### Python依赖

```bash
pip3 install \
    aiortc \
    aiohttp \
    av \
    numpy \
    opencv-python \
    pyyaml
```

### ROS依赖

**ROS1:**
```bash
sudo apt-get install ros-noetic-cv-bridge ros-noetic-vision-msgs
```

**ROS2:**
```bash
sudo apt-get install ros-humble-cv-bridge ros-humble-vision-msgs
```

## 编译安装

### ROS1 (Catkin)

```bash
cd ~/catkin_ws/src
git clone <your-repo-url> webrtc_ros_bridge
cd ~/catkin_ws
catkin_make
source devel/setup.bash
```

### ROS2 (Colcon)

```bash
cd ~/ros2_ws/src
git clone <your-repo-url> webrtc_ros_bridge
cd ~/ros2_ws
colcon build --packages-select webrtc_ros_bridge
source install/setup.bash
```

## 配置

编辑 `config/stream_config.yaml`:

```yaml
server:
  host: "192.168.1.100"  # 你的媒体服务器地址
  port: 7777
  protocol: "http"

streams:
  - name: "camera_front"
    stream_id: "your_stream_id"
    token: "your_jwt_token"  # 如果需要认证
```

## 使用方法

### ROS1

```bash
# 启动节点
rosrun webrtc_ros_bridge bridge_node_ros1.py

# 或使用launch文件
roslaunch webrtc_ros_bridge webrtc.launch

# 查看话题
rostopic list
rostopic hz /webrtc/image

# 可视化
rqt_image_view
```

### ROS2

```bash
# 启动节点
ros2 run webrtc_ros_bridge bridge_node

# 或使用launch文件
ros2 launch webrtc_ros_bridge webrtc.launch.py

# 查看话题
ros2 topic list
ros2 topic hz /webrtc/image

# 可视化
ros2 run rqt_image_view rqt_image_view
```

## 发布的话题

| 话题 | 类型 | 描述 |
|------|------|------|
| `/webrtc/image` | `sensor_msgs/Image` | 原始图像 |
| `/webrtc/image/compressed` | `sensor_msgs/CompressedImage` | 压缩图像 |
| `/webrtc/camera_info` | `sensor_msgs/CameraInfo` | 相机信息 |
| `/webrtc/audio` | `audio_common_msgs/AudioData` | 音频数据 |

## 性能调优

在 `config/stream_config.yaml` 中调整:

```yaml
performance:
  buffer_size: 10        # 缓冲区大小
  queue_size: 10         # ROS队列大小
  thread_pool_size: 4    # 线程池大小
```

## 故障排查

### 连接失败

1. 检查媒体服务器是否运行
2. 验证stream_id是否正确
3. 检查网络连接和防火墙

### 无图像输出

1. 确认流是否活跃:  `curl http://your-server:7777/api/streams/`
2. 检查ROS话题:  `rostopic echo /webrtc/image` (ROS1) 或 `ros2 topic echo /webrtc/image`
3. 查看日志输出

### 延迟问题

- 减小buffer_size和queue_size
- 使用CompressedImage话题
- 检查网络带宽

## 许可证

MIT License

## 贡献

欢迎提交Issue和Pull Request! 
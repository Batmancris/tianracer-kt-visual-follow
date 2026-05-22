"""
ROS2发布节点
"""
import rclpy
from rclpy.node import Node
import cv2
from sensor_msgs.msg import Image, CompressedImage, CameraInfo
from cv_bridge import CvBridge
import numpy as np
import threading
import asyncio
from ..core.stream_manager import StreamManager
from ..utils.config_loader import ConfigLoader


class ROS2PublisherNode(Node):
    """
    ROS2发布节点
    低耦合: 仅负责ROS2相关功能
    """

    def __init__(self):
        super().__init__('webrtc_ros_bridge')

        # 声明参数
        # 默认尝试从 install 目录获取
        default_config = 'config/stream_config.yaml'
        self.declare_parameter('config_path', default_config)
        config_path = self.get_parameter('config_path').value

        # 增强鲁棒性：如果路径不存在且是相对路径，尝试在包 share 目录查找
        import os
        if not os.path.exists(config_path) and not os.path.isabs(config_path):
            try:
                from ament_index_python.packages import get_package_share_directory
                share_dir = get_package_share_directory('webrtc_ros_bridge')
                possible_path = os.path.join(share_dir, config_path)
                if os.path.exists(possible_path):
                    self.get_logger().info(f"Resolved relative config path to: {possible_path}")
                    config_path = possible_path
                else:
                    # 尝试只用文件名
                    filename = os.path.basename(config_path)
                    possible_path_2 = os.path.join(share_dir, 'config', filename)
                    if os.path.exists(possible_path_2):
                        self.get_logger().info(f"Resolved config by filename to: {possible_path_2}")
                        config_path = possible_path_2
            except ImportError:
                pass
            except Exception as e:
                self.get_logger().warn(f"Failed to resolve config path: {e}")

        # 加载配置
        self.config = ConfigLoader.load(config_path)

        # CV Bridge
        self.bridge = CvBridge()

        # 创建发布者
        qos = self.config['performance']['queue_size']
        self.image_pub = self.create_publisher(
            Image,
            self.config['ros']['image_topic'],
            qos
        )

        self. compressed_pub = self.create_publisher(
            CompressedImage,
            self.config['ros']['compressed_topic'],
            qos
        )

        self.camera_info_pub = self.create_publisher(
            CameraInfo,
            self. config['ros']['camera_info_topic'],
            qos
        )

        # 流管理器
        self.stream_manager = StreamManager(self. config)
        self.stream_manager.set_video_publisher(self._publish_video)

        # 异步事件循环
        self.loop = asyncio.new_event_loop()
        self.thread = None

        # 启动异步任务
        self._start_async_tasks()

    def _publish_video(self, img: np.ndarray, frame):
        """发布视频到ROS2"""
        try:
            if self.config['media']['video']['enabled']:
                # 发布原始图像
                ros_image = self.bridge.cv2_to_imgmsg(img, encoding="bgr8")
                ros_image. header.stamp = self.get_clock().now().to_msg()
                ros_image.header. frame_id = "camera"
                self.image_pub.publish(ros_image)

                self.get_logger().debug('Published image frame')

        except Exception as e:
            self.get_logger().error(f"Publish error: {e}")

    def _run_async_loop(self):
        """在独立线程中运行异步事件循环"""
        asyncio.set_event_loop(self.loop)

        # 启动流管理器
        for stream_config in self.config['streams']:
            self.loop.run_until_complete(
                self.stream_manager.start(stream_config)
            )

        # 保持循环运行
        self.loop.run_forever()

    def _start_async_tasks(self):
        """启动异步任务"""
        self.get_logger().info("Starting WebRTC ROS2 Bridge...")
        self.thread = threading.Thread(
            target=self._run_async_loop, daemon=True) # 已经是 daemon=True 了，这很好
        self.thread.start()

    def destroy_node(self):
        """清理资源"""
        self.loop. call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self. thread.join()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    node = ROS2PublisherNode()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        # 确保在销毁节点前停止异步线程
        if hasattr(node, "destroy_node"):
            node.destroy_node()
        
        # 避免多次调用 shutdown
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()

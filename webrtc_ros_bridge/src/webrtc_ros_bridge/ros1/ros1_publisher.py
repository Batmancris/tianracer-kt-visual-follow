"""
ROS1发布节点
"""
import rospy
import numpy as np
import cv2
from sensor_msgs. msg import Image, CompressedImage, CameraInfo
from cv_bridge import CvBridge
import threading
import asyncio
from .. core.stream_manager import StreamManager
from ..utils.config_loader import ConfigLoader


class ROS1PublisherNode:
    """
    ROS1发布节点
    低耦合：仅负责ROS1相关功能
    """

    def __init__(self):
        rospy.init_node('webrtc_ros_bridge', anonymous=True)

        # 加载配置
        config_path = rospy.get_param(
            '~config_path', 'config/stream_config.yaml')
        self.config = ConfigLoader. load(config_path)

        # CV Bridge
        self.bridge = CvBridge()

        # 创建发布者
        self.image_pub = rospy.Publisher(
            self.config['ros']['image_topic'],
            Image,
            queue_size=self.config['performance']['queue_size']
        )

        self.compressed_pub = rospy.Publisher(
            self.config['ros']['compressed_topic'],
            CompressedImage,
            queue_size=self.config['performance']['queue_size']
        )

        self.camera_info_pub = rospy.Publisher(
            self. config['ros']['camera_info_topic'],
            CameraInfo,
            queue_size=self. config['performance']['queue_size']
        )

        # 流管理器
        self.stream_manager = StreamManager(self. config)
        self.stream_manager.set_video_publisher(self._publish_video)

        # 异步事件循环
        self. loop = asyncio.new_event_loop()
        self.thread = None

    def _publish_video(self, img: np.ndarray, frame):
        """发布视频到ROS"""
        try:
            # 发布原始图像
            if self.config['media']['video']['enabled']:
                ros_image = self.bridge.cv2_to_imgmsg(img, encoding="bgr8")
                ros_image.header.stamp = rospy.Time.now()
                ros_image.header.frame_id = "camera"
                self.image_pub. publish(ros_image)

                # 发布压缩图像
                compressed_msg = CompressedImage()
                compressed_msg.header = ros_image.header
                compressed_msg.format = "jpeg"
                compressed_msg.data = np.array(
                    cv2.imencode('.jpg', img)[1]).tobytes()
                self.compressed_pub.publish(compressed_msg)

        except Exception as e:
            rospy.logerr(f"Publish error: {e}")

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

    def run(self):
        """运行节点"""
        rospy.loginfo("Starting WebRTC ROS1 Bridge...")

        # 在独立线程中运行异步代码
        self.thread = threading.Thread(
            target=self._run_async_loop, daemon=True)
        self.thread.start()

        # ROS spin
        rospy.spin()

        # 清理
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.thread.join()

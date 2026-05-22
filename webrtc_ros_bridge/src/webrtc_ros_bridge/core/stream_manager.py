"""
流管理器，协调WebRTC客户端和媒体解码器
"""
import asyncio
from typing import Optional, Callable
from . webrtc_client import WebRTCStreamClient
from .media_decoder import MediaDecoder


class StreamManager:
    """
    流管理器
    低耦合：作为中介协调各组件
    """

    def __init__(self, config: dict):
        self.config = config
        self.client: Optional[WebRTCStreamClient] = None
        self.decoder = MediaDecoder()
        self.video_publisher: Optional[Callable] = None
        self. audio_publisher: Optional[Callable] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_video_publisher(self, publisher: Callable):
        """设置视频发布回调"""
        self.video_publisher = publisher

    def set_audio_publisher(self, publisher: Callable):
        """设置音频发布回调"""
        self. audio_publisher = publisher

    async def start(self, stream_config: dict):
        """
        启动流管理器

        Args:
            stream_config: 流配置字典
        """
        server_url = f"{self.config['server']['protocol']}://{self.config['server']['host']}:{self. config['server']['port']}"

        self.client = WebRTCStreamClient(
            server_url=server_url,
            stream_id=stream_config['stream_id'],
            token=stream_config.get('token')
        )

        # 设置回调
        self.client.set_video_callback(self._handle_video_frame)
        self.client.set_audio_callback(self._handle_audio_frame)

        # 连接
        await self.client.connect()

    async def _handle_video_frame(self, frame):
        """处理视频帧"""
        img = self.decoder.decode_video_frame(frame)
        if img is not None and self.video_publisher:
            # 调用ROS发布回调
            await asyncio.get_event_loop().run_in_executor(
                None, self.video_publisher, img, frame
            )

    async def _handle_audio_frame(self, frame):
        """处理音频帧"""
        audio_data = self.decoder.decode_audio_frame(frame)
        if audio_data is not None and self.audio_publisher:
            await asyncio.get_event_loop().run_in_executor(
                None, self.audio_publisher, audio_data, frame
            )

    async def stop(self):
        """停止流管理器"""
        if self.client:
            await self.client. disconnect()

"""
媒体解码器，将WebRTC帧转换为ROS消息格式
"""
import numpy as np
from typing import Optional
import av
from av import VideoFrame, AudioFrame


class MediaDecoder:
    """
    媒体解码器
    高内聚：专注于媒体格式转换
    """

    def __init__(self):
        self.video_codec = None
        self. audio_codec = None

    def decode_video_frame(self, frame: VideoFrame) -> Optional[np.ndarray]:
        """
        解码视频帧为numpy数组

        Args:
            frame: aiortc VideoFrame对象

        Returns:
            numpy数组 (height, width, 3) BGR格式
        """
        try:
            # 转换为numpy数组
            img = frame.to_ndarray(format="bgr24")
            return img
        except Exception as e:
            print(f"Video decode error: {e}")
            return None

    def decode_audio_frame(self, frame: AudioFrame) -> Optional[np.ndarray]:
        """
        解码音频帧为numpy数组

        Args:
            frame: aiortc AudioFrame对象

        Returns:
            numpy数组
        """
        try:
            # 转换为numpy数组
            audio_data = frame. to_ndarray()
            return audio_data
        except Exception as e:
            print(f"Audio decode error: {e}")
            return None

    def get_frame_info(self, frame: VideoFrame) -> dict:
        """获取帧信息"""
        return {
            'width': frame.width,
            'height': frame.height,
            'format': frame.format. name,
            'pts': frame.pts,
            'time_base': frame.time_base
        }

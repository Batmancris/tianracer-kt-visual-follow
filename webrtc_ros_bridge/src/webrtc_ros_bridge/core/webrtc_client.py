"""
WebRTC客户端封装，负责与媒体服务器建立连接并接收流
"""
import asyncio
import aiohttp
from typing import Optional, Callable
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import json
from urllib.parse import urljoin

# RtcpPsfbPacket 在较新版本 aiortc 中提供；老版本可能没有
try:
    from aiortc.rtcp import RtcpPsfbPacket  # type: ignore
except ImportError:
    import struct

    class RtcpPsfbPacket:
        """
        Fallback implementation of RTCP Payload-Specific Feedback packet (RFC 4585).
        Used when aiortc does not provide RtcpPsfbPacket (e.g. version 1.14.0).
        """

        def __init__(self, fmt=1):
            self.fmt = fmt  # FMT=1 for PLI
            self.ssrc = 0
            self.media_ssrc = 0

        def serialize(self) -> bytes:
            # v=2, p=0, fmt=...
            v_pf_fmt = (2 << 6) | (self.fmt & 0x1f)
            pt = 206  # Payload-specific (PSFB)
            # length in 32-bit words minus 1. Total 12 bytes = 3 words. 3-1=2.
            length = 2
            # SSRC of packet sender
            # SSRC of media source
            return struct.pack(
                "!BBHII", v_pf_fmt, pt, length, int(
                    self.ssrc), int(
                    self.media_ssrc))

        def __repr__(self):
            return f"<RtcpPsfbPacket fmt={self.fmt} ssrc={self.ssrc} media_ssrc={self.media_ssrc}>"


class WebRTCStreamClient:
    """
    WebRTC流客户端，通过WHEP协议订阅媒体流
    """

    def __init__(
            self,
            server_url: str,
            stream_id: str,
            token: Optional[str] = None):
        self.server_url = server_url. rstrip('/')
        self.stream_id = stream_id
        self.token = token
        self.pc: Optional[RTCPeerConnection] = None
        self.video_callback: Optional[Callable] = None
        self.audio_callback: Optional[Callable] = None
        self._running = False
        # WHEP Location header for trickle ICE
        self._whep_resource_url: Optional[str] = None

    def set_video_callback(self, callback: Callable):
        """设置视频帧回调"""
        self.video_callback = callback

    def set_audio_callback(self, callback: Callable):
        """设置音频帧回调"""
        self.audio_callback = callback

    async def connect(self):
        """
        建立WebRTC连接（WHEP协议）
        """
        self._running = True
        print(f"🔗 正在连接到流:  {self.stream_id}")
        print(f"📡 服务器: {self.server_url}")

        self.pc = RTCPeerConnection()

        # 注册track接收处理器
        @self.pc.on("track")
        async def on_track(track: MediaStreamTrack):
            print(f"✅ 收到 {track.kind} 轨道")

            if track.kind == "video" and self.video_callback:
                asyncio.create_task(
                    self._request_keyframe(
                        track, reason="track-received"))
                asyncio.create_task(self._process_video_track(track))
            elif track.kind == "audio" and self.audio_callback:
                asyncio.create_task(self._process_audio_track(track))

        # 记录 ICE/连接状态，便于诊断 ICE 是否真正连通
        @self.pc.on("iceconnectionstatechange")
        async def on_ice_state_change():
            print(f"🌡️ ICE 状态: {self.pc.iceConnectionState}")
            if self.pc.iceConnectionState == "connected":
                # ICE连通后再次确保请求关键帧，防止 on_track 时发送失败
                for transceiver in self.pc.getTransceivers():
                    if transceiver.receiver and transceiver.receiver.track and transceiver.receiver.track.kind == "video":
                        print("🔄 ICE Connected: 主动触发 PLI")
                        asyncio.create_task(
                            self._request_keyframe(
                                transceiver.receiver.track,
                                reason="ice-connected"))

        @self.pc.on("connectionstatechange")
        async def on_connection_state_change():
            print(f"🔄 Peer 连接状态: {self.pc.connectionState}")

        # WHEP trickle ICE: 在本地候选产生时，通过 PATCH 发送到 Location 资源
        @self.pc.on("icecandidate")
        async def on_ice_candidate(candidate):
            try:
                await self._send_trickle_candidate(candidate)
            except Exception as e:
                print(f"⚠️ 发送 ICE 候选失败: {e}")

        # ✅ 修复：只添加video transceiver，使用统一的ICE参数
        # 不要同时添加audio transceiver，避免ICE参数冲突
        self. pc.addTransceiver("video", direction="recvonly")
        # 注释掉audio transceiver，让服务器决定
        # self.pc.addTransceiver("audio", direction="recvonly")

        # 创建Offer
        offer = await self.pc.createOffer()
        await self.pc. setLocalDescription(offer)

        print(f"📤 发送SDP Offer到服务器...")
        # 修复：将反斜杠移到f-string外面
        newline = '\n'
        offer_media_count = len(
            [line for line in offer.sdp. split(newline) if 'm=' in line])
        print(f"📋 SDP Offer包含 {offer_media_count} 个媒体流")

        # 通过WHEP协议发送SDP
        whep_url = f"{self.server_url}/whep/{self.stream_id}"
        headers = {"Content-Type": "application/sdp"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"

        print(f"🌐 WHEP URL: {whep_url}")

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    whep_url,
                    data=self.pc.localDescription. sdp,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as response:
                    status = response.status

                    print(f"📥 服务器响应:  HTTP {status}")

                    if status == 404:
                        error_msg = f"❌ 流不存在: '{self.stream_id}'\n"
                        error_msg += f"💡 请检查:\n"
                        error_msg += f"   1. 流ID是否正确\n"
                        error_msg += f"   2. 是否有推流在运行\n"
                        error_msg += f"   3. 运行命令查看可用流:  curl http://192.168.128.10:7777/api/streams"
                        raise Exception(error_msg)

                    elif status == 500:
                        response_text = await response.text()
                        error_msg = f"❌ 服务器内部错误 (HTTP 500)\n"
                        error_msg += f"💡 可能的原因:\n"
                        error_msg += f"   1. 流 '{self.stream_id}' 没有活跃的发布者（没有推流）\n"
                        error_msg += f"   2. 服务器配置问题\n"
                        error_msg += f"   3. SDP协商失败\n"
                        error_msg += f"📄 服务器响应: {response_text[: 200]}\n"
                        error_msg += f"\n🔍 调试步骤:\n"
                        error_msg += f"   1. 检查流列表:  curl http://192.168.128.10:7777/api/streams\n"
                        error_msg += f"   2. 启动Tianracer摄像头推流\n"
                        error_msg += f"   3. 尝试其他流ID: fpv, camera, front, video"
                        raise Exception(error_msg)

                    elif status not in [200, 201]:
                        response_text = await response.text()
                        raise Exception(
                            f"WHEP请求失败:  HTTP {status}\n"
                            f"响应: {response_text[:200]}"
                        )

                    # 获取WHEP资源Location，用于后续trickle ICE PATCH
                    location = response.headers.get("Location")
                    if location:
                        # 服务器可能返回相对路径，转为绝对URL
                        self._whep_resource_url = urljoin(
                            self.server_url + '/', location)
                        print(f"📌 WHEP资源: {self._whep_resource_url}")
                    else:
                        print("⚠️ 未收到 Location 头，可能无法发送 ICE 候选")

                    # 获取Answer SDP
                    answer_sdp = await response.text()
                    print(f"✅ 收到SDP Answer")
                    answer_media_count = len(
                        [line for line in answer_sdp. split(newline) if 'm=' in line])
                    print(f"📋 SDP Answer包含 {answer_media_count} 个媒体流")

                    await self.pc.setRemoteDescription(
                        RTCSessionDescription(sdp=answer_sdp, type="answer")
                    )

        except asyncio. TimeoutError:
            raise Exception(
                f"❌ 连接超时\n"
                f"💡 请检查:\n"
                f"   1. 服务器 {self.server_url} 是否可访问\n"
                f"   2. 网络连接是否正常"
            )
        except aiohttp.ClientError as e:
            self._running = False
            raise Exception(f"❌ 网络错误: {e}")

        print(f"🎉 成功连接到流: {self.stream_id}")

    async def _send_trickle_candidate(self, candidate):
        """向WHEP资源发送单个ICE候选或结束标记"""
        if not self._whep_resource_url:
            print("⚠️ 没有 WHEP Location，跳过 ICE 候选发送")
            return

        headers = {"Content-Type": "application/trickle-ice-sdpfrag"}

        # candidate 为 None 表示 end-of-candidates
        if candidate is None:
            body = "a=end-of-candidates\r\n"
        else:
            body = f"a={candidate.to_sdp()}\r\n"

        async with aiohttp.ClientSession() as session:
            async with session.patch(
                self._whep_resource_url,
                data=body,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=5)
            ) as resp:
                if resp.status not in [200, 201, 204]:
                    text = await resp.text()
                    print(f"⚠️ ICE PATCH 失败 HTTP {resp.status}: {text[:200]}")
                else:
                    kind = "end-of-candidates" if candidate is None else "candidate"
                    print(f"📨 已发送 {kind} (HTTP {resp.status})")

    async def _process_video_track(self, track: MediaStreamTrack):
        """处理视频轨道"""
        frame_count = 0
        try:
            while self._running:
                try:
                    frame = await asyncio.wait_for(track.recv(), timeout=3.0)
                except asyncio.TimeoutError:
                    print("⏳ 3s 未收到视频帧，重发 PLI")
                    await self._request_keyframe(track, reason="timeout")
                    continue

                frame_count += 1
                if frame_count == 1:
                    print(f"🎥 开始接收视频帧 ({frame.width}x{frame.height})")
                if self.video_callback:
                    await self.video_callback(frame)
        except Exception as e:
            print(f"❌ 视频轨道错误: {e}")

    async def _process_audio_track(self, track: MediaStreamTrack):
        """处理音频轨道"""
        frame_count = 0
        try:
            while self._running:
                frame = await track. recv()
                frame_count += 1
                if frame_count == 1:
                    print(f"🎵 开始接收音频帧")
                if self.audio_callback:
                    await self.audio_callback(frame)
        except Exception as e:
            print(f"❌ 音频轨道错误: {e}")

    async def disconnect(self):
        """断开连接"""
        self._running = False
        if self.pc:
            await self.pc. close()
        print("🔌 已断开连接")

    async def _request_keyframe(
            self,
            track: MediaStreamTrack,
            reason: str = ""):
        """请求关键帧，部分编码端需要PLI后才开始推送"""
        receiver = self._find_receiver_for_track(track)
        label = f"reason={reason}" if reason else ""
        if not receiver:
            print(f"⚠️ 未找到receiver，无法发送 PLI {label}")
            return

        # 等待 transport 变为 'connected' 状态
        for _ in range(10):  # 最多等待 5 秒
            # 如果有官方 API，假定它可以工作或自行处理 transport
            if hasattr(receiver, "send_rtcp_pli"):
                break

            # 获取 transport
            transport = getattr(
                receiver,
                "transport",
                None) or getattr(
                receiver,
                "_transport",
                None)

            # 检查 transport 是否连接
            if transport and transport.state == "connected":
                break

            await asyncio.sleep(0.5)

        if hasattr(receiver, "send_rtcp_pli"):
            try:
                await receiver.send_rtcp_pli()
                await asyncio.sleep(0.5)
                await receiver.send_rtcp_pli()
                print(f"📨 已发送 PLI 请求关键帧 {label}")
                return
            except Exception as e:
                print(f"⚠️ 请求关键帧失败 {label}: {e}")

        # fallback: 构造 RTCP PLI 包直接通过 transport 发送
        sent = await self._send_rtcp_pli_fallback(receiver, label)
        if not sent:
            print(f"⚠️ receiver不支持 PLI，且fallback失败 {label}")

    def _find_receiver_for_track(self, track: MediaStreamTrack):
        if not self.pc:
            return None
        for transceiver in self.pc.getTransceivers():
            if transceiver.receiver and transceiver.receiver.track is track:
                return transceiver.receiver
        return None

    async def _send_rtcp_pli_fallback(self, receiver, label: str) -> bool:
        if RtcpPsfbPacket is None:
            print(
                f"⚠️ 当前 aiortc 不包含 RtcpPsfbPacket，无法 fallback 发送 PLI {label}")
            return False
        try:
            # 尝试获取 transport，兼容 public property 和 private attribute
            transport = getattr(
                receiver,
                "transport",
                None) or getattr(
                receiver,
                "_transport",
                None)
            if not transport:
                print(
                    f"⚠️ fallback PLI 无 transport {label} (dir={dir(receiver)[:20]}...)")
                return False

            # 选取本端/远端 SSRC
            # 1. 尝试获取本地 SSRC (Sender SSRC)
            # aiortc 1.x 可能使用 _RTCRtpReceiver__rtcp_ssrc
            ssrc = (
                getattr(receiver, "_RTCRtpReceiver__rtcp_ssrc", None) or
                getattr(receiver, "_ssrc", None) or
                getattr(receiver, "ssrc", 0) or
                0
            )

            # 2. 尝试获取媒体源 SSRC (Media SSRC)
            media_ssrc = 0
            # aiortc 1.x 可能使用 _RTCRtpReceiver__remote_streams (dict, keys are
            # ssrc)
            remote_streams = getattr(
                receiver, "_RTCRtpReceiver__remote_streams", None)
            if remote_streams and len(remote_streams) > 0:
                media_ssrc = list(remote_streams.keys())[0]

            # Legacy fallbacks
            if media_ssrc == 0:
                media_ssrc = (
                    getattr(receiver, "_remote_ssrc", None) or
                    getattr(receiver, "remote_ssrc", None)
                )

            if media_ssrc == 0 or media_ssrc is None:
                track_obj = getattr(
                    receiver, "track", None) or getattr(
                    receiver, "_track", None)
                if track_obj:
                    media_ssrc = getattr(track_obj, "ssrc", 0)

            media_ssrc = media_ssrc or 0

            packet = RtcpPsfbPacket(fmt=1)  # PLI
            packet.ssrc = ssrc
            packet.media_ssrc = media_ssrc

            # 序列化包数据
            if hasattr(packet, "serialize"):
                payload = packet.serialize()
            else:
                try:
                    payload = bytes(packet)
                except Exception as e:
                    print(f"⚠️ 无法序列化 packet: {e}")
                    return False

            # 通过 transport 发送 RTP/RTCP (需使用 _send_rtp 并传入 bytes)
            if hasattr(transport, "_send_rtp"):
                await transport._send_rtp(payload)
                print(
                    f"📨 已发送 PLI (fallback via _send_rtp) {label}, ssrc={packet.ssrc}, media_ssrc={packet.media_ssrc}")
                return True
            else:
                print(f"⚠️ transport 无 _send_rtp 方法 {label}")
                return False

        except Exception as e:
            print(f"⚠️ fallback PLI 失败 {label}: {e}")
            import traceback
            traceback.print_exc()
            return False

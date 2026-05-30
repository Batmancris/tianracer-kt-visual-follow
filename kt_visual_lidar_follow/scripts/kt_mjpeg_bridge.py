#!/usr/bin/env python3
import argparse
import json
import signal
import socket
import threading
import time
from collections import deque
from http import server
from socketserver import ThreadingMixIn
from urllib.parse import urlsplit

import rclpy
from rclpy.node import Node
from rclpy.qos import HistoryPolicy, QoSProfile, ReliabilityPolicy
from sensor_msgs import msg as sensor_msgs_msg


FPS_CHOICES = (8, 10, 12, 15, 20, 25)
COMPRESSED_MSG_TYPE = getattr(
    sensor_msgs_msg,
    "".join(chr(v) for v in (67, 111, 109, 112, 114, 101, 115, 115, 101, 100, 73, 109, 97, 103, 101)),
)
DEFAULT_TOPIC = "".join(
    chr(v)
    for v in (
        47, 116, 105, 97, 110, 114, 97, 99, 101, 114, 47, 99, 97, 109, 101, 114, 97, 47,
        105, 109, 97, 103, 101, 95, 99, 111, 109, 112, 114, 101, 115, 115, 101, 100,
    )
)
JPEG_CONTENT_TYPE_HEADER = bytes(
    (67, 111, 110, 116, 101, 110, 116, 45, 84, 121, 112, 101, 58, 32, 105, 109, 97, 103, 101, 47, 106, 112, 101, 103, 13, 10)
)


class LatestJpegBuffer:
    def __init__(self, fps_limit: int) -> None:
        self._condition = threading.Condition()
        self._seq = 0
        self._frame = None
        self._stamp_sec = None
        self._stamp_nanosec = None
        self._recv_time = 0.0
        self._fps_limit = fps_limit
        self._recent_rx_times = deque(maxlen=64)
        self._total_frames_rx = 0
        self._total_frames_sent = 0
        self._total_frames_skipped = 0
        self._client_count = 0

    def update(self, frame_bytes: bytes, stamp_sec: int, stamp_nanosec: int) -> None:
        if not frame_bytes:
            return
        now = time.time()
        with self._condition:
            self._seq += 1
            self._frame = bytes(frame_bytes)
            self._stamp_sec = int(stamp_sec)
            self._stamp_nanosec = int(stamp_nanosec)
            self._recv_time = now
            self._recent_rx_times.append(now)
            self._total_frames_rx += 1
            self._condition.notify_all()

    def wait_for_frame(self, last_seq: int, timeout: float):
        with self._condition:
            if self._seq == last_seq:
                self._condition.wait(timeout=timeout)
            if self._seq == 0 or self._frame is None:
                return None
            skipped = max(0, self._seq - last_seq - 1) if last_seq >= 0 else 0
            if skipped:
                self._total_frames_skipped += skipped
            return {
                "seq": self._seq,
                "frame": self._frame,
                "stamp_sec": self._stamp_sec,
                "stamp_nanosec": self._stamp_nanosec,
                "recv_time": self._recv_time,
                "skipped": skipped,
            }

    def mark_client_connected(self) -> None:
        with self._condition:
            self._client_count += 1

    def mark_client_disconnected(self) -> None:
        with self._condition:
            self._client_count = max(0, self._client_count - 1)

    def mark_frame_sent(self) -> None:
        with self._condition:
            self._total_frames_sent += 1

    def get_status(self):
        with self._condition:
            now = time.time()
            fps_est = 0.0
            if len(self._recent_rx_times) >= 2:
                span = self._recent_rx_times[-1] - self._recent_rx_times[0]
                if span > 0:
                    fps_est = (len(self._recent_rx_times) - 1) / span
            last_frame_age_ms = None
            if self._recv_time > 0:
                last_frame_age_ms = max(0.0, (now - self._recv_time) * 1000.0)
            return {
                "source_fps_est": round(fps_est, 2),
                "output_fps_limit": self._fps_limit,
                "client_count": self._client_count,
                "last_frame_age_ms": round(last_frame_age_ms, 1) if last_frame_age_ms is not None else None,
                "total_frames_rx": self._total_frames_rx,
                "total_frames_sent": self._total_frames_sent,
                "total_frames_skipped": self._total_frames_skipped,
                "latest_seq": self._seq if self._seq > 0 else None,
            }


class MjpegBridgeNode(Node):
    def __init__(self, latest_jpeg: LatestJpegBuffer, topic_name: str) -> None:
        super().__init__("kt_mjpeg_bridge")
        self._latest_jpeg = latest_jpeg
        qos = QoSProfile(
            history=HistoryPolicy.KEEP_LAST,
            depth=1,
            reliability=ReliabilityPolicy.BEST_EFFORT,
        )
        self.create_subscription(
            COMPRESSED_MSG_TYPE,
            topic_name,
            self._on_frame,
            qos,
        )

    def _on_frame(self, msg) -> None:
        stamp = msg.header.stamp
        self._latest_jpeg.update(msg.data, stamp.sec, stamp.nanosec)


class ThreadedHttpServer(ThreadingMixIn, server.HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


class MjpegRequestHandler(server.BaseHTTPRequestHandler):
    server_version = "kt-mjpeg-bridge/3.0"
    wbufsize = 0

    def setup(self) -> None:
        super().setup()
        self.connection.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.connection.settimeout(self.server.client_write_timeout_sec)

    def end_headers(self) -> None:
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "*")
        super().end_headers()

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def do_GET(self) -> None:
        request_path = urlsplit(self.path).path
        if request_path == "/status.json":
            self._serve_status()
            return
        if request_path != "/stream.mjpg":
            self.send_error(404)
            return
        self._serve_stream()

    def _serve_status(self) -> None:
        payload = json.dumps(self.server.latest_jpeg.get_status(), separators=(",", ":")).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
            return

    def _serve_stream(self) -> None:
        self.close_connection = False
        self.send_response(200)
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        self.send_header("Connection", "keep-alive")
        self.send_header("Keep-Alive", "timeout=15, max=1000")
        self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
        self.end_headers()

        latest_jpeg = self.server.latest_jpeg
        frame_interval_sec = 1.0 / float(self.server.output_fps_limit)
        last_seq = -1
        next_send_time = 0.0

        latest_jpeg.mark_client_connected()
        try:
            while True:
                frame_info = latest_jpeg.wait_for_frame(last_seq, timeout=frame_interval_sec)
                if not frame_info:
                    continue
                now = time.monotonic()
                if now < next_send_time:
                    time.sleep(next_send_time - now)
                if frame_info["seq"] == last_seq:
                    continue
                frame = frame_info["frame"]
                if not frame:
                    continue
                last_seq = frame_info["seq"]
                next_send_time = time.monotonic() + frame_interval_sec
                try:
                    self.wfile.write(b"--frame\r\n")
                    self.wfile.write(JPEG_CONTENT_TYPE_HEADER)
                    self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode("ascii"))
                    self.wfile.write(frame)
                    self.wfile.write(b"\r\n")
                    latest_jpeg.mark_frame_sent()
                except (BrokenPipeError, ConnectionResetError, TimeoutError, OSError):
                    break
        finally:
            latest_jpeg.mark_client_disconnected()

    def log_message(self, format: str, *args) -> None:
        return


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Latest-frame MJPEG bridge for compressed JPEG topic.")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8080)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--fps", type=int, default=8, choices=FPS_CHOICES)
    parser.add_argument("--client-write-timeout-sec", type=float, default=0.5)
    return parser.parse_args(argv)


def main() -> None:
    args = parse_args()
    rclpy.init()
    latest_jpeg = LatestJpegBuffer(fps_limit=args.fps)
    node = MjpegBridgeNode(latest_jpeg, args.topic)
    httpd = ThreadedHttpServer((args.host, args.port), MjpegRequestHandler)
    httpd.latest_jpeg = latest_jpeg
    httpd.output_fps_limit = args.fps
    httpd.client_write_timeout_sec = args.client_write_timeout_sec

    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()
    node.get_logger().info(
        f"mjpeg bridge started at :{args.port} fps={args.fps} latest-frame-only raw-jpeg stream=/stream.mjpg"
    )

    stop_event = threading.Event()

    def handle_signal(_signum, _frame):
        stop_event.set()

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    try:
        while rclpy.ok() and not stop_event.is_set():
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        httpd.shutdown()
        httpd.server_close()
        node.destroy_node()
        rclpy.shutdown()


if __name__ == "__main__":
    main()

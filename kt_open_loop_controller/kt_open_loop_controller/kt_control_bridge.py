#!/usr/bin/env python3
"""KT control bridge — HTTP API + radar safety + ackermann output."""

import json
import math
import subprocess
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

import rclpy
from rclpy.node import Node
from rclpy.qos import QoSProfile, ReliabilityPolicy, DurabilityPolicy
from sensor_msgs.msg import LaserScan
from ackermann_msgs.msg import AckermannDrive

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
HTTP_PORT = 8766
EMA_ALPHA = 0.3
RADAR_FRONT_WINDOW_DEG = 30.0
BRIGHTNESS_MIN = -64
BRIGHTNESS_MAX = 64


# ---------------------------------------------------------------------------
# HTTP handler (runs in its own thread)
# ---------------------------------------------------------------------------
class ControlHTTPHandler(BaseHTTPRequestHandler):
    bridge = None  # set after node creation

    def log_message(self, fmt, *args):
        pass  # silence default stderr logging

    def _cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")

    def _json(self, code, obj):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self._cors()
        self.end_headers()
        self.wfile.write(body)

    def _read_json_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        return json.loads(self.rfile.read(length))

    # -- routing ------------------------------------------------------------
    def do_OPTIONS(self):
        self.send_response(204)
        self._cors()
        self.end_headers()

    def do_GET(self):
        b = self.bridge
        if self.path == "/api/control/status":
            self._json(200, {
                "control_mode": b.control_mode,
                "enable_mcu_output": b.enable_mcu_output,
                "emergency_stop": b.emergency_stop,
                "manual_speed": b.manual_speed,
                "manual_steering": b.manual_steering,
                "radar_raw_distance": b.radar_raw_distance,
                "radar_filtered_distance": b.radar_filtered_distance,
            })
        elif self.path == "/api/camera/brightness":
            val = _read_brightness()
            if val is None:
                self._json(500, {"error": "failed to read brightness"})
            else:
                self._json(200, {"brightness": val})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        b = self.bridge
        body = self._read_json_body()

        if self.path == "/api/control/enable":
            b.enable_mcu_output = bool(body.get("enable", False))
            if not b.enable_mcu_output:
                b.control_mode = "disabled"
            b.get_logger().info(f"enable_mcu_output -> {b.enable_mcu_output}")
            self._json(200, {"enable_mcu_output": b.enable_mcu_output})

        elif self.path == "/api/control/stop":
            b.send_stop_command(force=True)
            b.enable_mcu_output = False
            b.control_mode = "disabled"
            b.get_logger().info("manual stop -> disabled")
            self._json(200, {"ok": True})

        elif self.path == "/api/control/estop":
            b.emergency_stop = bool(body.get("enable", True))
            if b.emergency_stop:
                b.send_stop_command(force=True)
            b.get_logger().info(f"emergency_stop -> {b.emergency_stop}")
            self._json(200, {"emergency_stop": b.emergency_stop})

        elif self.path == "/api/control/manual":
            speed = float(body.get("speed", 0.0))
            steering = float(body.get("steering", 0.0))
            b.manual_speed = speed
            b.manual_steering = steering
            b.control_mode = "manual"
            b.safe_send_motion_command(speed, steering)
            self._json(200, {"speed": speed, "steering": steering})

        elif self.path == "/api/camera/brightness":
            val = int(body.get("brightness", 0))
            val = max(BRIGHTNESS_MIN, min(BRIGHTNESS_MAX, val))
            ok = _write_brightness(val)
            if ok:
                self._json(200, {"brightness": val})
            else:
                self._json(500, {"error": "failed to write brightness"})

        else:
            self._json(404, {"error": "not found"})


# ---------------------------------------------------------------------------
# v4l2-ctl helpers
# ---------------------------------------------------------------------------
def _read_brightness():
    try:
        out = subprocess.check_output(
            ["v4l2-ctl", "-d", "/dev/video0", "--get-ctrl=brightness"],
            text=True, timeout=2,
        )
        return int(out.strip().split(":")[-1].strip())
    except Exception:
        return None


def _write_brightness(val):
    try:
        subprocess.check_call(
            ["v4l2-ctl", "-d", "/dev/video0", f"--set-ctrl=brightness={val}"],
            timeout=2,
        )
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# ROS 2 node
# ---------------------------------------------------------------------------
class KtControlBridge(Node):
    def __init__(self):
        super().__init__("kt_control_bridge")

        # internal state
        self.enable_mcu_output = False
        self.emergency_stop = False
        self.control_mode = "disabled"
        self.manual_speed = 0.0
        self.manual_steering = 0.0
        self.radar_raw_distance = None
        self.radar_filtered_distance = None

        # publisher
        self.ackermann_pub = self.create_publisher(
            AckermannDrive, "/ackermann_cmd", 10
        )

        # subscriber — best-effort for laser
        qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.create_subscription(LaserScan, "/scan", self._on_scan, qos)

        self.get_logger().info(
            f"kt_control_bridge started, HTTP port {HTTP_PORT}"
        )

    # -- scan callback ------------------------------------------------------
    def _on_scan(self, msg: LaserScan):
        front_dist = self._extract_front_distance(msg)
        self.radar_raw_distance = front_dist
        if front_dist is None:
            return
        if self.radar_filtered_distance is None:
            self.radar_filtered_distance = front_dist
        else:
            self.radar_filtered_distance = (
                EMA_ALPHA * front_dist
                + (1.0 - EMA_ALPHA) * self.radar_filtered_distance
            )

    def _extract_front_distance(self, msg: LaserScan):
        half_win = math.radians(RADAR_FRONT_WINDOW_DEG)
        ranges = msg.ranges
        n = len(ranges)
        if n == 0:
            return None
        angle = msg.angle_min
        valid = []
        for i in range(n):
            if -half_win <= angle <= half_win:
                r = ranges[i]
                if msg.range_min <= r <= msg.range_max:
                    valid.append(r)
            angle += msg.angle_increment
        if not valid:
            return None
        return min(valid)

    # -- motion commands ----------------------------------------------------
    def safe_send_motion_command(self, speed, steering):
        if self.emergency_stop:
            self.get_logger().warn("drop motion: emergency_stop=True")
            return
        if not self.enable_mcu_output:
            self.get_logger().warn("drop motion: enable_mcu_output=False")
            return
        cmd = AckermannDrive()
        cmd.speed = float(speed)
        cmd.steering_angle = float(steering)
        self.ackermann_pub.publish(cmd)

    def send_stop_command(self, force=True):
        cmd = AckermannDrive()
        cmd.speed = 0.0
        cmd.steering_angle = 0.0
        self.ackermann_pub.publish(cmd)
        self.get_logger().info("stop command sent")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main():
    rclpy.init()
    node = KtControlBridge()

    # start HTTP server in a daemon thread
    ControlHTTPHandler.bridge = node
    httpd = HTTPServer(("0.0.0.0", HTTP_PORT), ControlHTTPHandler)
    http_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    http_thread.start()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        node.destroy_node()
        rclpy.try_shutdown()


if __name__ == "__main__":
    main()

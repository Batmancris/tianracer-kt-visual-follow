#!/usr/bin/env python3
"""
KT demo camera control bridge.

Bridges /kt_camera/control JSON messages to v4l2-ctl on /dev/video0.
"""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Optional

import rclpy
from rclpy.node import Node
from rclpy.qos import DurabilityPolicy, QoSProfile, ReliabilityPolicy
from std_msgs.msg import String


def clamp_int(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


class CameraControlBridge(Node):
    def __init__(self) -> None:
        super().__init__("kt_camera_control_bridge")
        qos = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.status_pub = self.create_publisher(String, "/kt_camera/status", qos)
        self.create_subscription(String, "/kt_camera/control", self._on_control, qos)
        self.worker_pool = ThreadPoolExecutor(max_workers=1)
        self.apply_lock = threading.Lock()
        self.pending_status: Optional[dict] = None
        self.status_timer = self.create_timer(0.1, self._flush_status)
        self.poll_timer = self.create_timer(1.0, self._poll_current_status)
        self.get_logger().info("kt_camera_control_bridge started")

    def _flush_status(self) -> None:
        with self.apply_lock:
            payload = self.pending_status
            self.pending_status = None
        if payload is None:
            return
        self.status_pub.publish(String(data=json.dumps(payload, ensure_ascii=True)))

    def _set_pending_status(self, payload: dict) -> None:
        with self.apply_lock:
            self.pending_status = payload

    def _parse_control_value(self, raw_line: str) -> Optional[int]:
        match = re.search(r"value=(-?\d+)", raw_line)
        if not match:
            return None
        try:
            return int(match.group(1))
        except ValueError:
            return None

    def _build_current_snapshot(self, controls: Dict[str, str]) -> dict:
        auto_mode = self._parse_control_value(controls.get("auto_exposure", ""))
        exposure = self._parse_control_value(controls.get("exposure_time_absolute", ""))
        if exposure is None:
            exposure = self._parse_control_value(controls.get("exposure_absolute", ""))
        if exposure is None:
            exposure = self._parse_control_value(controls.get("exposure", ""))
        return {
            "brightness": self._parse_control_value(controls.get("brightness", "")),
            "exposure": exposure,
            "auto_exposure": None if auto_mode is None else auto_mode not in (1,),
        }

    def _poll_current_status(self) -> None:
        controls = self._load_controls()
        if controls is None:
            self._set_pending_status({"ok": False, "message": "camera backend offline"})
            return
        self._set_pending_status(
            {
                "ok": True,
                "message": "camera status",
                "current": self._build_current_snapshot(controls),
            }
        )

    def _run_command(self, args: List[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=2.0,
            check=False,
        )

    def _load_controls(self) -> Optional[Dict[str, str]]:
        if shutil.which("v4l2-ctl") is None:
            return None
        try:
            result = self._run_command(["v4l2-ctl", "-d", "/dev/video0", "--list-ctrls"])
        except (subprocess.SubprocessError, OSError):
            return None
        if result.returncode != 0:
            return None

        controls: Dict[str, str] = {}
        for raw_line in result.stdout.splitlines():
            line = raw_line.strip()
            if not line or line.endswith("Controls"):
                continue
            name = line.split()[0]
            if name:
                controls[name] = line
        return controls

    def _apply_controls(self, msg_data: str) -> None:
        try:
            payload = json.loads(msg_data)
        except json.JSONDecodeError:
            self.get_logger().warn("invalid camera control json")
            self._set_pending_status({"ok": False, "message": "invalid json"})
            return

        if not isinstance(payload, dict):
            self._set_pending_status({"ok": False, "message": "invalid payload"})
            return

        controls = self._load_controls()
        if controls is None:
            self._set_pending_status({"ok": False, "message": "camera backend offline"})
            return

        applied: Dict[str, int] = {}
        unsupported: List[str] = []
        failed: List[str] = []

        if "brightness" in payload:
            if "brightness" not in controls:
                unsupported.append("brightness")
            else:
                try:
                    brightness = clamp_int(int(payload["brightness"]), -64, 64)
                    result = self._run_command(["v4l2-ctl", "-d", "/dev/video0", "-c", f"brightness={brightness}"])
                    if result.returncode == 0:
                        applied["brightness"] = brightness
                    else:
                        failed.append("brightness")
                except (TypeError, ValueError, subprocess.SubprocessError, OSError):
                    failed.append("brightness")

        auto_exposure_name = None
        for name in ("exposure_auto", "auto_exposure"):
            if name in controls:
                auto_exposure_name = name
                break

        exposure_name = None
        for name in ("exposure_absolute", "exposure_time_absolute", "exposure"):
            if name in controls:
                exposure_name = name
                break

        if "auto_exposure" in payload:
            if auto_exposure_name is None:
                unsupported.append("auto_exposure")
            else:
                try:
                    auto_exposure = bool(payload["auto_exposure"])
                    value = 1 if auto_exposure else 0
                    if auto_exposure_name == "auto_exposure":
                        value = 3 if auto_exposure else 1
                    result = self._run_command(
                        ["v4l2-ctl", "-d", "/dev/video0", "-c", f"{auto_exposure_name}={value}"]
                    )
                    if result.returncode == 0:
                        applied[auto_exposure_name] = value
                    else:
                        failed.append(auto_exposure_name)
                except (subprocess.SubprocessError, OSError):
                    failed.append(auto_exposure_name)

        if "exposure" in payload:
            if exposure_name is None:
                unsupported.append("exposure")
            else:
                try:
                    exposure = clamp_int(int(payload["exposure"]), 1, 5000)
                    result = self._run_command(
                        ["v4l2-ctl", "-d", "/dev/video0", "-c", f"{exposure_name}={exposure}"]
                    )
                    if result.returncode == 0:
                        applied[exposure_name] = exposure
                    else:
                        failed.append(exposure_name)
                except (TypeError, ValueError, subprocess.SubprocessError, OSError):
                    failed.append(exposure_name)

        ok = bool(applied) and not failed
        if not applied and not unsupported and not failed:
            message = "no supported fields"
        elif failed:
            message = "failed"
        elif unsupported:
            message = "unsupported control"
        else:
            message = "camera controls applied"

        refreshed_controls = self._load_controls() or controls
        self._set_pending_status(
            {
                "ok": ok,
                "applied": applied,
                "unsupported": unsupported,
                "failed": failed,
                "message": message,
                "current": self._build_current_snapshot(refreshed_controls),
            }
        )

    def _on_control(self, msg: String) -> None:
        self.worker_pool.submit(self._apply_controls, msg.data)

    def destroy_node(self) -> bool:
        self.worker_pool.shutdown(wait=False, cancel_futures=True)
        return super().destroy_node()


def main() -> int:
    rclpy.init()
    node = CameraControlBridge()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""
KT demo production follow controller v4.

Formal control chain:
  /kt_follow/mode + /bear_detection/targets + /tianracer/scan -> /ackermann_cmd

Legacy debug-string inputs are intentionally not used here.
"""

from __future__ import annotations

import argparse
import json
import math
import signal
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import rclpy
from ackermann_msgs.msg import AckermannDrive
from ai_msgs.msg import PerceptionTargets
from rclpy.node import Node
from rclpy.qos import (
    DurabilityPolicy,
    QoSProfile,
    ReliabilityPolicy,
)
from sensor_msgs.msg import LaserScan
from std_msgs.msg import String

try:
    from rclpy.qos import SensorDataQoS
except ImportError:
    from rclpy.qos import qos_profile_sensor_data

    def make_sensor_data_qos() -> QoSProfile:
        return qos_profile_sensor_data
else:
    def make_sensor_data_qos() -> QoSProfile:
        return SensorDataQoS()


def clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def smoothstep(x: float) -> float:
    x = clamp(x, 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def rate_limit(current: float, target: float, rise_limit: float, fall_limit: float, dt: float) -> float:
    if target >= current:
        return min(current + rise_limit * dt, target)
    return max(current - fall_limit * dt, target)


@dataclass
class ControllerConfig:
    enable_control: bool = False
    scan_topic: str = "/tianracer/scan"
    image_width: float = 640.0
    image_center_x: float = 320.0
    horizontal_fov_deg: float = 70.0
    min_confidence: float = 0.5
    angle_window_deg: float = 8.0
    scan_range_min: float = 0.15
    scan_range_max: float = 3.0
    target_distance_m: float = 1.0
    stop_distance_m: float = 1.0
    full_speed_distance_m: float = 1.6
    max_speed: float = 0.25
    max_steering_angle: float = 0.18
    k_steer: float = 0.85
    steer_sign: float = -1.0
    theta_deadband: float = 0.025
    theta_filter_alpha: float = 0.35
    dist_filter_alpha: float = 0.30
    target_grace_sec: float = 0.25
    stale_stop_sec: float = 0.45
    max_accel: float = 0.60
    max_decel: float = 1.20
    max_steer_rate: float = 0.60
    loop_hz: float = 20.0


@dataclass
class ScanWindow:
    angle_min: float
    angle_increment: float
    ranges: Sequence[float]


@dataclass
class ScanDistanceResult:
    distance: Optional[float]
    valid_scan_pts: int
    samples: List[float] = field(default_factory=list)


@dataclass
class ControllerState:
    mode: str = "OFF"
    last_mode: str = "OFF"
    mode_stop_sent: bool = False
    theta_filtered: float = 0.0
    theta_filter_inited: bool = False
    dist_filtered: Optional[float] = None
    dist_filter_inited: bool = False
    speed_cmd: float = 0.0
    steering_cmd: float = 0.0


@dataclass
class FollowDecision:
    speed_cmd: float
    steer_cmd: float
    reason: str
    publishing: bool


@dataclass
class StatusSnapshot:
    reason: str = "mode=OFF"
    publishing: bool = False


def percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires non-empty input")
    index = int(math.floor((len(sorted_values) - 1) * q))
    return sorted_values[index]


def select_bear_target(detections: Iterable[Any], min_confidence: float) -> Optional[dict]:
    best: Optional[dict] = None
    best_area = -1.0
    for item in detections:
        target_type = None
        rois: Sequence[Any] = ()
        if isinstance(item, dict):
            target_type = item.get("type")
            if "rois" in item:
                rois = item.get("rois") or []
            else:
                rois = [item]
        else:
            target_type = getattr(item, "type", None)
            rois = getattr(item, "rois", []) or []

        if target_type != "bear":
            continue

        for roi in rois:
            if isinstance(roi, dict):
                confidence = float(roi.get("confidence", 0.0))
                x_offset = float(roi.get("x_offset", 0.0))
                y_offset = float(roi.get("y_offset", 0.0))
                width = float(roi.get("width", 0.0))
                height = float(roi.get("height", 0.0))
            else:
                confidence = float(getattr(roi, "confidence", 0.0))
                rect = getattr(roi, "rect", roi)
                x_offset = float(getattr(rect, "x_offset", 0.0))
                y_offset = float(getattr(rect, "y_offset", 0.0))
                width = float(getattr(rect, "width", 0.0))
                height = float(getattr(rect, "height", 0.0))

            if confidence < min_confidence:
                continue

            area = width * height
            if area > best_area:
                best_area = area
                best = {
                    "type": "bear",
                    "confidence": confidence,
                    "x_offset": x_offset,
                    "y_offset": y_offset,
                    "width": width,
                    "height": height,
                    "roi_cx": x_offset + width * 0.5,
                    "roi_cy": y_offset + height * 0.5,
                }
    return best


def compute_theta_raw(roi_cx: float, image_width: float, horizontal_fov_deg: float) -> float:
    center_x = image_width * 0.5
    fx = image_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) * 0.5))
    return math.atan2(roi_cx - center_x, fx)


def compute_image_theta_limits(image_width: float, horizontal_fov_deg: float) -> Tuple[float, float]:
    return (
        compute_theta_raw(0.0, image_width, horizontal_fov_deg),
        compute_theta_raw(image_width, image_width, horizontal_fov_deg),
    )


def collect_scan_samples(
    scan: ScanWindow,
    theta_raw: float,
    half_window_rad: float,
    range_min: float,
    range_max: float,
) -> List[float]:
    samples: List[float] = []
    for idx, value in enumerate(scan.ranges):
        angle = scan.angle_min + idx * scan.angle_increment
        if abs(angle - theta_raw) > half_window_rad:
            continue
        if not math.isfinite(value):
            continue
        if value < range_min or value > range_max:
            continue
        samples.append(float(value))
    return samples


def extract_scan_distance(
    scan: ScanWindow,
    theta_raw: float,
    angle_window_deg: float,
    range_min: float,
    range_max: float,
) -> ScanDistanceResult:
    half_window = math.radians(angle_window_deg)
    samples = collect_scan_samples(scan, theta_raw, half_window, range_min, range_max)
    if not samples:
        fallback_half_window = math.radians(max(angle_window_deg * 2.5, angle_window_deg + 6.0))
        samples = collect_scan_samples(scan, theta_raw, fallback_half_window, range_min, range_max)

    if not samples:
        return ScanDistanceResult(distance=None, valid_scan_pts=0, samples=[])

    samples.sort()
    median = samples[len(samples) // 2]
    low_tail = percentile(samples, 0.2)
    return ScanDistanceResult(distance=min(median, low_tail), valid_scan_pts=len(samples), samples=samples)


def compute_follow_step(
    state: ControllerState,
    config: ControllerConfig,
    mode: str,
    now: float,
    target_theta: Optional[float],
    target_distance: Optional[float],
    valid_scan_pts: int,
    target_is_fresh: bool,
    scan_is_fresh: bool,
    dt: float,
) -> FollowDecision:
    should_compute = mode == "FOLLOW"
    should_publish = config.enable_control and should_compute
    reason = "mode_off"

    if target_theta is not None and abs(target_theta) < config.theta_deadband:
        theta_used = 0.0
    else:
        theta_used = target_theta

    if theta_used is not None:
        if not state.theta_filter_inited:
            state.theta_filtered = theta_used
            state.theta_filter_inited = True
        else:
            state.theta_filtered = (
                config.theta_filter_alpha * theta_used
                + (1.0 - config.theta_filter_alpha) * state.theta_filtered
            )

    if target_distance is not None:
        if not state.dist_filter_inited:
            state.dist_filtered = target_distance
            state.dist_filter_inited = True
        else:
            state.dist_filtered = (
                config.dist_filter_alpha * target_distance
                + (1.0 - config.dist_filter_alpha) * state.dist_filtered
            )

    speed_target = 0.0
    steering_target = 0.0

    if not should_compute:
        reason = f"mode={mode}"
    elif not target_is_fresh:
        reason = "target_stale"
    elif not scan_is_fresh:
        reason = "scan_stale"
    elif target_theta is None:
        reason = "no_bear"
    elif target_distance is None:
        reason = "no_scan"
    elif valid_scan_pts <= 0:
        reason = "no_valid_scan"
    else:
        reason = "ok"
        if state.dist_filtered is None or state.dist_filtered <= config.stop_distance_m:
            speed_target = 0.0
        elif state.dist_filtered >= config.full_speed_distance_m:
            speed_target = config.max_speed
        else:
            x = (state.dist_filtered - config.stop_distance_m) / (
                config.full_speed_distance_m - config.stop_distance_m
            )
            speed_target = config.max_speed * smoothstep(x)

        steering_target = clamp(
            config.steer_sign * config.k_steer * state.theta_filtered,
            -config.max_steering_angle,
            config.max_steering_angle,
        )

    state.speed_cmd = rate_limit(state.speed_cmd, speed_target, config.max_accel, config.max_decel, dt)
    state.steering_cmd = rate_limit(
        state.steering_cmd,
        steering_target,
        config.max_steer_rate,
        config.max_steer_rate,
        dt,
    )

    if reason != "ok":
        state.steering_cmd = rate_limit(
            state.steering_cmd,
            0.0,
            config.max_steer_rate,
            config.max_steer_rate,
            dt,
        )
        state.speed_cmd = 0.0

    state.speed_cmd = clamp(state.speed_cmd, 0.0, config.max_speed)
    state.steering_cmd = clamp(
        state.steering_cmd,
        -config.max_steering_angle,
        config.max_steering_angle,
    )

    return FollowDecision(
        speed_cmd=state.speed_cmd,
        steer_cmd=state.steering_cmd,
        reason=reason,
        publishing=should_publish,
    )


class FollowControllerV4(Node):
    VALID_MODES = ("FOLLOW", "MANUAL", "OFF")

    def __init__(self, config: ControllerConfig):
        super().__init__("kt_follow_controller_v4")
        self.config = config
        self.state = ControllerState()
        self.start_time = time.time()
        self.stop_requested = False
        self.last_log_time = 0.0

        self.current_target: Optional[dict] = None
        self.current_theta_raw: Optional[float] = None
        self.current_dist_raw: Optional[float] = None
        self.current_valid_scan_pts: int = 0
        self.last_target_time = 0.0
        self.last_scan_time = 0.0
        self.last_scan_angle_min: Optional[float] = None
        self.last_scan_angle_max: Optional[float] = None
        self.last_scan_angle_increment: Optional[float] = None
        self.last_scan_count: int = 0
        self.status_snapshot = StatusSnapshot()

        qos_reliable = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.RELIABLE,
            durability=DurabilityPolicy.VOLATILE,
        )

        self.cmd_pub = self.create_publisher(AckermannDrive, "/ackermann_cmd", qos_reliable)
        self.tuning_status_pub = self.create_publisher(String, "/kt_follow/tuning_status", qos_reliable)
        self.status_pub = self.create_publisher(String, "/kt_follow/status", qos_reliable)
        self.create_subscription(String, "/kt_follow/mode", self._on_mode, qos_reliable)
        self.create_subscription(String, "/kt_follow/tuning", self._on_tuning, qos_reliable)
        self.create_subscription(PerceptionTargets, "/bear_detection/targets", self._on_targets, make_sensor_data_qos())
        self.create_subscription(LaserScan, self.config.scan_topic, self._on_scan, make_sensor_data_qos())

        self.loop_dt = 1.0 / self.config.loop_hz
        self.timer = self.create_timer(self.loop_dt, self._control_loop)
        self.status_timer = self.create_timer(0.2, self._publish_status)

        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

        self.get_logger().info(
            "kt_follow_controller_v4 started enable_control=%s scan_topic=%s max_speed=%.2f max_steering_angle=%.2f"
            % (
                self.config.enable_control,
                self.config.scan_topic,
                self.config.max_speed,
                self.config.max_steering_angle,
            )
        )

    def _on_mode(self, msg: String) -> None:
        new_mode = msg.data.strip().upper()
        if new_mode not in self.VALID_MODES:
            self.get_logger().warn("ignoring invalid mode '%s'" % msg.data.strip())
            return
        if new_mode != self.state.mode:
            self.state.last_mode = self.state.mode
            self.state.mode = new_mode
            self.state.mode_stop_sent = False
            self.state.speed_cmd = 0.0
            self.get_logger().info("mode changed %s -> %s" % (self.state.last_mode, self.state.mode))

    def _on_targets(self, msg: PerceptionTargets) -> None:
        target = select_bear_target(msg.targets, self.config.min_confidence)
        self.current_target = target
        if target is None:
            self.current_theta_raw = None
            return
        self.current_theta_raw = compute_theta_raw(
            roi_cx=target["roi_cx"],
            image_width=self.config.image_width,
            horizontal_fov_deg=self.config.horizontal_fov_deg,
        )
        self.last_target_time = time.time()

    def _on_scan(self, msg: LaserScan) -> None:
        self.last_scan_time = time.time()
        self.last_scan_angle_min = float(msg.angle_min)
        self.last_scan_angle_max = float(msg.angle_max)
        self.last_scan_angle_increment = float(msg.angle_increment)
        self.last_scan_count = len(msg.ranges)
        if self.current_theta_raw is None:
            self.current_dist_raw = None
            self.current_valid_scan_pts = 0
            return

        result = extract_scan_distance(
            ScanWindow(angle_min=msg.angle_min, angle_increment=msg.angle_increment, ranges=msg.ranges),
            theta_raw=self.current_theta_raw,
            angle_window_deg=self.config.angle_window_deg,
            range_min=self.config.scan_range_min,
            range_max=self.config.scan_range_max,
        )
        self.current_dist_raw = result.distance
        self.current_valid_scan_pts = result.valid_scan_pts

    def _publish_tuning_status(self, ok: bool, message: str) -> None:
        payload = {
            "ok": ok,
            "max_speed": round(self.config.max_speed, 3),
            "max_steering_angle": round(self.config.max_steering_angle, 3),
            "stop_distance_m": round(self.config.stop_distance_m, 3),
            "full_speed_distance_m": round(self.config.full_speed_distance_m, 3),
            "message": message,
        }
        self.tuning_status_pub.publish(String(data=json.dumps(payload, ensure_ascii=True)))

    def _on_tuning(self, msg: String) -> None:
        try:
            payload = json.loads(msg.data)
        except json.JSONDecodeError:
            self.get_logger().warn("ignoring invalid tuning json")
            self._publish_tuning_status(False, "invalid json")
            return

        if not isinstance(payload, dict):
            self.get_logger().warn("ignoring tuning payload that is not an object")
            self._publish_tuning_status(False, "invalid payload")
            return

        updated = False
        proposed_values = {
            "max_speed": self.config.max_speed,
            "max_steering_angle": self.config.max_steering_angle,
            "stop_distance_m": self.config.stop_distance_m,
            "full_speed_distance_m": self.config.full_speed_distance_m,
        }
        for field_name, low, high in (
            ("max_speed", 0.0, 0.6),
            ("max_steering_angle", 0.0, 1.0),
            ("stop_distance_m", 0.2, 1.5),
            ("full_speed_distance_m", 0.3, 3.0),
        ):
            if field_name not in payload:
                continue
            try:
                value = float(payload[field_name])
            except (TypeError, ValueError):
                self.get_logger().warn("ignoring invalid tuning value for %s" % field_name)
                self._publish_tuning_status(False, "invalid %s" % field_name)
                return
            proposed_values[field_name] = clamp(value, low, high)
            updated = True

        if not updated:
            self._publish_tuning_status(False, "no supported fields")
            return

        if proposed_values["full_speed_distance_m"] <= proposed_values["stop_distance_m"]:
            self._publish_tuning_status(False, "full_speed_distance_m must be greater than stop_distance_m")
            return

        self.config.max_speed = proposed_values["max_speed"]
        self.config.max_steering_angle = proposed_values["max_steering_angle"]
        self.config.stop_distance_m = proposed_values["stop_distance_m"]
        self.config.full_speed_distance_m = proposed_values["full_speed_distance_m"]

        self.get_logger().info(
            "tuning updated: max_speed=%.2f max_steering_angle=%.2f stop_distance_m=%.2f full_speed_distance_m=%.2f"
            % (
                self.config.max_speed,
                self.config.max_steering_angle,
                self.config.stop_distance_m,
                self.config.full_speed_distance_m,
            )
        )
        self._publish_tuning_status(True, "updated")

    def _publish_stop(self, count: int) -> None:
        cmd = AckermannDrive()
        cmd.speed = 0.0
        cmd.steering_angle = 0.0
        for _ in range(count):
            self.cmd_pub.publish(cmd)
            time.sleep(0.05)
        self.state.speed_cmd = 0.0
        self.state.steering_cmd = 0.0

    def _request_stop(self) -> None:
        if self.stop_requested:
            return
        self.stop_requested = True
        try:
            self.timer.cancel()
        except Exception:
            pass
        self._publish_stop(10)

    def _sig_handler(self, *_args) -> None:
        self.get_logger().warn("signal received, stop x10")
        self._request_stop()
        raise SystemExit(0)

    def _age_ms(self, last_time: float, now: float) -> Optional[int]:
        if last_time <= 0.0:
            return None
        return max(0, int(round((now - last_time) * 1000.0)))

    def _publish_status(self) -> None:
        now = time.time()
        target = self.current_target
        image_theta_left, image_theta_right = compute_image_theta_limits(
            self.config.image_width,
            self.config.horizontal_fov_deg,
        )
        payload = {
            "mode": self.state.mode,
            "scan_topic": self.config.scan_topic,
            "roi_cx": None if target is None else round(float(target["roi_cx"]), 1),
            "roi_cy": None if target is None else round(float(target["roi_cy"]), 1),
            "theta_raw": None if self.current_theta_raw is None else round(float(self.current_theta_raw), 4),
            "theta_filt": None if not self.state.theta_filter_inited else round(float(self.state.theta_filtered), 4),
            "image_theta_left_deg": round(math.degrees(image_theta_left), 2),
            "image_theta_right_deg": round(math.degrees(image_theta_right), 2),
            "dist_raw": None if self.current_dist_raw is None else round(float(self.current_dist_raw), 4),
            "dist_filt": None if not self.state.dist_filter_inited or self.state.dist_filtered is None else round(float(self.state.dist_filtered), 4),
            "valid_scan_pts": int(self.current_valid_scan_pts),
            "stop_distance_m": round(float(self.config.stop_distance_m), 3),
            "full_speed_distance_m": round(float(self.config.full_speed_distance_m), 3),
            "scan_angle_min_deg": None if self.last_scan_angle_min is None else round(math.degrees(self.last_scan_angle_min), 2),
            "scan_angle_max_deg": None if self.last_scan_angle_max is None else round(math.degrees(self.last_scan_angle_max), 2),
            "scan_angle_increment_deg": None if self.last_scan_angle_increment is None else round(math.degrees(self.last_scan_angle_increment), 4),
            "scan_range_count": int(self.last_scan_count),
            "speed_cmd": round(float(self.state.speed_cmd), 4),
            "steer_cmd": round(float(self.state.steering_cmd), 4),
            "reason": self.status_snapshot.reason,
            "publishing": bool(self.status_snapshot.publishing),
            "max_speed": round(float(self.config.max_speed), 3),
            "max_steering_angle": round(float(self.config.max_steering_angle), 3),
            "target_age_ms": self._age_ms(self.last_target_time, now),
            "scan_age_ms": self._age_ms(self.last_scan_time, now),
        }
        self.status_pub.publish(String(data=json.dumps(payload, ensure_ascii=True)))

    def _control_loop(self) -> None:
        if self.stop_requested:
            return

        now = time.time()

        if self.state.mode == "MANUAL" and not self.state.mode_stop_sent:
            self.get_logger().info("MANUAL stop x5 then release")
            self._publish_stop(5)
            self.state.mode_stop_sent = True
        elif self.state.mode == "OFF" and not self.state.mode_stop_sent:
            self.get_logger().info("OFF stop x10 then release")
            self._publish_stop(10)
            self.state.mode_stop_sent = True

        target_fresh = (now - self.last_target_time) < self.config.target_grace_sec
        scan_fresh = (now - self.last_scan_time) < self.config.stale_stop_sec

        decision = compute_follow_step(
            state=self.state,
            config=self.config,
            mode=self.state.mode,
            now=now,
            target_theta=self.current_theta_raw,
            target_distance=self.current_dist_raw,
            valid_scan_pts=self.current_valid_scan_pts,
            target_is_fresh=target_fresh,
            scan_is_fresh=scan_fresh,
            dt=self.loop_dt,
        )
        self.status_snapshot = StatusSnapshot(
            reason=decision.reason,
            publishing=decision.publishing,
        )

        if decision.publishing:
            cmd = AckermannDrive()
            cmd.speed = float(decision.speed_cmd)
            cmd.steering_angle = float(decision.steer_cmd)
            self.cmd_pub.publish(cmd)

        if now - self.last_log_time >= 1.0:
            self.last_log_time = now
            roi_cx = self.current_target["roi_cx"] if self.current_target else None
            theta_raw = self.current_theta_raw
            dist_raw = self.current_dist_raw
            self.get_logger().info(
                "mode=%s roi_cx=%s theta_raw=%s theta_filt=%.3f dist_raw=%s dist_filt=%s valid_scan_pts=%d speed_cmd=%.3f steer_cmd=%.3f reason=%s publishing=%s"
                % (
                    self.state.mode,
                    "None" if roi_cx is None else "%.1f" % roi_cx,
                    "None" if theta_raw is None else "%.3f" % theta_raw,
                    self.state.theta_filtered,
                    "None" if dist_raw is None else "%.3f" % dist_raw,
                    "None" if self.state.dist_filtered is None else "%.3f" % self.state.dist_filtered,
                    self.current_valid_scan_pts,
                    decision.speed_cmd,
                    decision.steer_cmd,
                    decision.reason,
                    decision.publishing,
                )
            )


def parse_args(argv: Sequence[str]) -> ControllerConfig:
    parser = argparse.ArgumentParser(description="KT demo follow controller v4")
    parser.add_argument("--enable-control", type=str, default="false")
    parser.add_argument("--scan-topic", type=str, default="/tianracer/scan")
    parser.add_argument("--target-distance-m", type=float, default=1.0)
    parser.add_argument("--stop-distance-m", type=float, default=1.0)
    parser.add_argument("--full-speed-distance-m", type=float, default=1.6)
    parser.add_argument("--max-speed", type=float, default=0.25)
    parser.add_argument("--max-steering-angle", type=float, default=0.18)
    parser.add_argument("--max-accel", type=float, default=0.60)
    parser.add_argument("--max-decel", type=float, default=1.20)
    parser.add_argument("--max-steer-rate", type=float, default=0.60)
    parser.add_argument("--theta-deadband", type=float, default=0.025)
    parser.add_argument("--theta-filter-alpha", type=float, default=0.35)
    parser.add_argument("--dist-filter-alpha", type=float, default=0.30)
    parser.add_argument("--target-grace-sec", type=float, default=0.25)
    parser.add_argument("--stale-stop-sec", type=float, default=0.45)
    parser.add_argument("--angle-window-deg", type=float, default=8.0)
    args = parser.parse_args(argv)

    return ControllerConfig(
        enable_control=args.enable_control.lower() in ("1", "true", "yes"),
        scan_topic=args.scan_topic,
        target_distance_m=args.target_distance_m,
        stop_distance_m=args.stop_distance_m,
        full_speed_distance_m=args.full_speed_distance_m,
        max_speed=args.max_speed,
        max_steering_angle=args.max_steering_angle,
        max_accel=args.max_accel,
        max_decel=args.max_decel,
        max_steer_rate=args.max_steer_rate,
        theta_deadband=args.theta_deadband,
        theta_filter_alpha=args.theta_filter_alpha,
        dist_filter_alpha=args.dist_filter_alpha,
        target_grace_sec=args.target_grace_sec,
        stale_stop_sec=args.stale_stop_sec,
        angle_window_deg=args.angle_window_deg,
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    config = parse_args(sys.argv[1:] if argv is None else argv)
    rclpy.init()
    node = FollowControllerV4(config)
    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        node._request_stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

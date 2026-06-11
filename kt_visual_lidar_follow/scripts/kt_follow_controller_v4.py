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
from enum import Enum
from typing import Any, Iterable, List, Optional, Sequence, Tuple

import rclpy
from ackermann_msgs.msg import AckermannDrive
from ai_msgs.msg import PerceptionTargets
from nav_msgs.msg import Odometry
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
    odom_topic: str = "/odom"
    ackermann_cmd_topic: str = "/ackermann_cmd"
    targets_topic: str = "/bear_detection/targets"
    image_width: float = 640.0
    image_center_x: float = 320.0
    horizontal_fov_deg: float = 70.0
    min_confidence: float = 0.5
    angle_window_deg: float = 8.0
    scan_range_min: float = 0.15
    scan_range_max: float = 3.0
    target_distance_m: float = 0.5
    restart_distance_m: float = 0.7
    stop_distance_m: float = 0.5
    full_speed_distance_m: float = 1.6
    max_speed: float = 0.25
    min_effective_speed_mps: float = 0.30
    slow_speed_mps: float = 0.35
    fast_speed_mps: float = 0.50
    stop_decel_mps2: float = 0.80
    stop_margin_m: float = 0.08
    max_valid_odom_age_ms: int = 200
    max_valid_range_age_ms: int = 200
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

    # --- v4.1: robust lidar sector search ---
    lidar_search_half_angle_rad: float = 0.24
    lidar_min_valid_points: int = 3
    lidar_range_percentile: float = 0.20
    lidar_hold_ms: int = 250
    turn_slow_angle_rad: float = 0.18
    turn_stop_angle_rad: float = 0.30
    turn_speed_cap: float = 0.22

    # --- v4.2: camera-lidar sector fusion ---
    min_sector_half_angle_rad: float = 0.16
    max_sector_half_angle_rad: float = 0.45
    sector_extra_margin_rad: float = 0.08
    camera_lidar_yaw_offset_rad: float = 0.0
    cluster_range_jump_m: float = 0.25
    cluster_min_points: int = 3
    max_search_half_angle_rad: float = 0.60

    # --- v4.3: bbox depth prior + track continuity gating ---
    bear_width_m: float = 0.25
    bbox_depth_gate_m: float = 0.65
    bbox_depth_gate_ratio: float = 0.65
    track_range_gate_m: float = 0.40
    track_angle_gate_rad: float = 0.25
    track_gate_grace_sec: float = 0.5

    # --- v4.4: target-aware camera-lidar association ---
    association_angle_weight: float = 1.0
    association_depth_weight: float = 0.8
    association_track_range_weight: float = 0.6
    association_track_angle_weight: float = 0.5
    association_max_angle_err_rad: float = 0.35
    association_max_depth_err_m: float = 0.60
    association_max_depth_err_ratio: float = 0.70
    association_max_track_range_jump_m: float = 0.50
    association_max_track_angle_jump_rad: float = 0.35


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
class LidarCluster:
    points: int = 0
    angle_min: float = 0.0
    angle_max: float = 0.0
    angle_center: float = 0.0
    range_median: float = 0.0
    range_p20: float = 0.0
    range_min: float = 0.0
    width_angle: float = 0.0


@dataclass
class SectorFusionResult:
    distance: Optional[float]
    valid_scan_pts: int
    cluster_count: int
    selected_cluster: Optional[LidarCluster]
    sector_points: int
    reason: str = ""
    sector_center: float = 0.0
    sector_half_angle: float = 0.0
    clusters_dbg: str = ""
    bbox_depth_m: Optional[float] = None
    bbox_depth_err: Optional[float] = None
    selected_cluster_reject_reason: str = ""
    selected_cluster_reason: str = ""
    selected_cluster_score: float = 0.0
    # v4.4: target-aware association
    lidar_target_state: str = "no_vision_target"
    association_score: float = 0.0
    association_reject_reason: str = ""
    association_candidates: int = 0
    selected_cluster_range: Optional[float] = None
    selected_cluster_angle: Optional[float] = None
    association_dbg: str = ""


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
    longitudinal_state: str = "IDLE"
    last_valid_range: Optional[float] = None
    last_valid_range_time: float = 0.0
    range_source: str = "invalid"
    range_hold_age_ms: Optional[int] = None
    last_cluster_angle: Optional[float] = None
    last_cluster_range: Optional[float] = None
    last_cluster_time: float = 0.0


@dataclass
class FollowDecision:
    speed_cmd: float
    steer_cmd: float
    reason: str
    publishing: bool


class LongitudinalState(str, Enum):
    IDLE = "IDLE"
    APPROACH_FAST = "APPROACH_FAST"
    APPROACH_SLOW = "APPROACH_SLOW"
    BRAKE = "BRAKE"
    HOLD = "HOLD"


class RangeSource(str, Enum):
    CURRENT = "current"
    HOLD = "hold"
    INVALID = "invalid"


@dataclass
class LongitudinalDecision:
    state: LongitudinalState
    cmd_speed: float
    range_m: Optional[float]
    v_odom: float
    s_remain: Optional[float]
    s_stop: Optional[float]


@dataclass
class StatusSnapshot:
    reason: str = "mode=OFF"
    publishing: bool = False
    range_source: str = "invalid"
    range_hold_age_ms: Optional[int] = None


def percentile(sorted_values: Sequence[float], q: float) -> float:
    if not sorted_values:
        raise ValueError("percentile requires non-empty input")
    index = int(math.floor((len(sorted_values) - 1) * q))
    return sorted_values[index]


def longitudinal_speed_limit(config: ControllerConfig) -> float:
    return max(
        float(config.max_speed),
        float(config.min_effective_speed_mps),
        float(config.slow_speed_mps),
        float(config.fast_speed_mps),
    )


def normalize_positive_speed(speed: float, min_effective_speed_mps: float) -> float:
    if speed <= 0.0:
        return 0.0
    if speed < min_effective_speed_mps:
        return float(min_effective_speed_mps)
    return float(speed)


def enforce_speed_deadband(speed_cmd: float, speed_target: float, min_effective_speed_mps: float) -> float:
    if speed_cmd <= 0.0 or min_effective_speed_mps <= 0.0:
        return max(0.0, float(speed_cmd))
    if speed_cmd < min_effective_speed_mps:
        if speed_target > 0.0:
            return float(min_effective_speed_mps)
        return 0.0
    return float(speed_cmd)


def compute_longitudinal_step(
    current_state: LongitudinalState,
    config: ControllerConfig,
    range_m: Optional[float],
    v_odom: Optional[float],
    range_is_valid: bool,
    odom_is_fresh: bool,
) -> LongitudinalDecision:
    if (
        not range_is_valid
        or range_m is None
        or not math.isfinite(range_m)
        or range_m < config.scan_range_min
        or range_m > config.scan_range_max
        or v_odom is None
        or not math.isfinite(v_odom)
        or not odom_is_fresh
    ):
        return LongitudinalDecision(
            state=LongitudinalState.IDLE,
            cmd_speed=0.0,
            range_m=range_m,
            v_odom=0.0 if v_odom is None or not math.isfinite(v_odom) else abs(float(v_odom)),
            s_remain=None,
            s_stop=None,
        )

    v_odom = abs(float(v_odom))
    s_remain = float(range_m) - float(config.target_distance_m)
    stop_decel_mps2 = max(float(config.stop_decel_mps2), 1e-6)
    s_stop = (v_odom * v_odom) / (2.0 * stop_decel_mps2) + float(config.stop_margin_m)

    if current_state == LongitudinalState.HOLD and range_m < config.restart_distance_m:
        return LongitudinalDecision(
            state=LongitudinalState.HOLD,
            cmd_speed=0.0,
            range_m=float(range_m),
            v_odom=v_odom,
            s_remain=s_remain,
            s_stop=s_stop,
        )

    if s_remain <= 0.0:
        return LongitudinalDecision(
            state=LongitudinalState.HOLD,
            cmd_speed=0.0,
            range_m=float(range_m),
            v_odom=v_odom,
            s_remain=s_remain,
            s_stop=s_stop,
        )

    if s_remain <= s_stop:
        return LongitudinalDecision(
            state=LongitudinalState.BRAKE,
            cmd_speed=0.0,
            range_m=float(range_m),
            v_odom=v_odom,
            s_remain=s_remain,
            s_stop=s_stop,
        )

    if range_m > (config.target_distance_m + 1.0):
        return LongitudinalDecision(
            state=LongitudinalState.APPROACH_FAST,
            cmd_speed=normalize_positive_speed(config.fast_speed_mps, config.min_effective_speed_mps),
            range_m=float(range_m),
            v_odom=v_odom,
            s_remain=s_remain,
            s_stop=s_stop,
        )

    return LongitudinalDecision(
        state=LongitudinalState.APPROACH_SLOW,
        cmd_speed=normalize_positive_speed(config.slow_speed_mps, config.min_effective_speed_mps),
        range_m=float(range_m),
        v_odom=v_odom,
        s_remain=s_remain,
        s_stop=s_stop,
    )


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
    q: float = 0.2,
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
    lidar_search_half_angle_rad: float = 0.24,
    lidar_min_valid_points: int = 3,
    lidar_range_percentile: float = 0.20,
) -> ScanDistanceResult:
    """Extract lidar range from a wide sector centered on theta_raw.

    Uses lidar_search_half_angle_rad as the primary search half-angle.
    Falls back to a wider window (2.5x) if primary has too few points.
    Requires lidar_min_valid_points for a valid measurement.
    Uses lidar_range_percentile for robust distance selection.
    """
    samples = collect_scan_samples(scan, theta_raw, lidar_search_half_angle_rad, range_min, range_max)
    fallback_half_window = math.radians(max(angle_window_deg * 2.5, angle_window_deg + 6.0))
    if len(samples) < lidar_min_valid_points:
        samples = collect_scan_samples(scan, theta_raw, fallback_half_window, range_min, range_max)

    if len(samples) < lidar_min_valid_points:
        return ScanDistanceResult(distance=None, valid_scan_pts=len(samples), samples=samples)

    samples.sort()
    dist = percentile(samples, lidar_range_percentile)
    return ScanDistanceResult(distance=dist, valid_scan_pts=len(samples), samples=samples)


def compute_sector_fusion(
    scan: ScanWindow,
    theta_cam_center: float,
    target_width: Optional[float],
    image_width: float,
    horizontal_fov_deg: float,
    range_min: float,
    range_max: float,
    min_sector_half_angle_rad: float,
    max_sector_half_angle_rad: float,
    sector_extra_margin_rad: float,
    camera_lidar_yaw_offset_rad: float,
    cluster_range_jump_m: float,
    cluster_min_points: int,
    lidar_min_valid_points: int,
    last_cluster_angle: Optional[float],
    last_cluster_range: Optional[float],
    last_cluster_time: float = 0.0,
    now: float = 0.0,
    lidar_search_half_angle_rad: float = 0.24,
    max_search_half_angle_rad: float = 0.60,
    bear_width_m: float = 0.25,
    track_gate_grace_sec: float = 0.5,
    association_angle_weight: float = 1.0,
    association_depth_weight: float = 0.8,
    association_track_range_weight: float = 0.6,
    association_track_angle_weight: float = 0.5,
    association_max_angle_err_rad: float = 0.35,
    association_max_depth_err_m: float = 0.60,
    association_max_depth_err_ratio: float = 0.70,
    association_max_track_range_jump_m: float = 0.50,
    association_max_track_angle_jump_rad: float = 0.35,
) -> SectorFusionResult:
    """Compute camera-lidar sector fusion with cluster selection."""

    # 1. Compute sector half angle from target bbox angular width
    if target_width is not None and target_width > 0 and image_width > 0:
        # Compute angular width of target using pinhole model
        fx = image_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) * 0.5))
        half_angular_width = math.atan(target_width / (2.0 * fx))
        sector_half_angle = clamp(half_angular_width, min_sector_half_angle_rad, max_sector_half_angle_rad)
    else:
        # Fallback: use lidar search window minus margin, clamped to safe bounds
        fallback_half_angle = max(
            min_sector_half_angle_rad,
            lidar_search_half_angle_rad - sector_extra_margin_rad,
        )
        sector_half_angle = clamp(
            fallback_half_angle,
            min_sector_half_angle_rad,
            max_sector_half_angle_rad,
        )

    # 2. Apply camera-lidar yaw offset
    theta_lidar_center = theta_cam_center + camera_lidar_yaw_offset_rad

    # 3. Check if theta_lidar_center is within scan FOV
    if scan.angle_increment > 0 and len(scan.ranges) > 0:
        scan_angle_min = scan.angle_min
        scan_angle_max = scan.angle_min + (len(scan.ranges) - 1) * scan.angle_increment
        if theta_lidar_center < scan_angle_min or theta_lidar_center > scan_angle_max:
            return SectorFusionResult(
                distance=None,
                valid_scan_pts=0,
                cluster_count=0,
                selected_cluster=None,
                sector_points=0,
                reason="center_out_of_scan_fov",
                sector_center=theta_lidar_center,
                sector_half_angle=sector_half_angle,
            )

    # 4. Collect points in sector with margin, preserving scan index
    search_half_angle = sector_half_angle + sector_extra_margin_rad
    search_half_angle = min(search_half_angle, max_search_half_angle_rad)
    sector_points: List[Tuple[int, float, float]] = []  # (scan_idx, angle, range)
    for idx, value in enumerate(scan.ranges):
        angle = scan.angle_min + idx * scan.angle_increment
        if abs(angle - theta_lidar_center) > search_half_angle:
            continue
        if not math.isfinite(value):
            continue
        if value < range_min or value > range_max:
            continue
        sector_points.append((idx, angle, value))

    sector_count = len(sector_points)

    if sector_count < lidar_min_valid_points:
        return SectorFusionResult(
            distance=None,
            valid_scan_pts=sector_count,
            cluster_count=0,
            selected_cluster=None,
            sector_points=sector_count,
            reason="insufficient_points",
            sector_center=theta_lidar_center,
            sector_half_angle=sector_half_angle,
        )

    # 5. Cluster segmentation by scan index adjacency + range jump
    clusters: List[LidarCluster] = []
    current_cluster_indices: List[int] = [0]

    for i in range(1, len(sector_points)):
        prev_idx = sector_points[i - 1][0]
        cur_idx = sector_points[i][0]
        prev_rng = sector_points[i - 1][2]
        cur_rng = sector_points[i][2]
        idx_gap = cur_idx - prev_idx
        range_diff = abs(cur_rng - prev_rng)

        if idx_gap <= 2 and range_diff < cluster_range_jump_m:
            current_cluster_indices.append(i)
        else:
            if len(current_cluster_indices) >= cluster_min_points:
                pts = [sector_points[j] for j in current_cluster_indices]
                angles = [p[1] for p in pts]
                ranges = [p[2] for p in pts]
                ranges_sorted = sorted(ranges)
                cluster = LidarCluster(
                    points=len(pts),
                    angle_min=min(angles),
                    angle_max=max(angles),
                    angle_center=(min(angles) + max(angles)) / 2.0,
                    range_median=percentile(ranges_sorted, 0.5),
                    range_p20=percentile(ranges_sorted, 0.2),
                    range_min=min(ranges),
                    width_angle=max(angles) - min(angles),
                )
                clusters.append(cluster)
            current_cluster_indices = [i]

    # Don't forget last cluster
    if len(current_cluster_indices) >= cluster_min_points:
        pts = [sector_points[j] for j in current_cluster_indices]
        angles = [p[1] for p in pts]
        ranges = [p[2] for p in pts]
        ranges_sorted = sorted(ranges)
        cluster = LidarCluster(
            points=len(pts),
            angle_min=min(angles),
            angle_max=max(angles),
            angle_center=(min(angles) + max(angles)) / 2.0,
            range_median=percentile(ranges_sorted, 0.5),
            range_p20=percentile(ranges_sorted, 0.2),
            range_min=min(ranges),
            width_angle=max(angles) - min(angles),
        )
        clusters.append(cluster)

    if not clusters:
        return SectorFusionResult(
            distance=None,
            valid_scan_pts=sector_count,
            cluster_count=0,
            selected_cluster=None,
            sector_points=sector_count,
            reason="no_cluster",
            lidar_target_state="no_cluster",
            sector_center=theta_lidar_center,
            sector_half_angle=sector_half_angle,
            selected_cluster_reason="no_cluster",
        )

    # 6. Compute bbox depth prior (weak pinhole estimate)
    bbox_depth_m_val: Optional[float] = None
    if target_width is not None and target_width > 0 and image_width > 0 and horizontal_fov_deg > 0:
        fx = image_width / (2.0 * math.tan(math.radians(horizontal_fov_deg) * 0.5))
        if fx > 0 and bear_width_m > 0:
            bbox_depth_m_val = fx * bear_width_m / target_width

    # 7. Check track continuity
    track_active = (
        last_cluster_time > 0
        and now > 0
        and (now - last_cluster_time) < track_gate_grace_sec
    )

    # 8. Score and hard-gate each cluster
    scored_clusters = []
    for c in clusters:
        selected_range = 0.7 * c.range_median + 0.3 * c.range_p20

        # --- score ---
        score = 0.0
        angle_err = abs(c.angle_center - theta_lidar_center)
        score += association_angle_weight * angle_err

        if bbox_depth_m_val is not None and bbox_depth_m_val > 0:
            depth_err = abs(selected_range - bbox_depth_m_val)
            score += association_depth_weight * min(depth_err, 2.0)

        if track_active and last_cluster_range is not None and last_cluster_angle is not None:
            range_jump = abs(selected_range - last_cluster_range)
            angle_jump = abs(c.angle_center - last_cluster_angle)
            score += association_track_range_weight * min(range_jump, 2.0)
            score += association_track_angle_weight * angle_jump

        score -= 0.005 * min(c.points, 20)

        # --- hard gating ---
        reject_reason = ""

        if angle_err > association_max_angle_err_rad:
            reject_reason = "angle_gate"

        if not reject_reason and bbox_depth_m_val is not None and bbox_depth_m_val > 0:
            depth_err = abs(selected_range - bbox_depth_m_val)
            if depth_err > association_max_depth_err_m and depth_err / max(bbox_depth_m_val, 0.1) > association_max_depth_err_ratio:
                reject_reason = "bbox_depth_gate"

        if not reject_reason and track_active and last_cluster_range is not None and last_cluster_angle is not None:
            range_jump = abs(selected_range - last_cluster_range)
            angle_jump = abs(c.angle_center - last_cluster_angle)
            if range_jump > association_max_track_range_jump_m or angle_jump > association_max_track_angle_jump_rad:
                reject_reason = "track_gate"

        scored_clusters.append((c, score, reject_reason, selected_range))

    # Sort by score ascending (lower = better)
    scored_clusters.sort(key=lambda x: x[1])

    # Build clusters_dbg
    dbg_parts: List[str] = []
    for ci, (c, sc, rej, _) in enumerate(scored_clusters[:5]):
        tag = "OK" if not rej else "REJ_" + rej.split("_")[0]
        dbg_parts.append(
            "%d:%s:a=%.2f,r=%.2f,p=%d,s=%.2f"
            % (ci, tag, c.angle_center, c.range_median, c.points, sc)
        )
    clusters_dbg_str = ";".join(dbg_parts)

    # 9. Select best non-rejected cluster
    candidates = [(c, sc, rej, sr) for c, sc, rej, sr in scored_clusters if not rej]

    if not candidates:
        # All rejected — determine dominant reject reason
        reject_counts: dict = {}
        for _, _, rej, _ in scored_clusters:
            reject_counts[rej] = reject_counts.get(rej, 0) + 1
        dominant_reject = max(reject_counts, key=reject_counts.get) if reject_counts else "unknown"
        return SectorFusionResult(
            distance=None,
            valid_scan_pts=0,
            cluster_count=len(clusters),
            selected_cluster=None,
            sector_points=sector_count,
            reason="no_lidar_match",
            lidar_target_state="no_lidar_match",
            sector_center=theta_lidar_center,
            sector_half_angle=sector_half_angle,
            clusters_dbg=clusters_dbg_str,
            bbox_depth_m=bbox_depth_m_val,
            selected_cluster_reason="no_lidar_match",
            selected_cluster_reject_reason=dominant_reject + "_all",
            association_candidates=0,
            association_reject_reason=dominant_reject + "_all",
        )

    # Best candidate
    best_c, best_sc, _, best_sr = candidates[0]

    bbox_depth_err_val: Optional[float] = None
    if bbox_depth_m_val is not None:
        bbox_depth_err_val = abs(best_sr - bbox_depth_m_val)

    return SectorFusionResult(
        distance=best_sr,
        valid_scan_pts=best_c.points,
        cluster_count=len(clusters),
        selected_cluster=best_c,
        sector_points=sector_count,
        reason="ok",
        lidar_target_state="associated",
        sector_center=theta_lidar_center,
        sector_half_angle=sector_half_angle,
        clusters_dbg=clusters_dbg_str,
        bbox_depth_m=bbox_depth_m_val,
        bbox_depth_err=bbox_depth_err_val,
        selected_cluster_reason="ok",
        selected_cluster_score=best_sc,
        selected_cluster_range=best_sr,
        selected_cluster_angle=best_c.angle_center,
        association_candidates=len(candidates),
        association_score=best_sc,
    )


def compute_follow_step(
    state: ControllerState,
    config: ControllerConfig,
    mode: str,
    now: float,
    target_theta: Optional[float],
    target_distance: Optional[float],
    v_odom: Optional[float],
    valid_scan_pts: int,
    target_is_fresh: bool,
    scan_is_fresh: bool,
    odom_is_fresh: bool,
    range_is_valid: bool,
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
        longitudinal_decision = compute_longitudinal_step(
            current_state=LongitudinalState(state.longitudinal_state),
            config=config,
            range_m=target_distance,
            v_odom=v_odom,
            range_is_valid=range_is_valid,
            odom_is_fresh=odom_is_fresh,
        )
        state.longitudinal_state = longitudinal_decision.state.value
        speed_target = longitudinal_decision.cmd_speed

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
        state.longitudinal_state = LongitudinalState.IDLE.value

    state.speed_cmd = clamp(state.speed_cmd, 0.0, longitudinal_speed_limit(config))
    state.speed_cmd = enforce_speed_deadband(
        state.speed_cmd,
        speed_target,
        config.min_effective_speed_mps,
    )
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
        self.current_odom_speed_mps: float = 0.0
        self.current_valid_scan_pts: int = 0
        self.current_sector_result: Optional[SectorFusionResult] = None
        self.last_target_time = 0.0
        self.last_scan_time = 0.0
        self.last_odom_time = 0.0
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

        self.cmd_pub = self.create_publisher(AckermannDrive, self.config.ackermann_cmd_topic, qos_reliable)
        self.tuning_status_pub = self.create_publisher(String, "/kt_follow/tuning_status", qos_reliable)
        # Status publisher uses BEST_EFFORT to match rosbridge_websocket subscriber QoS.
        # RELIABLE publisher + BEST_EFFORT subscriber causes silent message drops on
        # rmw_fastrtps (Humble default), making the web UI never receive status updates.
        qos_best_effort = QoSProfile(
            depth=5,
            reliability=ReliabilityPolicy.BEST_EFFORT,
            durability=DurabilityPolicy.VOLATILE,
        )
        self.status_pub = self.create_publisher(String, "/kt_follow/status", qos_best_effort)
        self.create_subscription(String, "/kt_follow/mode", self._on_mode, qos_reliable)
        self.create_subscription(String, "/kt_follow/tuning", self._on_tuning, qos_reliable)
        self.create_subscription(PerceptionTargets, self.config.targets_topic, self._on_targets, make_sensor_data_qos())
        self.create_subscription(LaserScan, self.config.scan_topic, self._on_scan, make_sensor_data_qos())
        self.create_subscription(Odometry, self.config.odom_topic, self._on_odom, make_sensor_data_qos())

        self.loop_dt = 1.0 / self.config.loop_hz
        self.timer = self.create_timer(self.loop_dt, self._control_loop)
        self.status_timer = self.create_timer(0.2, self._publish_status)

        signal.signal(signal.SIGINT, self._sig_handler)
        signal.signal(signal.SIGTERM, self._sig_handler)

        if self.config.slow_speed_mps < self.config.min_effective_speed_mps:
            self.get_logger().warn(
                "slow_speed_mps %.2f below min_effective_speed_mps %.2f, clamping"
                % (self.config.slow_speed_mps, self.config.min_effective_speed_mps)
            )
            self.config.slow_speed_mps = self.config.min_effective_speed_mps
        if self.config.fast_speed_mps < self.config.min_effective_speed_mps:
            self.get_logger().warn(
                "fast_speed_mps %.2f below min_effective_speed_mps %.2f, clamping"
                % (self.config.fast_speed_mps, self.config.min_effective_speed_mps)
            )
            self.config.fast_speed_mps = self.config.min_effective_speed_mps

        self.get_logger().info(
            "kt_follow_controller_v4 started enable_control=%s scan_topic=%s odom_topic=%s max_speed=%.2f max_steering_angle=%.2f"
            % (
                self.config.enable_control,
                self.config.scan_topic,
                self.config.odom_topic,
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
            self.current_sector_result = None
            return

        # Compute target width for sector fusion
        target_width = None
        if self.current_target is not None:
            target_width = self.current_target.get("width")

        result = compute_sector_fusion(
            scan=ScanWindow(angle_min=msg.angle_min, angle_increment=msg.angle_increment, ranges=msg.ranges),
            theta_cam_center=self.current_theta_raw,
            target_width=target_width,
            image_width=self.config.image_width,
            horizontal_fov_deg=self.config.horizontal_fov_deg,
            range_min=self.config.scan_range_min,
            range_max=self.config.scan_range_max,
            min_sector_half_angle_rad=self.config.min_sector_half_angle_rad,
            max_sector_half_angle_rad=self.config.max_sector_half_angle_rad,
            sector_extra_margin_rad=self.config.sector_extra_margin_rad,
            camera_lidar_yaw_offset_rad=self.config.camera_lidar_yaw_offset_rad,
            cluster_range_jump_m=self.config.cluster_range_jump_m,
            cluster_min_points=self.config.cluster_min_points,
            lidar_min_valid_points=self.config.lidar_min_valid_points,
            last_cluster_angle=self.state.last_cluster_angle,
            last_cluster_range=self.state.last_cluster_range,
            last_cluster_time=self.state.last_cluster_time,
            now=time.time(),
            lidar_search_half_angle_rad=self.config.lidar_search_half_angle_rad,
            max_search_half_angle_rad=self.config.max_search_half_angle_rad,
            bear_width_m=self.config.bear_width_m,
            track_gate_grace_sec=self.config.track_gate_grace_sec,
            association_angle_weight=self.config.association_angle_weight,
            association_depth_weight=self.config.association_depth_weight,
            association_track_range_weight=self.config.association_track_range_weight,
            association_track_angle_weight=self.config.association_track_angle_weight,
            association_max_angle_err_rad=self.config.association_max_angle_err_rad,
            association_max_depth_err_m=self.config.association_max_depth_err_m,
            association_max_depth_err_ratio=self.config.association_max_depth_err_ratio,
            association_max_track_range_jump_m=self.config.association_max_track_range_jump_m,
            association_max_track_angle_jump_rad=self.config.association_max_track_angle_jump_rad,
        )
        self.current_dist_raw = result.distance
        self.current_valid_scan_pts = result.valid_scan_pts
        self.current_sector_result = result

        # Update cluster state for continuity — only when associated
        if (
            result.lidar_target_state == "associated"
            and result.selected_cluster is not None
            and result.distance is not None
        ):
            self.state.last_cluster_angle = result.selected_cluster.angle_center
            self.state.last_cluster_range = result.distance
            self.state.last_cluster_time = time.time()

    def _on_odom(self, msg: Odometry) -> None:
        self.last_odom_time = time.time()
        self.current_odom_speed_mps = abs(float(msg.twist.twist.linear.x))

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

        # Build fusion diagnostics
        sector = self.current_sector_result
        selected = sector.selected_cluster if sector else None

        payload = {
            "mode": self.state.mode,
            "scan_topic": self.config.scan_topic,
            "odom_topic": self.config.odom_topic,
            "roi_cx": None if target is None else round(float(target["roi_cx"]), 1),
            "roi_cy": None if target is None else round(float(target["roi_cy"]), 1),
            "roi_width": None if target is None else round(float(target.get("width", 0.0)), 1),
            "theta_raw": None if self.current_theta_raw is None else round(float(self.current_theta_raw), 4),
            "theta_filt": None if not self.state.theta_filter_inited else round(float(self.state.theta_filtered), 4),
            "theta_lidar_center": None if sector is None else round(float(sector.sector_center), 4),
            "sector_half_angle": None if sector is None else round(float(sector.sector_half_angle), 4),
            "sector_points": int(sector.sector_points) if sector else 0,
            "image_theta_left_deg": round(math.degrees(image_theta_left), 2),
            "image_theta_right_deg": round(math.degrees(image_theta_right), 2),
            "range_m": None if self.current_dist_raw is None else round(float(self.current_dist_raw), 4),
            "dist_filt": None if not self.state.dist_filter_inited or self.state.dist_filtered is None else round(float(self.state.dist_filtered), 4),
            "valid_scan_pts": int(self.current_valid_scan_pts),
            "cluster_count": int(sector.cluster_count) if sector else 0,
            "selected_cluster_points": int(selected.points) if selected else 0,
            "selected_cluster_angle": None if selected is None else round(float(selected.angle_center), 4),
            "selected_cluster_range": None if selected is None else round(float(selected.range_median), 4),
            "selected_cluster_reason": None if sector is None else sector.selected_cluster_reason,
            "camera_lidar_yaw_offset": round(float(self.config.camera_lidar_yaw_offset_rad), 4),
            "stop_distance_m": round(float(self.config.stop_distance_m), 3),
            "full_speed_distance_m": round(float(self.config.full_speed_distance_m), 3),
            "scan_angle_min_deg": None if self.last_scan_angle_min is None else round(math.degrees(self.last_scan_angle_min), 2),
            "scan_angle_max_deg": None if self.last_scan_angle_max is None else round(math.degrees(self.last_scan_angle_max), 2),
            "scan_angle_increment_deg": None if self.last_scan_angle_increment is None else round(math.degrees(self.last_scan_angle_increment), 4),
            "scan_range_count": int(self.last_scan_count),
            "speed_cmd": round(float(self.state.speed_cmd), 4),
            "steer_cmd": round(float(self.state.steering_cmd), 4),
            "v_odom": round(float(self.current_odom_speed_mps), 4),
            "longitudinal_state": self.state.longitudinal_state,
            "reason": self.status_snapshot.reason,
            "publishing": bool(self.status_snapshot.publishing),
            "max_speed": round(float(self.config.max_speed), 3),
            "max_steering_angle": round(float(self.config.max_steering_angle), 3),
            "target_age_ms": self._age_ms(self.last_target_time, now),
            "scan_age_ms": self._age_ms(self.last_scan_time, now),
            "odom_age_ms": self._age_ms(self.last_odom_time, now),
            "lidar_window": round(float(self.config.lidar_search_half_angle_rad), 4),
            "range_source": self.state.range_source,
            "range_hold_age": self.state.range_hold_age_ms,
            # --- v4.3 diagnostic fields ---
            "bbox_depth_m": None if sector is None or sector.bbox_depth_m is None else round(float(sector.bbox_depth_m), 4),
            "bbox_depth_err": None if sector is None or sector.bbox_depth_err is None else round(float(sector.bbox_depth_err), 4),
            "clusters_dbg": "" if sector is None else sector.clusters_dbg,
            "selected_cluster_score": 0.0 if sector is None else round(float(sector.selected_cluster_score), 4),
            "selected_cluster_reject_reason": "" if sector is None else sector.selected_cluster_reject_reason,
            # --- v4.4: target-aware association fields ---
            "lidar_target_state": "no_vision_target" if sector is None else sector.lidar_target_state,
            "association_candidates": 0 if sector is None else int(sector.association_candidates),
            "association_score": 0.0 if sector is None else round(float(sector.association_score), 4),
            "association_reject_reason": "" if sector is None else sector.association_reject_reason,
            "association_dbg": "" if sector is None else sector.association_dbg,
            "selected_cluster_range": None if sector is None or sector.selected_cluster_range is None else round(float(sector.selected_cluster_range), 4),
            "selected_cluster_angle": None if sector is None or sector.selected_cluster_angle is None else round(float(sector.selected_cluster_angle), 4),
            "cmd_speed": round(float(self.state.speed_cmd), 4),
            "enable_control": bool(self.config.enable_control),
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
        odom_age_ms = self._age_ms(self.last_odom_time, now)
        range_age_ms = self._age_ms(self.last_scan_time, now)
        odom_fresh = odom_age_ms is not None and odom_age_ms <= self.config.max_valid_odom_age_ms
        range_valid = (
            self.current_dist_raw is not None
            and math.isfinite(self.current_dist_raw)
            and self.current_dist_raw >= self.config.scan_range_min
            and self.current_valid_scan_pts >= self.config.lidar_min_valid_points
            and range_age_ms is not None
            and range_age_ms <= self.config.max_valid_range_age_ms
        )

        # --- lidar_target_state gating: only allow range when associated ---
        lidar_state = None
        if self.current_sector_result is not None:
            lidar_state = self.current_sector_result.lidar_target_state
        if lidar_state != "associated":
            range_valid = False

        # --- range hold: keep last valid range for a short window ---
        if range_valid:
            self.state.last_valid_range = self.current_dist_raw
            self.state.last_valid_range_time = now
            self.state.range_source = RangeSource.CURRENT.value
            self.state.range_hold_age_ms = 0
        else:
            hold_age_ms = self._age_ms(self.state.last_valid_range_time, now)
            if (
                self.state.last_valid_range is not None
                and hold_age_ms is not None
                and hold_age_ms <= self.config.lidar_hold_ms
            ):
                self.state.range_source = RangeSource.HOLD.value
                self.state.range_hold_age_ms = hold_age_ms
            else:
                self.state.range_source = RangeSource.INVALID.value
                self.state.range_hold_age_ms = hold_age_ms
                self.state.last_cluster_angle = None
                self.state.last_cluster_range = None

        range_for_control = (
            self.current_dist_raw if range_valid else self.state.last_valid_range
        )
        range_for_control_valid = range_valid or (
            self.state.last_valid_range is not None
            and self.state.range_source == RangeSource.HOLD.value
        )

        # --- safety: never move on hold range when not associated ---
        if lidar_state != "associated":
            range_for_control = None
            range_for_control_valid = False

        decision = compute_follow_step(
            state=self.state,
            config=self.config,
            mode=self.state.mode,
            now=now,
            target_theta=self.current_theta_raw,
            target_distance=range_for_control,
            v_odom=self.current_odom_speed_mps,
            valid_scan_pts=self.current_valid_scan_pts,
            target_is_fresh=target_fresh,
            scan_is_fresh=scan_fresh,
            odom_is_fresh=odom_fresh,
            range_is_valid=range_for_control_valid,
            dt=self.loop_dt,
        )

        # --- steering speed limit: large turn => cap / stop ---
        if abs(self.state.steering_cmd) >= self.config.turn_stop_angle_rad:
            self.state.speed_cmd = 0.0
        elif abs(self.state.steering_cmd) >= self.config.turn_slow_angle_rad:
            self.state.speed_cmd = min(self.state.speed_cmd, self.config.turn_speed_cap)

        self.status_snapshot = StatusSnapshot(
            reason=decision.reason,
            publishing=decision.publishing,
            range_source=self.state.range_source,
            range_hold_age_ms=self.state.range_hold_age_ms,
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
            sector = self.current_sector_result
            selected = sector.selected_cluster if sector else None
            longitudinal = compute_longitudinal_step(
                current_state=LongitudinalState(self.state.longitudinal_state),
                config=self.config,
                range_m=range_for_control,
                v_odom=self.current_odom_speed_mps,
                range_is_valid=range_for_control_valid,
                odom_is_fresh=odom_fresh,
            )
            self.get_logger().info(
                "mode=%s roi_cx=%s theta_raw=%s theta_filt=%.3f range_m=%s dist_filt=%s v_odom=%.3f "
                "s_remain=%s s_stop=%s long_state=%s valid_scan_pts=%d cmd_speed=%.3f steer_cmd=%.3f "
                "reason=%s publishing=%s range_source=%s range_hold_age=%s "
                "theta_lidar_center=%.3f sector_half=%.3f sector_pts=%d cluster_cnt=%d "
                "sel_pts=%d sel_angle=%.3f sel_range=%.3f sel_reason=%s "
                "bbox_depth_m=%s bbox_depth_err=%s sel_score=%.3f sel_reject=%s clusters_dbg=%s "
                "lidar_state=%s assoc_candidates=%d assoc_score=%.3f assoc_reject=%s assoc_dbg=%s"
                % (
                    self.state.mode,
                    "None" if roi_cx is None else "%.1f" % roi_cx,
                    "None" if theta_raw is None else "%.3f" % theta_raw,
                    self.state.theta_filtered,
                    "None" if range_for_control is None else "%.3f" % range_for_control,
                    "None" if self.state.dist_filtered is None else "%.3f" % self.state.dist_filtered,
                    self.current_odom_speed_mps,
                    "None" if longitudinal.s_remain is None else "%.3f" % longitudinal.s_remain,
                    "None" if longitudinal.s_stop is None else "%.3f" % longitudinal.s_stop,
                    longitudinal.state.value,
                    self.current_valid_scan_pts,
                    decision.speed_cmd,
                    decision.steer_cmd,
                    decision.reason,
                    decision.publishing,
                    self.state.range_source,
                    "None" if self.state.range_hold_age_ms is None else "%d" % self.state.range_hold_age_ms,
                    0.0 if sector is None else sector.sector_center,
                    0.0 if sector is None else sector.sector_half_angle,
                    0 if sector is None else sector.sector_points,
                    0 if sector is None else sector.cluster_count,
                    0 if selected is None else selected.points,
                    0.0 if selected is None else selected.angle_center,
                    0.0 if selected is None else selected.range_median,
                    "None" if sector is None else sector.reason,
                    "None" if sector is None or sector.bbox_depth_m is None else "%.3f" % sector.bbox_depth_m,
                    "None" if sector is None or sector.bbox_depth_err is None else "%.3f" % sector.bbox_depth_err,
                    0.0 if sector is None else sector.selected_cluster_score,
                    "" if sector is None else sector.selected_cluster_reject_reason,
                    "" if sector is None else sector.clusters_dbg,
                    "None" if sector is None else sector.lidar_target_state,
                    0 if sector is None else int(sector.association_candidates),
                    0.0 if sector is None else sector.association_score,
                    "" if sector is None else sector.association_reject_reason,
                    "" if sector is None else sector.association_dbg,
                )
            )


def parse_args(argv: Sequence[str]) -> ControllerConfig:
    parser = argparse.ArgumentParser(description="KT demo follow controller v4")
    parser.add_argument("--enable-control", type=str, default="false")
    parser.add_argument("--scan-topic", type=str, default="/tianracer/scan")
    parser.add_argument("--odom-topic", type=str, default="/odom")
    parser.add_argument("--target-distance-m", type=float, default=0.5)
    parser.add_argument("--restart-distance-m", type=float, default=0.7)
    parser.add_argument("--stop-distance-m", type=float, default=0.5)
    parser.add_argument("--full-speed-distance-m", type=float, default=1.6)
    parser.add_argument("--max-speed", type=float, default=0.25)
    parser.add_argument("--min-effective-speed-mps", type=float, default=0.30)
    parser.add_argument("--slow-speed-mps", type=float, default=0.35)
    parser.add_argument("--fast-speed-mps", type=float, default=0.50)
    parser.add_argument("--stop-decel-mps2", type=float, default=0.80)
    parser.add_argument("--stop-margin-m", type=float, default=0.08)
    parser.add_argument("--max-valid-odom-age-ms", type=int, default=200)
    parser.add_argument("--max-valid-range-age-ms", type=int, default=200)
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
    parser.add_argument("--ackermann-cmd-topic", type=str, default="/ackermann_cmd")
    parser.add_argument("--targets-topic", type=str, default="/bear_detection/targets")
    # v4.1: robust lidar sector search
    parser.add_argument("--lidar-search-half-angle-rad", type=float, default=0.24)
    parser.add_argument("--lidar-min-valid-points", type=int, default=3)
    parser.add_argument("--lidar-range-percentile", type=float, default=0.20)
    parser.add_argument("--lidar-hold-ms", type=int, default=250)
    parser.add_argument("--turn-slow-angle-rad", type=float, default=0.18)
    parser.add_argument("--turn-stop-angle-rad", type=float, default=0.30)
    parser.add_argument("--turn-speed-cap", type=float, default=0.22)
    # v4.2: camera-lidar sector fusion
    parser.add_argument("--min-sector-half-angle-rad", type=float, default=0.16)
    parser.add_argument("--max-sector-half-angle-rad", type=float, default=0.45)
    parser.add_argument("--sector-extra-margin-rad", type=float, default=0.08)
    parser.add_argument("--camera-lidar-yaw-offset-rad", type=float, default=0.0)
    parser.add_argument("--cluster-range-jump-m", type=float, default=0.25)
    parser.add_argument("--cluster-min-points", type=int, default=3)
    parser.add_argument("--max-search-half-angle-rad", type=float, default=0.60)
    # v4.3: bbox depth prior + track continuity gating
    parser.add_argument("--bear-width-m", type=float, default=0.25)
    parser.add_argument("--bbox-depth-gate-m", type=float, default=0.65)
    parser.add_argument("--bbox-depth-gate-ratio", type=float, default=0.65)
    parser.add_argument("--track-range-gate-m", type=float, default=0.40)
    parser.add_argument("--track-angle-gate-rad", type=float, default=0.25)
    parser.add_argument("--track-gate-grace-sec", type=float, default=0.5)
    # v4.4: target-aware camera-lidar association
    parser.add_argument("--association-angle-weight", type=float, default=1.0)
    parser.add_argument("--association-depth-weight", type=float, default=0.8)
    parser.add_argument("--association-track-range-weight", type=float, default=0.6)
    parser.add_argument("--association-track-angle-weight", type=float, default=0.5)
    parser.add_argument("--association-max-angle-err-rad", type=float, default=0.35)
    parser.add_argument("--association-max-depth-err-m", type=float, default=0.60)
    parser.add_argument("--association-max-depth-err-ratio", type=float, default=0.70)
    parser.add_argument("--association-max-track-range-jump-m", type=float, default=0.50)
    parser.add_argument("--association-max-track-angle-jump-rad", type=float, default=0.35)
    # Strip ROS2 launch-injected args (--ros-args, -r, etc.) before argparse
    from rclpy.utilities import remove_ros_args
    non_ros_argv = remove_ros_args(args=list(argv))
    args = parser.parse_args(non_ros_argv)

    return ControllerConfig(
        enable_control=args.enable_control.lower() in ("1", "true", "yes"),
        scan_topic=args.scan_topic,
        odom_topic=args.odom_topic,
        target_distance_m=args.target_distance_m,
        restart_distance_m=args.restart_distance_m,
        stop_distance_m=args.stop_distance_m,
        full_speed_distance_m=args.full_speed_distance_m,
        max_speed=args.max_speed,
        min_effective_speed_mps=args.min_effective_speed_mps,
        slow_speed_mps=args.slow_speed_mps,
        fast_speed_mps=args.fast_speed_mps,
        stop_decel_mps2=args.stop_decel_mps2,
        stop_margin_m=args.stop_margin_m,
        max_valid_odom_age_ms=args.max_valid_odom_age_ms,
        max_valid_range_age_ms=args.max_valid_range_age_ms,
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
        ackermann_cmd_topic=args.ackermann_cmd_topic,
        targets_topic=args.targets_topic,
        lidar_search_half_angle_rad=args.lidar_search_half_angle_rad,
        lidar_min_valid_points=args.lidar_min_valid_points,
        lidar_range_percentile=args.lidar_range_percentile,
        lidar_hold_ms=args.lidar_hold_ms,
        turn_slow_angle_rad=args.turn_slow_angle_rad,
        turn_stop_angle_rad=args.turn_stop_angle_rad,
        turn_speed_cap=args.turn_speed_cap,
        min_sector_half_angle_rad=args.min_sector_half_angle_rad,
        max_sector_half_angle_rad=args.max_sector_half_angle_rad,
        sector_extra_margin_rad=args.sector_extra_margin_rad,
        camera_lidar_yaw_offset_rad=args.camera_lidar_yaw_offset_rad,
        cluster_range_jump_m=args.cluster_range_jump_m,
        cluster_min_points=args.cluster_min_points,
        max_search_half_angle_rad=args.max_search_half_angle_rad,
        bear_width_m=args.bear_width_m,
        bbox_depth_gate_m=args.bbox_depth_gate_m,
        bbox_depth_gate_ratio=args.bbox_depth_gate_ratio,
        track_range_gate_m=args.track_range_gate_m,
        track_angle_gate_rad=args.track_angle_gate_rad,
        track_gate_grace_sec=args.track_gate_grace_sec,
        association_angle_weight=args.association_angle_weight,
        association_depth_weight=args.association_depth_weight,
        association_track_range_weight=args.association_track_range_weight,
        association_track_angle_weight=args.association_track_angle_weight,
        association_max_angle_err_rad=args.association_max_angle_err_rad,
        association_max_depth_err_m=args.association_max_depth_err_m,
        association_max_depth_err_ratio=args.association_max_depth_err_ratio,
        association_max_track_range_jump_m=args.association_max_track_range_jump_m,
        association_max_track_angle_jump_rad=args.association_max_track_angle_jump_rad,
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

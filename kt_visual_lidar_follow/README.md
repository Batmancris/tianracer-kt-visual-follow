# kt_visual_lidar_follow

Dry-run visual-lidar follow node for Tianracer KT.

## 1. Purpose

Fuses a visual detection target (`ai_msgs/PerceptionTargets`) with `LaserScan`
distance association and a finite state machine to produce suggested follow
velocities. In dry-run mode (the default) the node **never publishes
`/cmd_vel`** — it only outputs debug topics for offline analysis and tuning.

## 2. Input Topics

| Topic | Type | Description |
|---|---|---|
| `/bear_detection/targets` | `ai_msgs/msg/PerceptionTargets` | Visual detections from bear detection |
| `/tianracer/scan` | `sensor_msgs/msg/LaserScan` | 2D lidar scan |
| `/tianracer/camera/camera_info` | `sensor_msgs/msg/CameraInfo` | Camera intrinsics for angle estimation |

All topic names are configurable via parameters.

## 3. Output Topics

| Topic | Type | Description |
|---|---|---|
| `/kt_follow/state` | `std_msgs/msg/String` | Current FSM state + optional stop reason |
| `/kt_follow/debug_target` | `std_msgs/msg/String` | Parsed target info (cx, cy, theta, distance) |
| `/kt_follow/debug_cmd` | `geometry_msgs/msg/TwistStamped` | Suggested velocity (NOT connected to chassis) |

## 4. Dry-Run Safety Design

- `dry_run` parameter defaults to `true`.
- The node **does not create a `/cmd_vel` publisher** in dry-run mode.
- Even if `cmd_vel_topic` is set, it is never used to publish.
- `debug_cmd` is a `TwistStamped` that carries suggested velocities for
  logging/tuning only.
- The node can be killed at any time without affecting the chassis.

## 5. State Machine

```
IDLE -> VISION_LOCK -> VISION_LIDAR_FUSED
                     \-> LIDAR_HOLD -> SEARCH
VISION_LIDAR_FUSED -> LIDAR_HOLD (visual lost)
                    -> VISION_LOCK (lidar lost)
Any -> STOP (safety: camera_info missing, scan timeout, too close, theta jump)
STOP -> IDLE (recovery when conditions clear)
```

States:
- **IDLE**: No target. Zero output.
- **VISION_LOCK**: Visual target found, waiting for lidar association.
- **VISION_LIDAR_FUSED**: Full fusion — computes suggested linear/angular.
- **LIDAR_HOLD**: Visual briefly lost; continues with last known lidar distance.
- **SEARCH**: Visual lost beyond hold timeout. First version outputs zero.
- **STOP**: Safety halt (camera_info missing, scan timeout, too close, theta jump).

## 6. Why No /cmd_vel

This is a **dry-run** package for development and validation. Publishing to
`/cmd_vel` would drive the real chassis. The debug output allows offline
analysis of the control logic without any physical risk.

## 7. Future Integration with kt_bear_detection

When `kt_bear_detection` is ready:
1. Set `visual_targets_topic` to the detection output topic.
2. Ensure the detection publishes `ai_msgs/msg/PerceptionTargets` with
   ROI type matching `target_type` parameter (default: `"bear"`).
3. Set `dry_run:=false` after thorough testing.

## 8. cmd_vel_to_ackermann_drive.py 0.5 m/s Clamp Risk

Before running on real hardware, the `cmd_vel_to_ackermann_drive.py` node
clamps `linear.x` to 0.5 m/s. If the follow node suggests higher speeds,
they will be silently clamped. This must be addressed before real-vehicle
deployment.

## 9. Build

```bash
colcon build --packages-select kt_visual_lidar_follow
```

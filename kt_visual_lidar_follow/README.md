# kt_visual_lidar_follow

This package now contains two clearly separated tracks:

- **formal demo/prod path**: `kt_follow_controller_v4.py`
- **legacy research path**: `kt_visual_lidar_follow_node` and `kt_smooth_follow_controller_v3.py`

The formal path is the only recommended chain for KT demo bring-up.

## Path Semantics

- Local source path in this repo: `work_src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py`
- Board deployment path at runtime: `~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py`
- The board path is not a repo-local directory. Populate it with `scripts/kt_demo_sync_follow_v4.ps1` before using direct board-side commands on a fresh robot workspace.

## Formal Demo Chain

Formal control is fixed to:

`/kt_follow/mode` + `/bear_detection/targets` + `/tianracer/scan` -> `kt_follow_controller_v4.py` -> `/ackermann_cmd`

### Inputs

| Topic | Type | Notes |
|---|---|---|
| `/kt_follow/mode` | `std_msgs/msg/String` | `FOLLOW`, `MANUAL`, `OFF` |
| `/bear_detection/targets` | `ai_msgs/msg/PerceptionTargets` | BEST_EFFORT compatible |
| `/tianracer/scan` | `sensor_msgs/msg/LaserScan` | BEST_EFFORT compatible |

### Output

| Topic | Type | Notes |
|---|---|---|
| `/ackermann_cmd` | `ackermann_msgs/msg/AckermannDrive` | Formal chassis command path |

### Safety Rules

- `OFF` sends stop x10, then releases publisher activity.
- `MANUAL` sends stop x5, then releases control to manual/RC path.
- stale target, stale scan, no bear, no scan, or `valid_scan_pts=0` all force stop.
- `SIGINT` / `SIGTERM` trigger stop x10.

### Launch

```bash
ros2 launch kt_visual_lidar_follow kt_follow_controller_v4.launch.py enable_control:=false
```

### Direct Python Run

This is a board-side runtime command. It assumes the deployment target above already exists on the robot.

```bash
python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py \
  --enable-control true \
  --target-distance-m 1.0 \
  --stop-distance-m 1.0 \
  --full-speed-distance-m 1.6 \
  --max-speed 0.25 \
  --max-steering-angle 0.18
```

## Legacy Assets

These remain in-repo for reference only and should not be used as the formal demo path:

- `kt_visual_lidar_follow_node`
- `kt_smooth_follow_controller_v3.py`
- `/kt_follow/debug_target`
- `/kt_follow/state`
- old ROS1 scan bridge helpers

Legacy files are kept to preserve prior experiments, but they are not the recommended runtime.

## Web UI

Formal web entry is `work_src/tools/bear_overlay_prod.html`.

It is intentionally limited to:

- image display from `/tianracer/camera/image_compressed`
- overlay display from `/bear_detection/targets`
- mode publish to `/kt_follow/mode`

It does not provide chassis direct-control APIs and does not define `/ackermann_cmd` writes.

## Build

```bash
colcon build \
  --packages-select kt_visual_lidar_follow \
  --executor sequential \
  --parallel-workers 1 \
  --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
```

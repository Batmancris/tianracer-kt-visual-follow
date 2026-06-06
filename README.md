# KT Visual Follow — Start Here

Git root: `E:\research\1\kt\work_src`

唯一正式入口。旧 demo 脚本已全部删除。

## Quick Start

```powershell
# Start (dry-run, enable_control=false)
.\scripts\kt_start_follow_stack.ps1

# Check status
.\scripts\kt_check_follow_stack.ps1

# Stop
.\scripts\kt_stop_follow_stack.ps1
```

## Web Console

Open `tools\bear_overlay_prod.html` in browser.

## Default Mode

- **dry-run** — no ground follow, no nonzero ackermann publish
- `enable_control=false`
- Follow controller runs but does NOT publish to `/ackermann_cmd`

## Board (Remote Robot)

```bash
# Start
ssh sunrise@10.138.249.241 "bash /home/sunrise/kt_scripts/start_kt_follow_stack.sh"

# Check
ssh sunrise@10.138.249.241 "bash /home/sunrise/kt_scripts/check_kt_follow_stack.sh"

# Stop
ssh sunrise@10.138.249.241 "bash /home/sunrise/kt_scripts/stop_kt_follow_stack.sh"
```

## Formal Entry Points

### Local Windows

| File | Purpose |
|------|---------|
| `scripts/kt_start_follow_stack.ps1` | Start stack |
| `scripts/kt_check_follow_stack.ps1` | Check status |
| `scripts/kt_stop_follow_stack.ps1` | Stop stack |

### Board

| File | Purpose |
|------|---------|
| `/home/sunrise/kt_scripts/start_kt_follow_stack.sh` | Start stack |
| `/home/sunrise/kt_scripts/check_kt_follow_stack.sh` | Check status |
| `/home/sunrise/kt_scripts/stop_kt_follow_stack.sh` | Stop stack |
| `/home/sunrise/kt_scripts/kt_ros2_env.bash` | ROS2 env setup |

### ROS2 Package

| File | Purpose |
|------|---------|
| `kt_visual_lidar_follow/launch/kt_follow_controller_v4.launch.py` | Follow launch |
| `kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py` | Follow controller |

### Web

| File | Purpose |
|------|---------|
| `tools/bear_overlay_prod.html` | Web console |

## Formal Control Chain

`/kt_follow/mode` + `/bear_detection/targets` + `/tianracer/scan` → `kt_follow_controller_v4.py` → `/ackermann_cmd`

## Important Boundaries

- The formal page is `bear_overlay_prod.html`, not `bear_overlay.html`.
- The formal controller is `kt_follow_controller_v4.py`, not `kt_smooth_follow_controller_v3.py`.
- `kt_smooth_follow_controller_v3.py` has been deleted — do not search for it.
- Old demo scripts (`kt_demo_*.ps1`, `start_ros2_overlay.ps1`) have been deleted.
- Default mode is dry-run with `enable_control=false`.
- Only hover test is allowed to temporarily set `armed` mode.
- The formal path is ROS2-only with LDS_E110.
- The web page does not directly control the chassis.

## IP Configuration

Default robot IP: `10.138.249.241`

Override via web console URL parameter:
- `tools/bear_overlay_prod.html?robot=10.138.249.241`

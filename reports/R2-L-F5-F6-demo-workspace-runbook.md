# KT Demo Workspace Runbook

## Goal

Single recommended demo path:

- `/kt_follow/mode`
- `/bear_detection/targets`
- `/tianracer/scan`
- `kt_follow_controller_v4.py`
- `/ackermann_cmd`

The web page is visualization plus mode publish only. It is not part of the control loop.

## Local Entry Points

- `scripts/kt_demo_preflight.ps1`
- `scripts/kt_demo_sync_follow_v4.ps1`
- `scripts/kt_demo_bringup.ps1`
- `scripts/kt_demo_follow_v4_hover.ps1`
- `scripts/kt_demo_hover_gate.ps1`
- `scripts/kt_demo_ground_gate.ps1`
- `scripts/kt_demo_follow_v4_ground.ps1`
- `scripts/kt_demo_capture_readiness.ps1`
- `scripts/kt_demo_hover_check.ps1`
- `scripts/kt_demo_ground_cycle.ps1`
- `scripts/kt_demo_status.ps1`
- `scripts/kt_demo_stop.ps1`
- `scripts/kt_demo_summary.ps1`
- `scripts/kt_demo_report_draft.ps1`
- `tools/bear_overlay_prod.html`

## Path Semantics

- Local source path: `kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py`
- Board deployment path: `~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py`
- The board deployment path is a deployment target, not a repo-local path.
- Use `scripts/kt_demo_sync_follow_v4.ps1` to create or refresh the board-side copy before hover or ground runs on a fresh robot workspace.

## 机器人 IP 变化时如何连接

临时方式：

- `.\scripts\start_ros2_overlay.ps1 -RobotIp 10.138.249.241`
- `.\scripts\status_ros2_overlay.ps1 -RobotIp 10.138.249.241`
- `.\scripts\stop_ros2_overlay.ps1 -RobotIp 10.138.249.241`

长期方式：

- 复制 `config/local.robot.example.ps1`
- 为 `config/local.robot.ps1`
- 把其中的 `$KT_ROBOT_IP = "10.138.249.241"` 改成当前机器人 IP

Web 页面方式：

- `tools/bear_overlay_prod.html?robot=10.138.249.241`
- 或在页面里手动填写 `ws://10.138.249.241:9090`
- 以及手动填写 `http://10.138.249.241:8080/stream.mjpg`

## Required Startup Order

1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_preflight.ps1`.
1. If preflight reports `MISSING deployment target` for `kt_follow_controller_v4.py`, run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_sync_follow_v4.ps1`.
1. Re-run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_preflight.ps1` and confirm the `follow_v4 file` section shows the deployed file.
1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_bringup.ps1`.
1. Confirm `/ackermann_cmd` subscriber is `tianracer_core`.
1. Confirm `/tianracer/scan_raw` and `/tianracer/scan` are near 10Hz.
1. Confirm `/bear_detection/targets` has a publisher and non-zero rate.
1. Confirm there is no `joy`, `teleop`, `navigation`, or `nav2`.
1. Open `tools\bear_overlay_prod.html` for image overlay and `/kt_follow/mode`.
1. If you need readiness evidence, run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_capture_readiness.ps1`.
1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_summary.ps1 -IncludeArtifactPaths` to see the current artifact-backed state in one place.
1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_report_draft.ps1` to generate the current conservative report draft.

## Hover Test

Before hover verification, clear any legacy controller:

- `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_stop.ps1`

Start `v4` with the hover profile:

- Recommended: `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_follow_v4_hover.ps1`
- Equivalent board command after `scripts/kt_demo_sync_follow_v4.ps1` has populated the board deployment path:

```bash
python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py \
  --enable-control true \
  --target-distance-m 1.0 \
  --stop-distance-m 1.0 \
  --full-speed-distance-m 1.6 \
  --max-speed 0.25 \
  --max-steering-angle 0.18
```

Check:

- Left/right bear movement matches steering direction.
- Near/far bear movement matches speed change.
- `MANUAL` sends stop burst and releases control.
- `OFF` sends stop burst and releases control.
- stale / no target / no scan / `valid_scan_pts=0` all stop the car and recenter steering.

Capture evidence with `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_hover_check.ps1`.
Then convert it into a gate result with `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_hover_gate.ps1`.
Default policy: hover evidence older than 30 minutes is stale and must be regenerated before ground gating.
The hover gate must be regenerated from the latest raw `kt-demo-hover-*.txt` run. Reusing an older pass after a newer raw hover run is not accepted.

## Ground Test Gate

Do not put the car on the ground unless all of these are true:

- `/tianracer/scan` is near 10Hz.
- `/ackermann_cmd` subscriber is `tianracer_core`.
- No legacy `smooth_follow` or `kt_visual_lidar_follow` controller remains.
- Hover verification passed.

First ground run uses conservative parameters only:

- Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_ground_gate.ps1` first.
- `kt_demo_ground_gate.ps1` will refuse to pass unless the latest `kt-demo-hover-gate-*.txt` says `Hover gate PASSED`.
- `kt_demo_ground_gate.ps1` also refuses stale hover-gate artifacts older than 30 minutes by default.
- `kt_demo_ground_gate.ps1` also refuses a passing hover-gate artifact if it is not based on the latest raw hover artifact.
- Recommended launch: `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_follow_v4_ground.ps1 -Armed`
- Equivalent board command after `scripts/kt_demo_sync_follow_v4.ps1` has populated the board deployment path:

```bash
python3 ~/tianracer_ros2_ws/src/kt_visual_lidar_follow/scripts/kt_follow_controller_v4.py \
  --enable-control true \
  --target-distance-m 1.0 \
  --stop-distance-m 1.0 \
  --full-speed-distance-m 1.8 \
  --max-speed 0.10 \
  --max-steering-angle 0.12 \
  --max-accel 0.25 \
  --max-decel 0.80
```

Only run 3-5 seconds of `FOLLOW`, then switch to `OFF`.
Use `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_ground_cycle.ps1 -ExecuteGroundRun` to record one `FOLLOW -> OFF` cycle.

## Recovery

On any abnormal behavior:

1. Set the web page to `OFF`.
1. Run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_stop.ps1`.
1. Re-run `powershell -ExecutionPolicy Bypass -File .\scripts\kt_demo_preflight.ps1`.

## Evidence Path

Base the final report on these files:

- `scripts/kt_demo_capture_readiness.ps1`
- `scripts/kt_demo_hover_check.ps1`
- `reports/artifacts/kt-demo-hover-gate-*.txt`
- `scripts/kt_demo_ground_cycle.ps1`
- `reports/artifacts/kt-demo-ground-gate-*.txt`
- `reports/R2-L-F5-F6-ground-test-report-skeleton.md`
- `scripts/kt_demo_summary.ps1`
- `scripts/kt_demo_report_draft.ps1`

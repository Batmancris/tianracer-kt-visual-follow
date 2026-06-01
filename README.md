# KT Demo Workspace

Git root: `E:\research\1\kt\work_src`

This workspace has a single recommended KT demo path for presentation and reproduction.

## Operator Commands

```powershell
cd E:\research\1\kt\work_src
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_ros2_overlay.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\status_ros2_overlay.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_ros2_overlay.ps1
```

## Recommended Entry Points

- `scripts/start_ros2_overlay.ps1`
- `scripts/status_ros2_overlay.ps1`
- `scripts/stop_ros2_overlay.ps1`
- `scripts/kt_demo_preflight.ps1`
- `scripts/kt_demo_sync_follow_v4.ps1`
- `scripts/kt_demo_follow_v4_hover.ps1`
- `scripts/kt_demo_hover_gate.ps1`
- `scripts/kt_demo_ground_gate.ps1`
- `scripts/kt_demo_follow_v4_ground.ps1`
- `scripts/kt_demo_capture_readiness.ps1`
- `scripts/kt_demo_hover_check.ps1`
- `scripts/kt_demo_ground_cycle.ps1`
- `scripts/kt_demo_topic_inventory.ps1`
- `scripts/kt_demo_summary.ps1`
- `scripts/kt_demo_report_draft.ps1`
- `tools/bear_overlay_prod.html`

## Formal Control Chain

`/kt_follow/mode` + `/bear_detection/targets` + `/tianracer/scan` -> `kt_follow_controller_v4.py` -> `/ackermann_cmd`

## Current Verified Status

- hover steering follow verified
- OFF stop/release verified
- rear-wheel automatic speed handoff not yet closed
- RC can drive rear wheel
- ground full follow not yet claimed

## Important Boundaries

- The formal page is `bear_overlay_prod.html`, not `bear_overlay.html`.
- The formal controller is `kt_follow_controller_v4.py`, not `kt_smooth_follow_controller_v3.py`.
- Sync `kt_follow_controller_v4.py` to the board with `scripts/kt_demo_sync_follow_v4.ps1` before the first hover/ground run on a fresh robot workspace.
- Ground-run scripts are intentionally gated: run `scripts/kt_demo_ground_gate.ps1`, then pass `-Armed` / `-ExecuteGroundRun` explicitly for the first live ground attempt.
- `scripts/kt_demo_hover_gate.ps1` converts a hover artifact into a pass/fail gate; `kt_demo_ground_gate.ps1` now requires a passing hover-gate artifact.
- Both gates are freshness-aware by default: hover evidence and hover-gate artifacts older than 30 minutes are treated as stale.
- `kt_demo_ground_gate.ps1` now also refuses hover-gate artifacts that are not based on the latest raw `kt-demo-hover-*.txt` evidence.
- `kt_demo_ground_gate.ps1` also saves `reports/artifacts/kt-demo-ground-gate-*.txt` for the pre-ground safety record.
- `scripts/kt_demo_summary.ps1 -IncludeArtifactPaths` gives one operator-facing snapshot across readiness / hover / hover-gate / ground-gate / ground artifacts, including hover freshness and whether the current gate is based on the latest raw hover run.
- `scripts/kt_demo_report_draft.ps1` generates a conservative markdown report draft from the latest artifacts.
- The formal path is ROS2-only with LDS_E110.
- The web page does not directly control the chassis.

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

See `reports/R2-L-F5-F6-demo-workspace-runbook.md` for the operator runbook.

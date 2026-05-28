# KT Demo Operator Entry

Git root: `E:\research\1\kt\work_src`

Operator commands:

```powershell
cd E:\research\1\kt\work_src
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\start_ros2_overlay.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\status_ros2_overlay.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File .\scripts\stop_ros2_overlay.ps1
```

Web: `tools\bear_overlay_prod.html`

Formal chain: `/kt_follow/mode + /bear_detection/targets + /tianracer/scan -> kt_follow_controller_v4.py -> /ackermann_cmd -> tianracer_core`

Current verified status:

- hover steering follow verified
- OFF stop/release verified
- rear-wheel automatic speed handoff not yet closed
- RC can drive rear wheel
- ground full follow not yet claimed

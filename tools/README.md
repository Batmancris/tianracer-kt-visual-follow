# tools

PC-side debugging utilities.

## bear_overlay_prod.html

Formal demo page.

- Displays `/tianracer/camera/image_compressed`
- Draws `/bear_detection/targets`
- Publishes `/kt_follow/mode`
- Does NOT expose direct chassis control
- Loads `roslib.min.js` from the same directory

## bear_overlay.html

Browser-based debug page for bear detection overlay visualization.

This file is retained as a legacy debug page.
For the formal demo/product path, use `bear_overlay_prod.html`.

### Usage

1. For the formal demo path, open `bear_overlay_prod.html` in a PC browser.
2. Open `bear_overlay.html` only if you explicitly need the legacy debug surface.
3. Set Vehicle IP to `192.168.128.10`.
4. Click **Connect**.

### Connection

- Rosbridge: `ws://192.168.128.10:9090`
- Image topic: `/tianracer/camera/image_compressed`
- Target topic: `/bear_detection/targets`

### Features

- Canvas-only rendering: both camera image and bounding boxes drawn on `<canvas>`.
- Coordinate mapping debug: `actual_media_rect`, `computed_display_rect`, `rect_mismatch`.
- **Mapping Self Test** button for offline bbox alignment verification.
- Three target modes: `real_targets`, `mock_targets`, `self_test`.

### Safety

- **Read-only** debug page.
- Does NOT control the vehicle.
- Does NOT publish `/cmd_vel`.
- Does NOT publish `/ackermann_cmd`.

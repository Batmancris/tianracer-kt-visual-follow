# tools

PC-side debugging utilities.

## bear_overlay.html

Browser-based debug page for bear detection overlay visualization.

### Usage

1. Open `bear_overlay.html` in a PC browser (Chrome recommended).
2. Set Vehicle IP to `192.168.128.10`.
3. Click **Connect**.

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

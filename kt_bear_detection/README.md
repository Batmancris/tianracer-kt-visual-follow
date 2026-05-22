# kt_bear_detection

KT tianracer 小熊检测包。订阅标准 `sensor_msgs/Image`，发布 `ai_msgs/PerceptionTargets`。
只做检测，不控制车。

## 输入

| Topic | 类型 | 说明 |
|-------|------|------|
| `/tianracer/camera/image_raw` | `sensor_msgs/msg/Image` | usb_cam 发布的原始图像 |

## 输出

| Topic | 类型 | 说明 |
|-------|------|------|
| `/bear_detection/targets` | `ai_msgs/msg/PerceptionTargets` | 检测结果，target.type = "bear" |

## 与 rm_bear_detection 的区别

| 项目 | rm_bear_detection | kt_bear_detection |
|------|-------------------|-------------------|
| 输入 topic | `/hbmem_img` (hbm_img_msgs/HbmMsg1080P) | `/tianracer/camera/image_raw` (sensor_msgs/Image) |
| 输入格式 | NV12 共享内存 | BGR8 via cv_bridge |
| 前处理 | hobot_cv NV12 resize + letterbox | OpenCV BGR resize + BGR→NV12 + letterbox |
| 控制车 | 无（但为云台桥接节点提供输入） | 无，纯检测 |
| 模型 | bear_yolov8n_x5_640_nv12.bin | 同一模型文件 |

## 参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `image_topic` | `/tianracer/camera/image_raw` | 输入图像 topic |
| `output_topic` | `/bear_detection/targets` | 输出检测 topic |
| `model_path` | 包内 config/bear_yolov8n_x5_640_nv12.bin | 模型文件路径 |
| `target_type` | `bear` | 检测目标类型名 |
| `box_format` | `cxcywh` | YOLO 框格式 |
| `score_threshold` | `0.71` | 置信度阈值 |
| `nms_threshold` | `0.70` | NMS 阈值 |
| `stable_required_hits` | `2` | 稳定滤波所需连续命中帧数 |
| `publish_debug_log` | `true` | 是否打印检测日志 |

## 后续验证

通过 `bear_overlay.html` 页面订阅 `/bear_detection/targets`，在浏览器中观察检测框是否正确叠加在摄像头画面上。

## 板端构建

```bash
colcon build \
  --packages-select kt_bear_detection \
  --executor sequential \
  --parallel-workers 1 \
  --cmake-args -DCMAKE_BUILD_TYPE=RelWithDebInfo
```

## 板端运行

```bash
ros2 launch kt_bear_detection kt_bear_detection.launch.py
```

import importlib.util
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "kt_mjpeg_bridge.py"


def load_bridge_module():
    rclpy = types.ModuleType("rclpy")
    rclpy.init = lambda: None
    rclpy.ok = lambda: True
    rclpy.shutdown = lambda: None
    rclpy.spin_once = lambda *args, **kwargs: None

    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = type("Node", (), {})

    rclpy_qos = types.ModuleType("rclpy.qos")
    rclpy_qos.HistoryPolicy = types.SimpleNamespace(KEEP_LAST="KEEP_LAST")
    rclpy_qos.ReliabilityPolicy = types.SimpleNamespace(BEST_EFFORT="BEST_EFFORT")

    class QoSProfile:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    rclpy_qos.QoSProfile = QoSProfile

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.CompressedImage = type("CompressedImage", (), {})
    sensor_msgs.msg = sensor_msgs_msg

    sys.modules.setdefault("rclpy", rclpy)
    sys.modules.setdefault("rclpy.node", rclpy_node)
    sys.modules.setdefault("rclpy.qos", rclpy_qos)
    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs_msg)

    spec = importlib.util.spec_from_file_location("kt_mjpeg_bridge_tested", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class MjpegBridgeTests(unittest.TestCase):
    def test_source_removes_preview_processing_defaults(self):
        source = MODULE_PATH.read_text(encoding="utf-8")
        banned_tokens = [
            "from PIL import Image",
            "preview-width",
            "preview-height",
            "preview-quality",
            "Image.open",
            "resize(",
            "image.save",
            "/frame_preview.jpg",
        ]
        for token in banned_tokens:
            self.assertNotIn(token, source)

    def test_parse_args_accepts_runtime_args_without_preview_flags(self):
        module = load_bridge_module()
        args = module.parse_args(["--port", "8080", "--fps", "12"])
        self.assertEqual(args.port, 8080)
        self.assertEqual(args.fps, 12)
        self.assertFalse(hasattr(args, "preview_width"))
        self.assertFalse(hasattr(args, "preview_height"))
        self.assertFalse(hasattr(args, "preview_quality"))

    def test_latest_buffer_exposes_required_status_and_latest_seq(self):
        module = load_bridge_module()
        buffer = module.LatestJpegBuffer(fps_limit=12)
        buffer.update(b"frame-1", 10, 100)
        buffer.update(b"frame-2", 11, 200)

        frame_info = buffer.wait_for_frame(last_seq=0, timeout=0.0)
        self.assertEqual(frame_info["seq"], 2)
        self.assertEqual(frame_info["frame"], b"frame-2")
        self.assertEqual(frame_info["skipped"], 1)

        status = buffer.get_status()
        self.assertEqual(status["output_fps_limit"], 12)
        self.assertEqual(status["total_frames_rx"], 2)
        self.assertEqual(status["total_frames_skipped"], 1)
        self.assertIn("source_fps_est", status)
        self.assertIn("client_count", status)
        self.assertIn("last_frame_age_ms", status)
        self.assertIn("total_frames_sent", status)


if __name__ == "__main__":
    unittest.main()

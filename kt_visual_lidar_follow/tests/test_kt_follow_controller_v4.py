import importlib.util
import math
import sys
import types
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "scripts" / "kt_follow_controller_v4.py"


def load_controller_module():
    rclpy = types.ModuleType("rclpy")
    rclpy.init = lambda *args, **kwargs: None
    rclpy.ok = lambda: True
    rclpy.shutdown = lambda: None
    rclpy.spin = lambda *args, **kwargs: None

    rclpy_node = types.ModuleType("rclpy.node")
    rclpy_node.Node = type("Node", (), {})

    rclpy_qos = types.ModuleType("rclpy.qos")
    rclpy_qos.DurabilityPolicy = types.SimpleNamespace(VOLATILE="VOLATILE")
    rclpy_qos.ReliabilityPolicy = types.SimpleNamespace(RELIABLE="RELIABLE")

    class QoSProfile:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    class SensorDataQoS:
        def __call__(self):
            return QoSProfile()

    rclpy_qos.QoSProfile = QoSProfile
    rclpy_qos.SensorDataQoS = SensorDataQoS

    ackermann_msgs = types.ModuleType("ackermann_msgs")
    ackermann_msgs_msg = types.ModuleType("ackermann_msgs.msg")
    ackermann_msgs_msg.AckermannDrive = type("AckermannDrive", (), {})
    ackermann_msgs.msg = ackermann_msgs_msg

    ai_msgs = types.ModuleType("ai_msgs")
    ai_msgs_msg = types.ModuleType("ai_msgs.msg")
    ai_msgs_msg.PerceptionTargets = type("PerceptionTargets", (), {})
    ai_msgs.msg = ai_msgs_msg

    sensor_msgs = types.ModuleType("sensor_msgs")
    sensor_msgs_msg = types.ModuleType("sensor_msgs.msg")
    sensor_msgs_msg.LaserScan = type("LaserScan", (), {})
    sensor_msgs.msg = sensor_msgs_msg

    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.String = type("String", (), {})
    std_msgs.msg = std_msgs_msg

    sys.modules.setdefault("rclpy", rclpy)
    sys.modules.setdefault("rclpy.node", rclpy_node)
    sys.modules.setdefault("rclpy.qos", rclpy_qos)
    sys.modules.setdefault("ackermann_msgs", ackermann_msgs)
    sys.modules.setdefault("ackermann_msgs.msg", ackermann_msgs_msg)
    sys.modules.setdefault("ai_msgs", ai_msgs)
    sys.modules.setdefault("ai_msgs.msg", ai_msgs_msg)
    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs_msg)
    sys.modules.setdefault("std_msgs", std_msgs)
    sys.modules.setdefault("std_msgs.msg", std_msgs_msg)

    spec = importlib.util.spec_from_file_location("kt_follow_controller_v4_tested", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FollowControllerV4Tests(unittest.TestCase):
    def test_parse_args_accepts_scan_topic_override(self):
        module = load_controller_module()
        config = module.parse_args(["--scan-topic", "/tianracer/scan_raw"])
        self.assertEqual(config.scan_topic, "/tianracer/scan_raw")

    def test_compute_image_theta_limits_reports_symmetric_edges(self):
        module = load_controller_module()
        left_theta, right_theta = module.compute_image_theta_limits(640.0, 70.0)
        self.assertLess(left_theta, 0.0)
        self.assertGreater(right_theta, 0.0)
        self.assertAlmostEqual(abs(left_theta), right_theta, places=6)
        self.assertAlmostEqual(left_theta, module.compute_theta_raw(0.0, 640.0, 70.0), places=6)
        self.assertAlmostEqual(right_theta, module.compute_theta_raw(640.0, 640.0, 70.0), places=6)
        self.assertAlmostEqual(math.degrees(right_theta), 35.0, delta=0.5)

    def test_extract_scan_distance_expands_search_when_primary_window_is_empty(self):
        module = load_controller_module()
        ranges = [float("inf")] * 9
        ranges[6] = 0.92
        scan = module.ScanWindow(
            angle_min=math.radians(-20.0),
            angle_increment=math.radians(5.0),
            ranges=ranges,
        )

        result = module.extract_scan_distance(
            scan=scan,
            theta_raw=0.0,
            angle_window_deg=4.0,
            range_min=0.15,
            range_max=3.0,
        )

        self.assertAlmostEqual(result.distance, 0.92, places=3)
        self.assertEqual(result.valid_scan_pts, 1)

    def test_extract_scan_distance_prefers_primary_window_when_it_has_data(self):
        module = load_controller_module()
        ranges = [float("inf")] * 9
        ranges[4] = 0.88
        ranges[6] = 0.52
        scan = module.ScanWindow(
            angle_min=math.radians(-20.0),
            angle_increment=math.radians(5.0),
            ranges=ranges,
        )

        result = module.extract_scan_distance(
            scan=scan,
            theta_raw=0.0,
            angle_window_deg=4.0,
            range_min=0.15,
            range_max=3.0,
        )

        self.assertAlmostEqual(result.distance, 0.88, places=3)
        self.assertEqual(result.valid_scan_pts, 1)


if __name__ == "__main__":
    unittest.main()

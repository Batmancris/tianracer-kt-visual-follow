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

    nav_msgs = types.ModuleType("nav_msgs")
    nav_msgs_msg = types.ModuleType("nav_msgs.msg")
    nav_msgs_msg.Odometry = type("Odometry", (), {})
    nav_msgs.msg = nav_msgs_msg

    std_msgs = types.ModuleType("std_msgs")
    std_msgs_msg = types.ModuleType("std_msgs.msg")
    std_msgs_msg.String = type("String", (), {})
    std_msgs.msg = std_msgs_msg

    # Mock rclpy.utilities for remove_ros_args
    rclpy_utilities = types.ModuleType("rclpy.utilities")
    def _mock_remove_ros_args(args=None):
        """Simple mock: strip --ros-args and everything after it."""
        if args is None:
            args = sys.argv
        result = []
        skip = False
        for arg in args:
            if arg == "--ros-args":
                skip = True
                continue
            if not skip:
                result.append(arg)
        return result
    rclpy_utilities.remove_ros_args = _mock_remove_ros_args

    sys.modules.setdefault("rclpy", rclpy)
    sys.modules.setdefault("rclpy.node", rclpy_node)
    sys.modules.setdefault("rclpy.qos", rclpy_qos)
    sys.modules.setdefault("rclpy.utilities", rclpy_utilities)
    sys.modules.setdefault("ackermann_msgs", ackermann_msgs)
    sys.modules.setdefault("ackermann_msgs.msg", ackermann_msgs_msg)
    sys.modules.setdefault("ai_msgs", ai_msgs)
    sys.modules.setdefault("ai_msgs.msg", ai_msgs_msg)
    sys.modules.setdefault("sensor_msgs", sensor_msgs)
    sys.modules.setdefault("sensor_msgs.msg", sensor_msgs_msg)
    sys.modules.setdefault("nav_msgs", nav_msgs)
    sys.modules.setdefault("nav_msgs.msg", nav_msgs_msg)
    sys.modules.setdefault("std_msgs", std_msgs)
    sys.modules.setdefault("std_msgs.msg", std_msgs_msg)

    spec = importlib.util.spec_from_file_location("kt_follow_controller_v4_tested", MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class FollowControllerV4Tests(unittest.TestCase):
    def test_parse_args_accepts_scan_topic_override(self):
        module = load_controller_module()
        config = module.parse_args(["--scan-topic", "/tianracer/scan_raw"])
        self.assertEqual(config.scan_topic, "/tianracer/scan_raw")

    def test_parse_args_ignores_ros_args(self):
        """Verify parse_args handles ROS2 launch-injected --ros-args."""
        module = load_controller_module()
        # Simulate ROS2 launch passing: --ros-args -r __node:=kt_follow_controller_v4
        argv = ["--enable-control", "false", "--ros-args", "-r", "__node:=kt_follow_controller_v4"]
        config = module.parse_args(argv)
        self.assertFalse(config.enable_control)
        self.assertEqual(config.scan_topic, "/tianracer/scan")  # default preserved

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

    def test_parse_args_accepts_ackermann_cmd_topic_override(self):
        module = load_controller_module()
        config = module.parse_args(["--ackermann-cmd-topic", "/tianracer/ackermann_cmd"])
        self.assertEqual(config.ackermann_cmd_topic, "/tianracer/ackermann_cmd")

    def test_parse_args_accepts_targets_topic_override(self):
        module = load_controller_module()
        config = module.parse_args(["--targets-topic", "/bear_detection/targets"])
        self.assertEqual(config.targets_topic, "/bear_detection/targets")

    def test_parse_args_accepts_new_longitudinal_parameters(self):
        module = load_controller_module()
        config = module.parse_args(
            [
                "--odom-topic",
                "/odom_raw",
                "--restart-distance-m",
                "0.75",
                "--slow-speed-mps",
                "0.36",
                "--fast-speed-mps",
                "0.52",
                "--min-effective-speed-mps",
                "0.31",
                "--stop-decel-mps2",
                "0.9",
                "--stop-margin-m",
                "0.09",
                "--max-valid-odom-age-ms",
                "250",
                "--max-valid-range-age-ms",
                "260",
            ]
        )
        self.assertEqual(config.odom_topic, "/odom_raw")
        self.assertAlmostEqual(config.restart_distance_m, 0.75)
        self.assertAlmostEqual(config.slow_speed_mps, 0.36)
        self.assertAlmostEqual(config.fast_speed_mps, 0.52)
        self.assertAlmostEqual(config.min_effective_speed_mps, 0.31)
        self.assertAlmostEqual(config.stop_decel_mps2, 0.9)
        self.assertAlmostEqual(config.stop_margin_m, 0.09)
        self.assertEqual(config.max_valid_odom_age_ms, 250)
        self.assertEqual(config.max_valid_range_age_ms, 260)

    def test_longitudinal_stops_when_odom_is_stale(self):
        module = load_controller_module()
        config = module.ControllerConfig()
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_FAST,
            config=config,
            range_m=1.8,
            v_odom=0.4,
            range_is_valid=True,
            odom_is_fresh=False,
        )
        self.assertEqual(decision.state, module.LongitudinalState.IDLE)
        self.assertEqual(decision.cmd_speed, 0.0)

    def test_longitudinal_stops_when_range_is_invalid(self):
        module = load_controller_module()
        config = module.ControllerConfig()
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_SLOW,
            config=config,
            range_m=float("nan"),
            v_odom=0.2,
            range_is_valid=False,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.IDLE)
        self.assertEqual(decision.cmd_speed, 0.0)

    def test_longitudinal_enters_brake_when_stop_distance_exceeds_remaining_distance(self):
        module = load_controller_module()
        config = module.ControllerConfig(
            target_distance_m=0.50,
            stop_decel_mps2=0.80,
            stop_margin_m=0.08,
        )
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_FAST,
            config=config,
            range_m=0.70,
            v_odom=0.50,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.BRAKE)
        self.assertEqual(decision.cmd_speed, 0.0)

    def test_hold_does_not_restart_before_restart_distance(self):
        module = load_controller_module()
        config = module.ControllerConfig(target_distance_m=0.50, restart_distance_m=0.70)
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.HOLD,
            config=config,
            range_m=0.69,
            v_odom=0.0,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.HOLD)
        self.assertEqual(decision.cmd_speed, 0.0)

    def test_hold_restarts_only_after_restart_distance(self):
        module = load_controller_module()
        config = module.ControllerConfig(
            target_distance_m=0.50,
            restart_distance_m=0.70,
            slow_speed_mps=0.35,
        )
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.HOLD,
            config=config,
            range_m=0.75,
            v_odom=0.0,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.APPROACH_SLOW)
        self.assertEqual(decision.cmd_speed, 0.35)

    def test_longitudinal_never_outputs_positive_speed_below_deadband(self):
        module = load_controller_module()
        config = module.ControllerConfig(
            target_distance_m=0.50,
            restart_distance_m=0.70,
            slow_speed_mps=0.20,
            fast_speed_mps=0.25,
            min_effective_speed_mps=0.30,
        )
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_SLOW,
            config=config,
            range_m=0.90,
            v_odom=0.0,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertIn(decision.cmd_speed, (0.0, 0.30))
        self.assertFalse(0.0 < decision.cmd_speed < 0.30)

    def test_longitudinal_uses_fast_speed_for_far_distance(self):
        module = load_controller_module()
        config = module.ControllerConfig(
            target_distance_m=0.50,
            fast_speed_mps=0.50,
            min_effective_speed_mps=0.30,
        )
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_SLOW,
            config=config,
            range_m=1.60,
            v_odom=0.0,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.APPROACH_FAST)
        self.assertEqual(decision.cmd_speed, 0.50)

    def test_longitudinal_uses_slow_speed_for_mid_distance(self):
        module = load_controller_module()
        config = module.ControllerConfig(
            target_distance_m=0.50,
            slow_speed_mps=0.35,
            fast_speed_mps=0.50,
            min_effective_speed_mps=0.30,
        )
        decision = module.compute_longitudinal_step(
            current_state=module.LongitudinalState.APPROACH_FAST,
            config=config,
            range_m=1.00,
            v_odom=0.0,
            range_is_valid=True,
            odom_is_fresh=True,
        )
        self.assertEqual(decision.state, module.LongitudinalState.APPROACH_SLOW)
        self.assertEqual(decision.cmd_speed, 0.35)


if __name__ == "__main__":
    unittest.main()

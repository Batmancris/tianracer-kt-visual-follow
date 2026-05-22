#!/usr/bin/env python3

import os
import sys
import time
import yaml

# Ensure stdlib platform is used (avoid shadowing by local platform package path)
import platform as _stdlib_platform  # noqa: E402
sys.modules['platform'] = _stdlib_platform

# Add src to path just in case, though catkin setup should handle it
# sys.path.append(os.path.join(os.path.dirname(__file__), '../src'))

from robot_check.logger import CheckLogger
from robot_check.platform import get_platform
from robot_check.checkers import PassiveChecker, TFChecker, MotionChecker, WifiChecker

def load_config(yaml_path):
    with open(yaml_path, 'r') as f:
        return yaml.safe_load(f)

def main():
    # 1. 初始化日志
    # Logger 内部现在使用 get_platform() 来查找路径，也兼容无 ROS 环境
    logger = CheckLogger("TianRacerCheck")
    logger.log_info("Initializing Auto Check Procedure...")

    # 2. 初始化平台 (ROS)
    platform = get_platform()
    try:
        platform.init_node('tianracer_auto_check')
    except Exception as e:
        logger.log_error(f"Failed to init ROS node: {e}")
        return

    # 3. 加载配置
    try:
        pkg_path = platform.get_package_path('robot_check')
        if not pkg_path:
             # Fallback for testing without install
             pkg_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
             
        config_path = os.path.join(pkg_path, 'config', 'check_params.yaml')

        if not os.path.exists(config_path):
             logger.log_error(f"Config file not found: {config_path}")
             return

        config = load_config(config_path)
        logger.log_info(f"Loaded config from {config_path}")
        if 'global' in config:
            logger.apply_config(config['global'])
    except Exception as e:
        logger.log_error(f"Failed to load config: {e}")
        return

    # 4. 执行测试
    try:
        # 4.1 硬件/传感器检查
        logger.log_info(">>> STEP 1: Passive Sensor Checks")
        if 'passive_checks' in config:
            checker = PassiveChecker(platform, logger)
            checker.run(config['passive_checks'])

        # 4.2 TF 检查
        logger.log_info(">>> STEP 2: TF Tree Checks")
        if 'tf_check' in config:
            checker = TFChecker(platform, logger)
            checker.run(config['tf_check'])

        # 4.3 运动检查
        logger.log_info(">>> STEP 3: Motion Checks")
        if 'motion_check' in config:
            # 简单安全检查：确保前面关键传感器通过
            # TODO: add logic to skip if odom/scan failed
            checker = MotionChecker(platform, logger)
            checker.run(config['motion_check'])

        # 4.4 硬件状态检查 (WiFi等)
        logger.log_info(">>> STEP 4: Hardware Checks")
        if 'wifi_check' in config:
             checker = WifiChecker(platform, logger)
             checker.run(config['wifi_check'])
    except Exception as e:
        logger.log_error(f"Error during checks: {e}")
        import traceback
        logger.log_error(traceback.format_exc())

    # 5. 生成报告总结
    logger.print_summary_table()
    logger.save_summary_report()
    logger.log_info("=== Check Procedure Finished ===")
    logger.log_info(f"Report saved to: {logger.log_path}")

    # 6. 自动退出
    auto_close = platform.get_param("~auto_close", True)
    if auto_close:
        logger.log_info("Auto closing in 3 seconds...")
        platform.sleep(3.0)
        # 尝试自然退出，如果被 launch required=true 捕获则会杀掉整个组
        sys.exit(0)

if __name__ == "__main__":
    main()

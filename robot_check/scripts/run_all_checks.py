#!/usr/bin/env python3

# Force stdlib platform before any ROS/rospy imports to avoid shadowing by package paths
import platform as _stdlib_platform  # noqa: E402
import sys  # noqa: E402
sys.modules['platform'] = _stdlib_platform

from robot_check.run_checks import main

if __name__ == "__main__":
    main()

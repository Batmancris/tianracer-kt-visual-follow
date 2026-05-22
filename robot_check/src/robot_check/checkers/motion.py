import numpy as np
from .base import BaseChecker

class MotionChecker(BaseChecker):
    def run(self, motion_config):
        """
        MVP: 简单的运动前后检查
        """
        if not motion_config.get('enabled', False):
            self.logger.log_info("Motion check disabled in config.")
            return

        self.logger.log_info("====== Starting Motion Checks ======")

        # Linear Check
        self.run_linear_check(motion_config)
        
        # Angular Check
        self.run_angular_check(motion_config)

    def run_linear_check(self, motion_config):
        pub_freq = motion_config.get('publish_frequency', 20.0)
        sleep_time = 1.0 / pub_freq if pub_freq > 0 else 0.05
        
        lin_cfg = motion_config.get('linear', {})
        target_dist = lin_cfg.get('expected_dist', 1.0)
        vel = lin_cfg.get('command_vel', 0.1)
        duration = lin_cfg.get('duration', 5.0)

        # 1. Record Start
        start_pose = self.platform.get_odom_pose()
        start_scan_front = self.platform.get_lidar_range(0.0)
        start_scan_left = self.platform.get_lidar_range(90.0)

        if start_pose is None:
            self.logger.log_result("Motion_Linear", "FAIL", {'error': 'No Odom data'})
            return

        # 2. Move Forward
        scan_info = f"Front: {start_scan_front:.3f}m, Left: {start_scan_left:.3f}m" if (start_scan_front is not None and start_scan_left is not None) else "Scan: None"
        self.logger.log_info(f"Moving forward at {vel} m/s for {duration} s... ({scan_info})")
        start_time = self.platform.get_time()

        observed_velocities = []

        # New: Safety and Loop logic
        safety_dist_min = lin_cfg.get('safety_dist_min', 0.3)
        safety_stop_triggered = False

        while (self.platform.get_time() - start_time) < duration:
            # 2.1 Safety Check
            curr_front = self.platform.get_lidar_range(0.0)
            if curr_front is not None and curr_front != float('inf') and curr_front < safety_dist_min:
                 self.logger.log_info(f"Safety Stop Triggered! Obstacle at {curr_front:.3f}m")
                 safety_stop_triggered = True
                 break

            self.platform.pub_cmd_vel(vel, 0.0)

            # 采集速度反馈
            twist = self.platform.get_odom_twist()
            if twist:
                observed_velocities.append(twist[0])

            self.platform.sleep(sleep_time)

        self.platform.pub_cmd_vel(0.0, 0.0)
        self.platform.sleep(1.0) # Wait for stop

        # 3. Record End
        end_pose = self.platform.get_odom_pose()
        end_scan_front = self.platform.get_lidar_range(0.0)
        self.logger.log_info(f"Finished linear motion.")

        # 4. Verify
        dist_moved = np.hypot(end_pose[0] - start_pose[0], end_pose[1] - start_pose[1])
        max_vel = np.max(np.abs(observed_velocities)) if observed_velocities else 0.0
        avg_vel = np.mean(np.abs(observed_velocities)) if observed_velocities else 0.0
        is_moving = max_vel > (vel * 0.2)

        metrics = {
            'expected_dist': target_dist,
            'actual_dist': round(dist_moved, 3),
            'max_vel': round(max_vel, 3),
            'avg_vel': round(avg_vel, 3)
        }

        if safety_stop_triggered:
             metrics['note'] = "Safety Break Triggered"
             self.logger.log_result("Motion_Linear_Safety", "PASS", metrics)
        elif is_moving:
            self.logger.log_result("Motion_Linear", "PASS", metrics)
        else:
            metrics['reason'] = "No velocity feedback from encoders"
            self.logger.log_result("Motion_Linear", "FAIL", metrics)

        # Advanced: Odom Accuracy (Forward)
        if lin_cfg.get('check_odom_accuracy', False) and not safety_stop_triggered:
             self._check_odom_accuracy(start_scan_front, end_scan_front, dist_moved, lin_cfg, "Motion_Odom_Accuracy")
        
        # Reverse Motion Check
        self.run_reverse_check(motion_config, pub_freq)


    def run_reverse_check(self, motion_config, pub_freq):
        # ... Similar logic for reverse ...
        lin_cfg = motion_config.get('linear', {})
        sleep_time = 1.0 / pub_freq if pub_freq > 0 else 0.05

        self.logger.log_info("Starting backward (reverse) linear motion test...")
        
        start_pose_b = self.platform.get_odom_pose()
        start_front = self.platform.get_lidar_range(0.0)
        
        back_vel = -lin_cfg.get('command_vel', 1.0)
        back_duration = lin_cfg.get('duration', 1.0)
        
        self.logger.log_info(f"Moving backward at {abs(back_vel)} m/s for {back_duration} s...")

        start_time_b = self.platform.get_time()
        observed_velocities_b = []
        safety_stop_triggered_b = False

        while (self.platform.get_time() - start_time_b) < back_duration:
            curr_rear = self.platform.get_lidar_range(180.0)
            if curr_rear is not None and curr_rear != float('inf') and curr_rear < lin_cfg.get('safety_dist_min', 0.3):
                self.logger.log_info(f"Safety Stop (reverse) Triggered!")
                safety_stop_triggered_b = True
                break

            self.platform.pub_cmd_vel(back_vel, 0.0)
            twist = self.platform.get_odom_twist()
            if twist:
                observed_velocities_b.append(twist[0])

            self.platform.sleep(sleep_time)

        self.platform.pub_cmd_vel(0.0, 0.0)
        self.platform.sleep(1.0)

        end_pose_b = self.platform.get_odom_pose()
        end_front = self.platform.get_lidar_range(0.0)
        
        dist_moved_b = np.hypot(end_pose_b[0] - start_pose_b[0], end_pose_b[1] - start_pose_b[1])
        max_vel_b = np.max(np.abs(observed_velocities_b)) if observed_velocities_b else 0.0
        avg_vel_b = np.mean(np.abs(observed_velocities_b)) if observed_velocities_b else 0.0

        metrics_b = {
            'actual_dist': round(dist_moved_b, 3),
            'max_vel': round(max_vel_b, 3),
            'avg_vel': round(avg_vel_b, 3)
        }
        is_moving_b = max_vel_b > (abs(back_vel) * 0.2)

        if safety_stop_triggered_b:
            metrics_b['note'] = 'Safety Break Triggered (reverse)'
            self.logger.log_result("Motion_Linear_Reverse_Safety", "PASS", metrics_b)
        elif is_moving_b:
            self.logger.log_result("Motion_Linear_Reverse", "PASS", metrics_b)
        else:
            metrics_b['reason'] = 'No velocity feedback'
            self.logger.log_result("Motion_Linear_Reverse", "FAIL", metrics_b)

    def run_angular_check(self, motion_config):
        ang_cfg = motion_config.get('angular', {})
        if not ang_cfg.get('enabled', True):
            return
            
        self.logger.log_info("Starting angular motion test...")
        
        pub_freq = motion_config.get('publish_frequency', 20.0)
        sleep_time = 1.0 / pub_freq if pub_freq > 0 else 0.05

        # 1. Record Start
        p1_odom = self.platform.get_odom_pose()
        p1_imu_yaw = self.platform.get_imu_yaw()
        
        if p1_odom is None or p1_imu_yaw is None:
            self.logger.log_result("Motion_Angular", "FAIL", {'reason': "No Odom or IMU Data"})
            return

        cmd_vel = ang_cfg.get('command_vel', 0.0) 
        cmd_ang = ang_cfg.get('command_ang', 0.5) 
        target_angle = np.deg2rad(ang_cfg.get('expected_ang_deg', 90.0))
        max_duration = ang_cfg.get('timeout', 10.0)

        start_yaw = p1_imu_yaw
        start_time_turn = self.platform.get_time()

        while (self.platform.get_time() - start_time_turn) < max_duration:
            curr_yaw = self.platform.get_imu_yaw()
            if curr_yaw is not None:
                diff = curr_yaw - start_yaw
                while diff > np.pi: diff -= 2*np.pi
                while diff < -np.pi: diff += 2*np.pi
                if diff >= target_angle:
                    break
            self.platform.pub_cmd_vel(cmd_vel, cmd_ang)
            self.platform.sleep(sleep_time)

        self.platform.pub_cmd_vel(0.0, 0.0)
        self.platform.sleep(1.5)

        # 2. Results
        p2_odom = self.platform.get_odom_pose()
        p2_imu_yaw = self.platform.get_imu_yaw()

        passed_angle = True
        angle_metrics = {}
        tol_angle_rad = np.deg2rad(ang_cfg.get('ang_tol_deg', 5.0))

        # Check IMU Angle
        if p1_imu_yaw is not None and p2_imu_yaw is not None:
            imu_yaw_diff = p2_imu_yaw - p1_imu_yaw
            while imu_yaw_diff > np.pi: imu_yaw_diff -= 2*np.pi
            while imu_yaw_diff < -np.pi: imu_yaw_diff += 2*np.pi
            angle_metrics['imu_deg'] = round(np.rad2deg(imu_yaw_diff), 2)
            if abs(imu_yaw_diff - target_angle) > tol_angle_rad:
                 passed_angle = False

        if passed_angle:
            self.logger.log_result("Motion_Angular_Rotation", "PASS", angle_metrics)
        else:
            self.logger.log_result("Motion_Angular_Rotation", "FAIL", angle_metrics)

    def _check_odom_accuracy(self, start_lidar, end_lidar, odom_dist, lin_cfg, test_name):
        if (start_lidar is not None and start_lidar != float('inf') and
            end_lidar is not None and end_lidar != float('inf')):

            dist_lidar = abs(start_lidar - end_lidar)
            odom_err = abs(odom_dist - dist_lidar)
            odom_tol = lin_cfg.get('odom_accuracy_tol', 0.15)
            metrics = {
                'odom_dist': round(odom_dist, 3),
                'lidar_dist': round(dist_lidar, 3),
                'error': round(odom_err, 3),
                'tolerance': odom_tol
            }
            if odom_err < odom_tol:
                 self.logger.log_result(test_name, "PASS", metrics)
            else:
                 self.logger.log_result(test_name, "FAIL", metrics)

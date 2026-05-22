from .base import BaseChecker

class PassiveChecker(BaseChecker):
    def run(self, check_list):
        """
        运行被动传感器检查
        check_list: list of dict from yaml
        """
        self.logger.log_info("====== Starting Passive Sensor Checks ======")

        for item in check_list:
            topic = item.get('topic')

            self.logger.log_info(f"Checking {topic} ...")

            # 执行测量
            duration = item.get('timeout', 3.0)
            stats = self.platform.measure_topic_frequency(topic, item.get('type'), duration)

            # 判定逻辑
            if stats.get('error'):
                self.logger.log_result(f"Topic_{topic}", "FAIL", {'error': stats['error']})
                continue

            hz = stats.get('hz', 0)
            std = stats.get('std_dev', 0)
            frame = stats.get('frame_id', '')

            target_hz = item.get('min_hz', 0)
            max_jitter = item.get('max_jitter', None)
            require_valid = item.get('check_data_valid', False)
            data_range = item.get('check_data_range')

            # 判定
            result = "PASS"
            fail_reasons = []

            if hz < target_hz:
                result = "FAIL"
                fail_reasons.append(f"Low Hz ({hz} < {target_hz})")

            if max_jitter is not None and std > max_jitter:
                result = "FAIL"
                fail_reasons.append(f"High jitter ({std} > {max_jitter})")

            if item.get('check_frame_id') and not frame:
                result = "FAIL"
                fail_reasons.append("Missing Frame ID")

            data_valid = stats.get('data_valid')
            if require_valid and data_valid is False:
                result = "FAIL"
                fail_reasons.append("Invalid data payload")

            sample_value = stats.get('sample_value')
            if data_range:
                if sample_value is None:
                    result = "FAIL"
                    fail_reasons.append("No sample value for range check")
                else:
                    lo, hi = data_range
                    try:
                        val = float(sample_value)
                        if not (lo <= val <= hi):
                            result = "FAIL"
                            fail_reasons.append(f"Out of range ({val} not in [{lo}, {hi}])")
                    except Exception:
                        result = "FAIL"
                        fail_reasons.append("Sample value not numeric")

            metrics = {'hz': hz, 'std': std, 'frame': frame}
            if data_valid is not None:
                metrics['data_valid'] = data_valid
            if sample_value is not None:
                metrics['sample'] = sample_value
            if fail_reasons:
                metrics['reasons'] = "; ".join(fail_reasons)

            self.logger.log_result(f"Topic_{topic}", result, metrics)

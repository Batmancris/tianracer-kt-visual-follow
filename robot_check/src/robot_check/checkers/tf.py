from .base import BaseChecker

class TFChecker(BaseChecker):
    def run(self, tf_config):
        self.logger.log_info("====== Starting TF Checks ======")
        pairs = tf_config.get('required_frames', [])
        timeout = tf_config.get('timeout', 1.0)

        for parent, child in pairs:
            res = self.platform.check_tf(parent, child, timeout)
            status = "PASS" if res else "FAIL"
            self.logger.log_result(f"TF_{parent}_to_{child}", status)

import os
import sys
import logging
import datetime
import glob
from .platform import get_platform

class CheckLogger:
    def __init__(self, node_name="robot_check"):
        self.node_name = node_name

        # 1. 确定报告目录
        try:
            # 使用 platform 获取路径，不再直接依赖 rospkg
            # 但 logger 初始化可能早于 user explicit platform init?
            # get_platform() 只是获取类实例，不一定 init_node
            # 这里我们只为了获取路径
            platform = get_platform()
            pkg_path = platform.get_package_path('robot_check')
            
            if pkg_path:
                 self.report_dir = os.path.join(pkg_path, 'reports')
            else:
                 raise Exception("Package path not found")

        except Exception as e:
            # 如果找不到包 (非 ROS 环境调试或者未 source)，回退到当前目录
            # print(f"[WARN] Could not find package path: {e}. Using ./reports")
            self.report_dir = os.path.join(os.getcwd(), 'reports')

        if not os.path.exists(self.report_dir):
            os.makedirs(self.report_dir)

        # 2. 生成文件名
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_filename = f"{timestamp}.log"
        self.log_path = os.path.join(self.report_dir, self.log_filename)

        # 默认日志保留数，可由配置覆盖
        self.log_keep_count = 20

        # 3. 配置 Logging
        self.logger = logging.getLogger(node_name)
        self.logger.setLevel(logging.INFO)

        # 防止重复添加 handler
        if not self.logger.handlers:
            # File Handler
            file_handler = logging.FileHandler(self.log_path, encoding='utf-8')
            file_fmt = logging.Formatter('%(asctime)s [%(levelname)s] %(message)s')
            file_handler.setFormatter(file_fmt)
            self.logger.addHandler(file_handler)

            # Console Handler
            stream_handler = logging.StreamHandler(sys.stdout)
            stream_fmt = logging.Formatter('[%(levelname)s] %(message)s')
            stream_handler.setFormatter(stream_fmt)
            self.logger.addHandler(stream_handler)

        self.log_info(f"Log file created at: {self.log_path}")
        self._rotate_logs()

        # Storage for table summary
        self.results_list = []

    def log_info(self, msg):
        self.logger.info(msg)

    def log_warn(self, msg):
        self.logger.warning(msg)

    def log_error(self, msg):
        self.logger.error(msg)

    def log_result(self, test_name, result, metrics=None):
        """
        结构化记录测试结果
        result: "PASS" or "FAIL" or "SKIP"
        metrics: dict of values (e.g. {'hz': 10.1, 'std': 0.01})
        """
        metric_str = ""
        if metrics:
            metric_str = " | " + ", ".join([f"{k}={v}" for k, v in metrics.items()])

        msg = f"[{test_name}] >>> {result} <<<{metric_str}"
        if result == "FAIL":
            self.logger.error(msg)
        else:
            self.logger.info(msg)
        
        # Store for summary
        self.results_list.append((test_name, result, metrics))

    def print_summary_table(self):
        """Prints a summary table of all logged results."""
        if not self.results_list:
            self.log_info("No checks run.")
            return

        # Prepare table data
        headers = ["Test Item", "Result", "Details"]
        rows = []
        for name, res, metrics in self.results_list:
            detail_str = ""
            if metrics:
                 # Flatten metrics for the table
                 msg_parts = []
                 for k, v in metrics.items():
                     if isinstance(v, float):
                         msg_parts.append(f"{k}: {v:.2f}")
                     else:
                         msg_parts.append(f"{k}: {v}")
                 detail_str = ", ".join(msg_parts)
            rows.append([name, res, detail_str])
        
        # Calculate column widths
        widths = [len(h) for h in headers]
        for row in rows:
            for i, val in enumerate(row):
                widths[i] = max(widths[i], len(str(val)))
        
        # Add some padding
        widths = [w + 2 for w in widths]

        # Formatter
        def format_row(row_data):
            return "|".join(f" {str(val).ljust(w-2)} " for val, w in zip(row_data, widths))
        
        separator = "+" + "+".join("-" * w for w in widths) + "+"
        
        table_str = "\n" + separator + "\n"
        table_str += "|" + format_row(headers) + "|\n"
        
        # Double line for header
        header_sep = "+" + "+".join("=" * w for w in widths) + "+"
        table_str += header_sep + "\n"
        
        for row in rows:
            table_str += "|" + format_row(row) + "|\n"
            table_str += separator + "\n"

        self.logger.info("\n" + table_str)

    def save_summary_report(self):
        """Saves a clean Markdown summary report."""
        md_filename = self.log_filename.replace('.log', '_summary.md')
        md_path = os.path.join(self.report_dir, md_filename)
        
        with open(md_path, 'w', encoding='utf-8') as f:
            f.write(f"# TianRacer Auto Check Report\n")
            f.write(f"**Date:** {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            f.write("## Test Summary\n")
            f.write("| Test Item | Result | Details |\n")
            f.write("|-----------|--------|---------|\n")
            
            for name, res, metrics in self.results_list:
                # Format metrics nicely
                detail_str = ""
                if metrics:
                    msg_parts = []
                    for k, v in metrics.items():
                        if isinstance(v, float):
                            msg_parts.append(f"**{k}**: {v:.2f}")
                        else:
                            msg_parts.append(f"**{k}**: {v}")
                    detail_str = "<br>".join(msg_parts)
                
                # Add status icon
                icon = "✅" if res == "PASS" else "❌"
                
                f.write(f"| {name} | {icon} {res} | {detail_str} |\n")
            
            f.write("\n---\n*Generated by robot_check*\n")
            
        self.logger.info(f"Markdown summary report saved to: {md_path}")

    def apply_config(self, cfg):
        """Apply global config settings (e.g., log retention)."""
        try:
            keep = cfg.get('log_retention_count')
            if keep is not None:
                self.log_keep_count = int(keep)
                # Apply immediately so current run respects new policy
                self._rotate_logs()
        except Exception as e:
            self.logger.warning(f"Failed to apply logger config: {e}")

    def _rotate_logs(self, keep_count=None):
        """保留最近 keep_count 个日志文件，删除旧的"""
        if keep_count is None:
            keep_count = self.log_keep_count
        try:
            # 获取 reports 目录下所有 .log 文件
            files = glob.glob(os.path.join(self.report_dir, "*.log"))
            # 按修改时间排序
            files.sort(key=os.path.getmtime)

            if len(files) > keep_count:
                to_delete = files[:len(files) - keep_count]
                for f in to_delete:
                    try:
                        os.remove(f)
                        self.logger.info(f"Rotated/Deleted old log: {os.path.basename(f)}")
                    except Exception as e:
                        self.logger.warning(f"Failed to delete old log {f}: {e}")
        except Exception as e:
            self.logger.warning(f"Log rotation failed: {e}")

if __name__ == '__main__':
    # Simple test
    logger = CheckLogger("TestLogger")
    logger.log_info("Hello World")
    logger.log_warn("This is a warning")
    logger.log_result("CameraCheck", "PASS", {'hz': 30.0})
    logger.log_result("LidarCheck", "FAIL", {'reason': 'timeout'})

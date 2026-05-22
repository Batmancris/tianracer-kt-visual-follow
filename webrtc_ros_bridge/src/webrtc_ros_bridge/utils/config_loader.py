"""
配置加载工具
"""
import yaml
import os


class ConfigLoader:
    """配置文件加载器"""

    @staticmethod
    def load(config_path: str) -> dict:
        """
        加载YAML配置文件

        Args:
            config_path: 配置文件路径

        Returns:
            配置字典
        """
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Config file not found: {config_path}")

        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)

        # 验证必要字段
        ConfigLoader._validate_config(config)
        return config

    @staticmethod
    def _validate_config(config: dict):
        """验证配置完整性"""
        required_keys = ['server', 'streams', 'ros', 'media']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"Missing required config key: {key}")

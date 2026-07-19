import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.config import AppConfig


class TestConfigPersistence(unittest.TestCase):
    def setUp(self):
        self.config_path = "test_config.json"
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_persistence_of_overridden_violations(self):
        # 初始加载
        config = AppConfig.load(self.config_path)

        # 添加违规项并保存
        config.settings.overridden_violations = ["ADR-001"]
        # 目前尚未实现 save 方法，这是一个 RED 阶段测试
        config.save()

        # 重新加载
        new_config = AppConfig.load(self.config_path)
        self.assertIn("ADR-001", new_config.settings.overridden_violations)

if __name__ == "__main__":
    unittest.main()

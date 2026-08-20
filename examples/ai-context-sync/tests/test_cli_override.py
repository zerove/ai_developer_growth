import os
import sys
import unittest

from typer.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import os

from src.cli import app


class TestCLIOverride(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.config_path = "test_override_config.json"
        # 初始配置
        with open(self.config_path, "w") as f:
            json.dump({"settings": {"overridden_violations": []}}, f)

    def tearDown(self):
        if os.path.exists(self.config_path):
            os.remove(self.config_path)

    def test_override_command(self):
        # 初始未包含
        with open(self.config_path, "r") as f:
            data = json.load(f)
        self.assertNotIn("ADR-001", data["settings"]["overridden_violations"])

        # 执行 override
        result = self.runner.invoke(
            app, ["override", "ADR-001", "--config", self.config_path]
        )
        self.assertEqual(result.exit_code, 0)

        # 验证已添加
        with open(self.config_path, "r") as f:
            data = json.load(f)
        self.assertIn("ADR-001", data["settings"]["overridden_violations"])


if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest
from typer.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import app

class TestCLI(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()

    def test_cli_version(self):
        # 验证新 CLI 结构的基本调用（假设已重构为 app 作为主入口）
        result = self.runner.invoke(app, ["--help"])
        self.assertEqual(result.exit_code, 0)
        self.assertIn("Usage:", result.stdout)

if __name__ == "__main__":
    unittest.main()

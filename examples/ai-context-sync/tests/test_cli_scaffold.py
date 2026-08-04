import os
import sys
import unittest

from typer.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import os
import shutil

from src.cli import app


class TestCLIScaffold(unittest.TestCase):
    def setUp(self):
        self.runner = CliRunner()
        self.test_dir = "test_scaffold_dir"
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)
        os.makedirs(self.test_dir)
        os.chdir(self.test_dir)

    def tearDown(self):
        os.chdir("..")
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_scaffold_fails_on_non_empty_dir(self):
        with open("some_file.txt", "w") as f:
            f.write("hello")
        result = self.runner.invoke(app, ["scaffold", "nonexistent_template"])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("Directory is not empty", result.stdout)


if __name__ == "__main__":
    unittest.main()

"""案例研究验证器测试共享基类。"""

import shutil
import tempfile
import unittest
from pathlib import Path


class CaseStudyValidatorTestBase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.case_dir = Path(self.test_dir) / "test-case"
        self.case_dir.mkdir(exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def _write_case(self, content: str):
        """Write case study content to README.md"""
        (self.case_dir / "README.md").write_text(content, encoding="utf-8")

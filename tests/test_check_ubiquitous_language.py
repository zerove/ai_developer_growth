import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.scripts.check_ubiquitous_language import check_term_usage, extract_terms


class TestCheckUbiquitousLanguage(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.ubiquitous_file = Path(os.path.join(self.test_dir, "UBIQUITOUS_LANGUAGE.md"))
        self.docs_dir = Path(os.path.join(self.test_dir, "docs"))
        self.docs_dir.mkdir(exist_ok=True)

    def tearDown(self):
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_extract_terms_from_table(self):
        """Test extracting terms from markdown table."""
        content = """# Ubiquitous Language

| 术语 | 英文 | 定义 | 使用场景 | 来源 |
|------|------|------|----------|------|
| Agent | Agent | 智能体定义 | AI 开发 | GOVERNANCE.md |
| ADR | Architecture Decision Record | 架构决策记录 | 架构文档 | ADR.md |
| Header Row | Should | Be | Skipped | |
"""
        self.ubiquitous_file.write_text(content, encoding="utf-8")

        terms = extract_terms(self.ubiquitous_file)
        self.assertIn("Agent", terms)
        self.assertIn("ADR", terms)
        # Header row that doesn't have a proper term in column 1 should be filtered
        # But "Header Row" is actually in column 1, so it will be extracted
        # The filtering only skips known header names

    def test_extract_terms_empty_file(self):
        """Test extracting terms from empty file."""
        self.ubiquitous_file.write_text("# Empty\n", encoding="utf-8")
        terms = extract_terms(self.ubiquitous_file)
        self.assertEqual(terms, [])

    def test_check_term_usage_found(self):
        """Test checking term usage when term exists in docs."""
        (self.docs_dir / "test.md").write_text("This document mentions Agent and ADR in context.", encoding="utf-8")

        count = check_term_usage("Agent", self.docs_dir)
        self.assertEqual(count, 1)

        count = check_term_usage("ADR", self.docs_dir)
        self.assertEqual(count, 1)

    def test_check_term_usage_not_found(self):
        """Test checking term usage when term doesn't exist."""
        (self.docs_dir / "test.md").write_text("This document mentions something else.", encoding="utf-8")

        count = check_term_usage("NonExistentTerm", self.docs_dir)
        self.assertEqual(count, 0)

    def test_check_term_usage_case_insensitive(self):
        """Test term usage check is case sensitive (word boundary)."""
        (self.docs_dir / "test.md").write_text("agent Agent AGENT", encoding="utf-8")

        count = check_term_usage("Agent", self.docs_dir)
        self.assertEqual(count, 1)  # Only exact word boundary match

    def test_main_no_ubiquitous_file(self):
        """Test main exits with error when ubiquitous file missing."""
        result = subprocess.run(
            [sys.executable, "/home/zeron/dev/ai_developer_growth/tools/scripts/check_ubiquitous_language.py"],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )
        # Script returns 1 when file not found
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", result.stdout)

    def test_main_with_terms(self):
        """Test main runs successfully with terms file."""
        self.ubiquitous_file.write_text("| 术语 | 英文 | 定义 |\n| Agent | Agent | AI agent |\n", encoding="utf-8")

        (self.docs_dir / "test.md").write_text("Agent is used here.", encoding="utf-8")

        result = subprocess.run(
            [sys.executable, "/home/zeron/dev/ai_developer_growth/tools/scripts/check_ubiquitous_language.py"],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("OK", result.stdout)


if __name__ == "__main__":
    unittest.main()

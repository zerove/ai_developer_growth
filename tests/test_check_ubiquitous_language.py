import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from tools.scripts.check_ubiquitous_language import (
    check_term_usage,
    extract_terms,
    main,
)


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

    def test_extract_terms_empty_file(self):
        """Test extracting terms from empty file."""
        self.ubiquitous_file.write_text("# Empty\n", encoding="utf-8")
        terms = extract_terms(self.ubiquitous_file)
        self.assertEqual(terms, [])

    def test_extract_terms_filters_headers(self):
        """Test that table header keywords are filtered."""
        content = """| 术语 | 英文 | 定义 |
|------|------|------|
| Agent | Agent | AI agent |
"""
        self.ubiquitous_file.write_text(content, encoding="utf-8")
        terms = extract_terms(self.ubiquitous_file)
        # "英文", "定义" etc should be filtered
        self.assertNotIn("英文", terms)
        self.assertNotIn("定义", terms)
        self.assertIn("Agent", terms)

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

    def test_check_term_usage_multiple_files(self):
        """Test term usage across multiple files."""
        (self.docs_dir / "a.md").write_text("Agent is here.", encoding="utf-8")
        (self.docs_dir / "b.md").write_text("Agent appears twice. Agent again.", encoding="utf-8")

        count = check_term_usage("Agent", self.docs_dir)
        self.assertEqual(count, 3)

    def test_check_term_usage_read_error(self):
        """Test that unreadable files are skipped gracefully."""
        unreadable = self.docs_dir / "unreadable.md"
        unreadable.write_text("Agent content", encoding="utf-8")
        # Make it unreadable
        os.chmod(unreadable, 0o000)

        try:
            count = check_term_usage("Agent", self.docs_dir)
            # Should not crash, just skip the file
            self.assertIsInstance(count, int)
        finally:
            # Restore permissions for cleanup
            os.chmod(unreadable, 0o644)

    def test_main_no_ubiquitous_file(self):
        """Test main returns error when ubiquitous file missing."""
        # main() uses hardcoded paths relative to cwd, so test via subprocess
        proc = subprocess.run(
            [
                sys.executable,
                "/home/zeron/dev/ai_developer_growth/tools/scripts/check_ubiquitous_language.py",
            ],
            capture_output=True,
            text=True,
            cwd=self.test_dir,
        )
        self.assertEqual(proc.returncode, 1)
        self.assertIn("not found", proc.stdout)

    def test_main_with_terms(self):
        """Test main runs successfully with all terms used."""
        self.ubiquitous_file.write_text("| 术语 | 英文 | 定义 |\n| Agent | Agent | AI agent |\n", encoding="utf-8")
        (self.docs_dir / "test.md").write_text("Agent is used here.", encoding="utf-8")

        # Change cwd to test_dir so main() finds the files
        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            result = main()
            self.assertEqual(result, 0)
        finally:
            os.chdir(old_cwd)

    def test_main_with_missing_terms(self):
        """Test main runs with terms not used in docs."""
        self.ubiquitous_file.write_text("| 术语 | 英文 | 定义 |\n| Agent | Agent | AI agent |\n", encoding="utf-8")
        # Don't create any docs with the term

        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            result = main()
            self.assertEqual(result, 0)  # Warnings don't block
        finally:
            os.chdir(old_cwd)

    def test_main_multiple_terms(self):
        """Test main with multiple terms, some used and some not."""
        self.ubiquitous_file.write_text(
            "| 术语 | 英文 | 定义 |\n| Agent | Agent | AI agent |\n| Cosmos | Cosmos | Space system |\n",
            encoding="utf-8",
        )
        (self.docs_dir / "test.md").write_text("Agent is here.", encoding="utf-8")

        old_cwd = os.getcwd()
        try:
            os.chdir(self.test_dir)
            result = main()
            self.assertEqual(result, 0)
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    unittest.main()

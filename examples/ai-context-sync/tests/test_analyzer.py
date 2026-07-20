"""Tests for src/analyzer.py - targeting 100% coverage (excluding __main__)."""

import os
import subprocess
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzer import GitAnalyzer


class TestGetLastCommitDiff(unittest.TestCase):
    """Tests for get_last_commit_diff including CalledProcessError branch (lines 26-28)."""

    def setUp(self):
        self.analyzer = GitAnalyzer()

    @patch("subprocess.run")
    def test_returns_stdout_on_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="diff output")
        result = self.analyzer.get_last_commit_diff()
        self.assertEqual(result, "diff output")
        mock_run.assert_called_once_with(
            ["git", "diff", "HEAD~1", "HEAD"],
            capture_output=True, text=True, check=True,
        )

    @patch("subprocess.run")
    def test_returns_empty_on_called_process_error(self, mock_run):
        """Lines 26-28: CalledProcessError branch."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "diff"]
        )
        result = self.analyzer.get_last_commit_diff()
        self.assertEqual(result, "")


class TestGetLastCommitMessage(unittest.TestCase):
    """Tests for get_last_commit_message including CalledProcessError branch (lines 40-42)."""

    def setUp(self):
        self.analyzer = GitAnalyzer()

    @patch("subprocess.run")
    def test_returns_stripped_message_on_success(self, mock_run):
        mock_run.return_value = MagicMock(stdout="  fix: bug  \n")
        result = self.analyzer.get_last_commit_message()
        self.assertEqual(result, "fix: bug")

    @patch("subprocess.run")
    def test_returns_empty_on_called_process_error(self, mock_run):
        """Lines 40-42: CalledProcessError branch."""
        mock_run.side_effect = subprocess.CalledProcessError(
            returncode=128, cmd=["git", "log"]
        )
        result = self.analyzer.get_last_commit_message()
        self.assertEqual(result, "")


class TestFilterDiff(unittest.TestCase):
    """Tests for filter_diff including exception fallback (lines 68-70)."""

    def setUp(self):
        self.analyzer = GitAnalyzer(ignore_patterns=["package-lock.json"])

    def test_empty_diff_returns_empty(self):
        self.assertEqual(self.analyzer.filter_diff(""), "")

    def test_normal_diff_filters_ignored_files(self):
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "index 1234567..abcdefg 100644\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = self.analyzer.filter_diff(diff)
        self.assertIn("src/main.py", result)

    @patch("src.analyzer.PatchSet")
    def test_value_error_falls_back_to_basic_filter(self, mock_ps):
        """Lines 68-70: ValueError triggers _basic_filter fallback."""
        mock_ps.side_effect = ValueError("bad patch")

        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n"
            "+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n"
            "-old\n"
            "+new\n"
        )
        result = self.analyzer.filter_diff(diff)
        self.assertIn("src/main.py", result)
        self.assertIn("+new", result)

    @patch("src.analyzer.PatchSet")
    def test_index_error_falls_back_to_basic_filter(self, mock_ps):
        """Lines 68-70: IndexError triggers _basic_filter fallback."""
        mock_ps.side_effect = IndexError("bad index")

        diff = (
            "diff --git a/file.txt b/file.txt\n"
            "old content\n"
            "+new content\n"
        )
        result = self.analyzer.filter_diff(diff)
        self.assertIn("diff --git", result)


class TestBasicFilter(unittest.TestCase):
    """Tests for _basic_filter method (lines 76-88)."""

    def setUp(self):
        self.analyzer = GitAnalyzer(ignore_patterns=["package-lock.json", ".gitignore"])

    def test_filters_ignored_files(self):
        """Lines 83-86: file matching ignore pattern is skipped."""
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "old\n+new\n"
            "diff --git a/package-lock.json b/package-lock.json\n"
            "old\n+new\n"
        )
        result = self.analyzer._basic_filter(diff)
        self.assertIn("src/main.py", result)
        self.assertNotIn("package-lock.json", result)

    def test_keeps_non_ignored_files(self):
        """Line 87: non-ignored chunk is appended."""
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "-old\n"
            "+new\n"
        )
        result = self.analyzer._basic_filter(diff)
        self.assertIn("diff --git", result)
        self.assertIn("src/app.py", result)

    def test_skips_empty_chunks(self):
        """Line 79: empty chunk from split is skipped."""
        # First chunk after split is always empty string
        diff = "diff --git a/file.py b/file.py\nold\nnew"
        result = self.analyzer._basic_filter(diff)
        self.assertIn("file.py", result)

    def test_chunk_with_few_parts_no_filter(self):
        """Lines 82-83: chunk where parts < 2 skips the ignore check."""
        diff = "diff --git\nminimal content"
        result = self.analyzer._basic_filter(diff)
        self.assertIn("diff --git", result)

    def test_multiple_files_mixed(self):
        """Full scenario: multiple files, some ignored."""
        diff = (
            "diff --git a/src/app.py b/src/app.py\n"
            "-old\n+new\n"
            "diff --git a/.gitignore b/.gitignore\n"
            "old\n+new\n"
            "diff --git a/README.md b/README.md\n"
            "-old\n+updated\n"
        )
        result = self.analyzer._basic_filter(diff)
        self.assertIn("src/app.py", result)
        self.assertIn("README.md", result)
        self.assertNotIn(".gitignore", result)

    def test_strips_a_prefix_from_file_path(self):
        """Line 84: 'a/' prefix is removed for ignore matching."""
        diff = (
            "diff --git a/package-lock.json b/package-lock.json\n"
            "old\n+new\n"
        )
        result = self.analyzer._basic_filter(diff)
        self.assertEqual(result, "")


if __name__ == "__main__":
    unittest.main()

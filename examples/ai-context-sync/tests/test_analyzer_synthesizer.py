import os
import sys
import unittest
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analyzer import GitAnalyzer
from src.llm_client import LLMClient
from src.synthesizer import ContextSynthesizer


class TestGitAnalyzer(unittest.TestCase):
    def setUp(self):
        self.analyzer = GitAnalyzer(ignore_patterns=["package-lock.json", ".gitignore"])

    def test_filter_diff_removes_ignored_files(self):
        diff = (
            "diff --git a/src/main.py b/src/main.py\n"
            "--- a/src/main.py\n+++ b/src/main.py\n"
            "@@ -1,1 +1,1 @@\n-print('hi')\n+print('hello')\n"
            "diff --git a/package-lock.json b/package-lock.json\n"
            "--- a/package-lock.json\n+++ b/package-lock.json\n"
            "@@ -1,1 +1,1 @@\n-lock1\n+lock2\n"
        )
        filtered = self.analyzer.filter_diff(diff)
        self.assertIn("src/main.py", filtered)
        self.assertNotIn("package-lock.json", filtered)

    def test_filter_diff_keeps_relevant_files(self):
        diff = "diff --git a/src/utils.py b/src/utils.py\n-old\n+new"
        filtered = self.analyzer.filter_diff(diff)
        self.assertEqual(diff, filtered)

    def test_filter_diff_empty(self):
        self.assertEqual(self.analyzer.filter_diff(""), "")


class TestContextSynthesizer(unittest.TestCase):
    def setUp(self):
        self.mock_client = MagicMock(spec=LLMClient)
        mock_profile = MagicMock()
        mock_profile.name = "generic"
        self.synth = ContextSynthesizer(self.mock_client, mock_profile)

    def test_synthesize_context_update_calls_client(self):
        self.mock_client.generate.return_value = "Updated Context"
        result = self.synth.synthesize_context_update("diff", "msg", "old")
        self.assertEqual(result, "Updated Context")
        self.mock_client.generate.assert_called_once()

    def test_synthesize_adr_calls_client(self):
        self.mock_client.generate.return_value = "ADR Content " + "x" * 60
        result = self.synth.synthesize_adr("diff", "msg")
        self.assertIn("ADR Content", result)
        self.mock_client.generate.assert_called_once()


if __name__ == "__main__":
    unittest.main()

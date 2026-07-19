"""Tests for ai-context-manager.py"""
import os
import sys
import shutil
import tempfile
import unittest
import importlib.util
from unittest.mock import MagicMock

# Mock openai before importing the module (source imports openai at module level)
mock_openai = MagicMock()
sys.modules["openai"] = mock_openai

spec = importlib.util.spec_from_file_location(
    "ai_context_manager",
    os.path.join(os.path.dirname(__file__), "..", "tools", "scripts", "ai-context-manager.py")
)
ai_context_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_context_manager)

load_context = ai_context_manager.load_context
save_context = ai_context_manager.save_context


class TestLoadContext(unittest.TestCase):
    """Test context loading functionality."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    def test_load_context_returns_string(self):
        """Test that load_context returns a string."""
        context_file = os.path.join(self.tmp_dir, "CONTEXT.md")
        with open(context_file, "w", encoding="utf-8") as f:
            f.write("# Project Context\n\n## Current Progress\n- Test.")

        result = load_context()
        self.assertIsInstance(result, str)
        self.assertIn("Project Context", result)

    def test_load_context_returns_default_when_missing(self):
        """Test that load_context returns default when CONTEXT.md doesn't exist."""
        result = load_context()
        self.assertIn("Project Context", result)
        self.assertIn("Initial project setup", result)

    def test_load_context_preserves_content(self):
        """Test that load_context preserves full file content."""
        context_file = os.path.join(self.tmp_dir, "CONTEXT.md")
        content = "# Title\n\n## Section\n- Item 1\n- Item 2\n\n## Another\n- Detail"
        with open(context_file, "w", encoding="utf-8") as f:
            f.write(content)

        result = load_context()
        self.assertEqual(result, content)


class TestSaveContext(unittest.TestCase):
    """Test context saving functionality."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    def test_save_context_creates_file(self):
        """Test that save_context creates CONTEXT.md."""
        save_context("# Updated Context\n\n## Progress\n- Done.")
        self.assertTrue(os.path.exists("CONTEXT.md"))

        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Updated Context", content)

    def test_save_context_overwrites_existing(self):
        """Test that save_context overwrites existing file."""
        save_context("# Old Content")
        save_context("# New Content")

        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("New Content", content)
        self.assertNotIn("Old Content", content)

    def test_save_context_writes_utf8(self):
        """Test that save_context handles UTF-8 content correctly."""
        save_context("# 中文上下文\n\n## 进度\n- 完成")
        with open("CONTEXT.md", "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("中文上下文", content)


if __name__ == "__main__":
    unittest.main()

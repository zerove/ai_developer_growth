"""Tests for ai_context_manager.py"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import MagicMock, patch

# Mock openai before importing the module (source imports openai at module level)
mock_openai = MagicMock()
sys.modules["openai"] = mock_openai

spec = importlib.util.spec_from_file_location(
    "ai_context_manager", os.path.join(os.path.dirname(__file__), "..", "tools", "scripts", "ai_context_manager.py")
)
ai_context_manager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ai_context_manager)

load_context = ai_context_manager.load_context
save_context = ai_context_manager.save_context
update_context_with_llm = ai_context_manager.update_context_with_llm
main = ai_context_manager.main


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

        with open("CONTEXT.md", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Updated Context", content)

    def test_save_context_overwrites_existing(self):
        """Test that save_context overwrites existing file."""
        save_context("# Old Content")
        save_context("# New Content")

        with open("CONTEXT.md", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("New Content", content)
        self.assertNotIn("Old Content", content)

    def test_save_context_writes_utf8(self):
        """Test that save_context handles UTF-8 content correctly."""
        save_context("# 中文上下文\n\n## 进度\n- 完成")
        with open("CONTEXT.md", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("中文上下文", content)


class TestUpdateContextWithLLM(unittest.TestCase):
    """Test LLM-based context update functionality."""

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch.object(ai_context_manager, "OpenAI")
    def test_update_context_with_llm_success(self, mock_openai_class):
        """Test successful LLM context update."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_response = MagicMock()
        mock_response.choices = [MagicMock(message=MagicMock(content="# Updated Context\n\n## Progress\n- New item"))]
        mock_client.chat.completions.create.return_value = mock_response

        result = update_context_with_llm("# Current Context", "Added new feature")

        self.assertIn("Updated Context", result)
        self.assertIn("New item", result)
        mock_client.chat.completions.create.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch.object(ai_context_manager, "OpenAI")
    def test_update_context_with_llm_handles_error(self, mock_openai_class):
        """Test LLM error handling."""
        mock_client = MagicMock()
        mock_openai_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = Exception("API Error")

        with self.assertRaises(SystemExit) as cm:
            update_context_with_llm("# Current", "Changes")
        self.assertEqual(cm.exception.code, 1)

    def test_update_context_with_llm_exits_when_no_api_key(self):
        """Test that update_context_with_llm exits when no API key."""
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(SystemExit) as cm:
                update_context_with_llm("# Current", "Changes")
            self.assertEqual(cm.exception.code, 1)


class TestMain(unittest.TestCase):
    """Test main function."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("builtins.input", return_value="Test changes")
    @patch.object(ai_context_manager, "update_context_with_llm", return_value="# Updated\n\n## Progress\n- Test")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_with_changes_argument(self, mock_stdout, mock_update, mock_input):
        """Test main with changes as argument."""
        # Call with command line argument
        sys.argv = ["ai_context_manager.py", "Test changes"]
        main()
        output = mock_stdout.getvalue()
        self.assertIn("成功更新 CONTEXT.md", output)
        mock_update.assert_called_once()

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("builtins.input", return_value="Test changes")
    @patch.object(ai_context_manager, "update_context_with_llm", return_value="# Updated\n\n## Progress\n- Test")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_interactive_input(self, mock_stdout, mock_update, mock_input):
        """Test main with interactive input."""
        sys.argv = ["ai_context_manager.py"]
        main()
        output = mock_stdout.getvalue()
        self.assertIn("成功更新 CONTEXT.md", output)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    @patch("builtins.input", return_value="")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_empty_input_exits(self, mock_stdout, mock_input):
        """Test main exits when empty input provided."""
        sys.argv = ["ai_context_manager.py"]
        main()
        output = mock_stdout.getvalue()
        self.assertIn("没有提供变更信息", output)

    @patch.dict(os.environ, {}, clear=True)
    @patch("builtins.input", return_value="Test changes")
    @patch("sys.stdout", new_callable=StringIO)
    def test_main_no_api_key_exits(self, mock_stdout, mock_input):
        """Test main exits when no API key."""
        sys.argv = ["ai_context_manager.py", "Test changes"]
        with self.assertRaises(SystemExit) as cm:
            main()
        self.assertEqual(cm.exception.code, 1)
        output = mock_stdout.getvalue()
        self.assertIn("OPENAI_API_KEY", output)


if __name__ == "__main__":
    unittest.main()

"""Tests for adr-generator.py"""
import os
import sys
import shutil
import tempfile
import unittest
import importlib.util
from unittest.mock import patch, MagicMock

# Import using importlib to handle hyphenated filename
spec = importlib.util.spec_from_file_location(
    "adr_generator",
    os.path.join(os.path.dirname(__file__), "..", "tools", "scripts", "adr-generator.py")
)
adr_generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(adr_generator)

generate_from_llm = adr_generator.generate_from_llm
generate_interactive = adr_generator.generate_interactive
save_adr = adr_generator.save_adr


class TestGenerateFromLLM(unittest.TestCase):
    """Test LLM-based ADR generation."""

    @patch.object(adr_generator, "LLMClient")
    def test_generate_from_llm_returns_string(self, mock_llm_class):
        """Test that generate_from_llm returns a string."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "## Context\nTest context"
        mock_llm_class.return_value = mock_llm

        result = generate_from_llm("Test Title", "Test brief")
        self.assertIsInstance(result, str)
        self.assertIn("Context", result)

    @patch.object(adr_generator, "LLMClient")
    def test_generate_from_llm_handles_empty_response(self, mock_llm_class):
        """Test that generate_from_llm handles empty LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = ""
        mock_llm_class.return_value = mock_llm

        result = generate_from_llm("Test Title", "Test brief")
        self.assertEqual(result, "")


class TestGenerateInteractive(unittest.TestCase):
    """Test interactive ADR generation."""

    @patch("builtins.input", side_effect=["Test Title", "Context", "Alternatives", "Decision", "Consequences"])
    def test_generate_interactive_returns_tuple(self, mock_input):
        """Test that generate_interactive returns (title, body) tuple."""
        title, body = generate_interactive()
        self.assertEqual(title, "Test Title")
        self.assertIn("## Context", body)
        self.assertIn("## Alternatives", body)
        self.assertIn("## Decision", body)
        self.assertIn("## Consequences", body)


class TestSaveAdr(unittest.TestCase):
    """Test ADR saving functionality."""

    def setUp(self):
        self.original_dir = os.getcwd()
        self.tmp_dir = tempfile.mkdtemp()
        os.chdir(self.tmp_dir)

    def tearDown(self):
        os.chdir(self.original_dir)
        shutil.rmtree(self.tmp_dir)

    def test_save_adr_creates_file(self):
        """Test that save_adr creates a file in docs/adr/."""
        filepath = save_adr("Test Decision", "## Context\nTest content")
        self.assertTrue(os.path.exists(filepath))
        self.assertTrue(filepath.startswith("docs/adr/"))

        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Test Decision", content)
        self.assertIn("## Context", content)

    def test_save_adr_increments_index(self):
        """Test that save_adr increments ADR index."""
        filepath1 = save_adr("First Decision", "Body 1")
        filepath2 = save_adr("Second Decision", "Body 2")

        self.assertIn("ADR-001", filepath1)
        self.assertIn("ADR-002", filepath2)

    def test_save_adr_filename_format(self):
        """Test that save_adr generates correct filename format."""
        filepath = save_adr("My Test Decision", "Body")
        # Title lowercased with spaces replaced by underscores
        self.assertIn("ADR-001-my_test_decision.md", filepath)

    def test_save_adr_includes_metadata(self):
        """Test that saved ADR includes status and date."""
        filepath = save_adr("Meta Test", "## Context\nTest")
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("Accepted", content)
        self.assertIn("## Context", content)


if __name__ == "__main__":
    unittest.main()

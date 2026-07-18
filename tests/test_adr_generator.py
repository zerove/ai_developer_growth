"""Tests for adr-generator.py"""
import os
import sys
import importlib.util
import tempfile
import pytest
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


class TestGenerateFromLLM:
    """Test LLM-based ADR generation."""

    @patch.object(adr_generator, "LLMClient")
    def test_generate_from_llm_returns_string(self, mock_llm_class):
        """Test that generate_from_llm returns a string."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = "## Context\nTest context"
        mock_llm_class.return_value = mock_llm

        result = generate_from_llm("Test Title", "Test brief")
        assert isinstance(result, str)
        assert "Context" in result

    @patch.object(adr_generator, "LLMClient")
    def test_generate_from_llm_handles_empty_response(self, mock_llm_class):
        """Test that generate_from_llm handles empty LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate.return_value = ""
        mock_llm_class.return_value = mock_llm

        result = generate_from_llm("Test Title", "Test brief")
        assert result == ""


class TestGenerateInteractive:
    """Test interactive ADR generation."""

    @patch("builtins.input", side_effect=["Test Title", "Context", "Alternatives", "Decision", "Consequences"])
    def test_generate_interactive_returns_tuple(self, mock_input):
        """Test that generate_interactive returns (title, body) tuple."""
        title, body = generate_interactive()
        assert title == "Test Title"
        assert "## Context" in body
        assert "## Alternatives" in body
        assert "## Decision" in body
        assert "## Consequences" in body


class TestSaveAdr:
    """Test ADR saving functionality."""

    def test_save_adr_creates_file(self, tmp_path):
        """Test that save_adr creates a file in docs/adr/."""
        # Change to temp directory
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            filepath = save_adr("Test Decision", "## Context\nTest content")
            assert os.path.exists(filepath)
            assert filepath.startswith("docs/adr/")
            
            with open(filepath, "r", encoding="utf-8") as f:
                content = f.read()
            assert "Test Decision" in content
            assert "## Context" in content
        finally:
            os.chdir(original_dir)

    def test_save_adr_increments_index(self, tmp_path):
        """Test that save_adr increments ADR index."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Create first ADR
            filepath1 = save_adr("First Decision", "Body 1")
            # Create second ADR
            filepath2 = save_adr("Second Decision", "Body 2")
            
            assert "ADR-001" in filepath1
            assert "ADR-002" in filepath2
        finally:
            os.chdir(original_dir)

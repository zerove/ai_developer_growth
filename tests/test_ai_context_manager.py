"""Tests for ai-context-manager.py"""
import os
import sys
import importlib.util
import pytest
from unittest.mock import patch, MagicMock

# Mock openai before importing the module
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


class TestLoadContext:
    """Test context loading functionality."""

    def test_load_context_returns_string(self, tmp_path):
        """Test that load_context returns a string."""
        context_file = tmp_path / "CONTEXT.md"
        context_file.write_text("# Project Context\n\n## Current Progress\n- Test.")
        
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = load_context()
            assert isinstance(result, str)
            assert "Project Context" in result
        finally:
            os.chdir(original_dir)

    def test_load_context_returns_default_when_missing(self, tmp_path):
        """Test that load_context returns default when CONTEXT.md doesn't exist."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        try:
            result = load_context()
            assert "Project Context" in result
            assert "Initial project setup" in result
        finally:
            os.chdir(original_dir)


class TestSaveContext:
    """Test context saving functionality."""

    def test_save_context_creates_file(self, tmp_path):
        """Test that save_context creates CONTEXT.md."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            save_context("# Updated Context\n\n## Progress\n- Done.")
            assert os.path.exists("CONTEXT.md")
            
            with open("CONTEXT.md", "r", encoding="utf-8") as f:
                content = f.read()
            assert "Updated Context" in content
        finally:
            os.chdir(original_dir)

    def test_save_context_overwrites_existing(self, tmp_path):
        """Test that save_context overwrites existing file."""
        original_dir = os.getcwd()
        os.chdir(tmp_path)
        
        try:
            # Create initial file
            save_context("# Old Content")
            # Overwrite
            save_context("# New Content")
            
            with open("CONTEXT.md", "r", encoding="utf-8") as f:
                content = f.read()
            assert "New Content" in content
            assert "Old Content" not in content
        finally:
            os.chdir(original_dir)

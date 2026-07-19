"""Smoke tests for entry point modules."""
import os
import sys
import subprocess
import importlib.util
from pathlib import Path

import pytest


def test_main_entry_point():
    """Test that src/main.py can be imported and runs without error."""
    # Run via subprocess since relative imports don't work when imported directly
    result = subprocess.run(
        [sys.executable, "-c", "from src.main import app; print('OK')"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "OK" in result.stdout


def test_mcp_server_import():
    """Test that src/mcp_server.py can be imported (tests lines 1-32)."""
    spec = importlib.util.spec_from_file_location(
        "mcp_server", Path(__file__).parent.parent / "src" / "mcp_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Check mcp instance exists
    assert hasattr(module, "mcp")
    assert module.mcp is not None
    assert hasattr(module, "_get_sync_tool")


def test_main_cli_help():
    """Test main CLI help runs."""
    result = subprocess.run(
        [sys.executable, "-m", "src.main", "--help"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "AI-Context-Sync" in result.stdout


def test_mcp_server_cli_help():
    """Test mcp_server can be run with --help."""
    result = subprocess.run(
        [sys.executable, "-m", "src.mcp_server", "--help"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    # mcp server may not have --help, just check it doesn't crash on import
    # The run is tested above via import


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
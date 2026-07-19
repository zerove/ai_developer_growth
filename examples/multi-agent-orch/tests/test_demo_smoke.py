"""Smoke tests for entry point modules."""
import sys
import subprocess
import importlib.util
from pathlib import Path

import pytest


def test_demo_entry_point():
    """Test that src/demo.py can be imported and runs without error."""
    spec = importlib.util.spec_from_file_location(
        "demo", Path(__file__).parent.parent / "src" / "demo.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Check functions exist
    assert hasattr(module, "run_waterfall")
    assert hasattr(module, "run_fan_out")
    assert hasattr(module, "main")


def test_demo_cli_help():
    """Test demo CLI help runs."""
    result = subprocess.run(
        [sys.executable, "-m", "src.demo", "--help"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "Multi-agent workflow demo" in result.stdout
    assert "--mode" in result.stdout
    assert "--request" in result.stdout


def test_demo_cli_waterfall_mode():
    """Test demo runs in waterfall mode (quick test)."""
    result = subprocess.run(
        [sys.executable, "-m", "src.demo", "--mode", "waterfall", "--request", "test"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should complete without error
    assert result.returncode == 0
    assert "Waterfall Mode" in result.stdout
    assert "Iterations:" in result.stdout


def test_demo_cli_fan_out_mode():
    """Test demo runs in fan-out mode (quick test)."""
    result = subprocess.run(
        [sys.executable, "-m", "src.demo", "--mode", "fan-out", "--request", "test"],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should complete without error
    assert result.returncode == 0
    assert "Fan-Out Mode" in result.stdout
    assert "Agents:" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
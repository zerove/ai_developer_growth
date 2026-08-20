"""Smoke tests for entry point modules."""

import subprocess
import sys
from pathlib import Path


def test_demo_entry_point():
    """Test that multi_agent_orch.demo can be imported and runs without error."""
    import multi_agent_orch.demo as demo
    # Check functions exist
    assert hasattr(demo, "run_waterfall")
    assert hasattr(demo, "run_fan_out")
    assert hasattr(demo, "main")


def test_demo_cli_help():
    """Test demo CLI help runs."""
    result = subprocess.run(
        [sys.executable, "-m", "multi_agent_orch.demo", "--help"],
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
        [
            sys.executable,
            "-m",
            "multi_agent_orch.demo",
            "--mode",
            "waterfall",
            "--request",
            "test",
        ],
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
        [
            sys.executable,
            "-m",
            "multi_agent_orch.demo",
            "--mode",
            "fan-out",
            "--request",
            "test",
        ],
        cwd=Path(__file__).parent.parent,
        capture_output=True,
        text=True,
        timeout=30,
    )
    # Should complete without error
    assert result.returncode == 0
    assert "Fan-Out Mode" in result.stdout
    assert "Agents:" in result.stdout

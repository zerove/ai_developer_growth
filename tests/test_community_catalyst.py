#!/usr/bin/env python3
"""Tests for community-catalyst.py"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / ".jcode" / "scripts"


class TestCommunityCatalyst:
    """Test community-catalyst script functions."""

    def run_script(self, *args):
        """Run the script with given arguments."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "community-catalyst.py"), *args],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        return result

    def test_no_args(self):
        """Test running without arguments."""
        result = self.run_script()
        assert result.returncode == 1
        assert "用法" in result.stdout

    def test_unknown_action(self):
        """Test running with unknown action."""
        result = self.run_script("unknown")
        assert result.returncode == 1
        assert "未知" in result.stdout

    def test_triage(self):
        """Test triage action."""
        result = self.run_script("triage")
        assert result.returncode == 0
        assert "分流" in result.stdout
        assert "可用标签" in result.stdout

    def test_stats(self):
        """Test stats action."""
        result = self.run_script("stats")
        # stats may exit 1 if case-studies not found
        assert "案例" in result.stdout or "未找到" in result.stdout

    def test_validate(self):
        """Test validate action."""
        result = self.run_script("validate")
        # validate runs the case study validator
        assert "验证" in result.stdout or "案例" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

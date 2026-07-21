#!/usr/bin/env python3
"""Tests for workflow-optimizer.py"""

import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).parent.parent / ".jcode" / "scripts"


class TestWorkflowOptimizer:
    """Test workflow-optimizer script functions."""

    def run_script(self, *args):
        """Run the script with given arguments."""
        result = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "workflow-optimizer.py"), *args],
            capture_output=True,
            text=True,
            cwd=Path.cwd()
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

    def test_report(self):
        """Test report action."""
        result = self.run_script("report")
        assert result.returncode == 0
        assert "AI Developer Growth" in result.stdout
        assert "效率报告" in result.stdout

    def test_analyze(self):
        """Test analyze action (may fail if no case-studies dir)."""
        result = self.run_script("analyze")
        # analyze may exit 1 if case-studies not found
        assert "案例" in result.stdout or "未找到" in result.stdout

    def test_recommend(self):
        """Test recommend action (may fail if no tool matrix)."""
        result = self.run_script("recommend")
        # recommend may exit 1 if tool matrix not found
        assert "工具" in result.stdout or "未找到" in result.stdout


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

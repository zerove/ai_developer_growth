"""Tests for jcode_cli."""

import subprocess
import sys

import pytest


class TestJCodeCLI:
    """Tests for JCode CLI."""

    def test_help(self):
        """Test help command works."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.scripts.jcode_cli", "--help"],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "JCode AI-Native SDLC Command Line Interface" in result.stdout
        assert "ai-native-workflow" in result.stdout
        assert "ai-quality-gate" in result.stdout

    def test_case_quality_all(self):
        """Test case-quality command without arguments."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.scripts.jcode_cli", "case-quality"],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "Case Study Quality Analysis Report" in result.stdout
        # 案例数量随知识库增长动态变化，只断言格式而非具体数字
        import re as _re

        assert _re.search(r"\d+ cases", result.stdout), result.stdout

    def test_case_quality_specific(self):
        """Test case-quality command with specific case."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.scripts.jcode_cli",
                "case-quality",
                "--case",
                "case-studies/adg-scan-httpx.md",
            ],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "adg-scan-httpx" in result.stdout
        assert "Overall:" in result.stdout

    def test_dor_check(self):
        """Test dor-check command."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.scripts.jcode_cli",
                "dor-check",
                "--intent",
                "Add user authentication with JWT tokens and refresh logic",
            ],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "Passed: True" in result.stdout
        assert "Score: 7/7" in result.stdout

    def test_ai_quality_gate(self):
        """Test ai-quality-gate command."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.scripts.jcode_cli",
                "ai-quality-gate",
                "--path",
                "tools/scripts/jcode_cli.py",
            ],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        # May have issues, but should not crash
        assert "AI Quality Gate Results" in result.stdout

    def test_ai_pr_review(self):
        """Test ai-pr-review command."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.scripts.jcode_cli", "ai-pr-review"],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        # Should not crash
        assert (
            "AI PR Review" in result.stdout
            or "No changes to review" in result.stdout
            or "No issues found in PR review" in result.stdout
        )

    def test_metrics_telemetry(self):
        """Test metrics-telemetry command."""
        result = subprocess.run(
            [sys.executable, "-m", "tools.scripts.jcode_cli", "metrics-telemetry"],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "Collected metrics" in result.stdout

    def test_audit_attestation(self):
        """Test audit-attestation command."""
        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "tools.scripts.jcode_cli",
                "audit-attestation",
                "--intent",
                "Test audit",
            ],
            capture_output=True,
            text=True,
            cwd="/home/zeron/dev/ai_developer_growth",
        )
        assert result.returncode == 0
        assert "audit" in result.stdout.lower() or "trace" in result.stdout.lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for basic_checks hook module."""

import subprocess
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks.basic_checks import (
    BASIC_CHECKS,
    CODE_EXTENSIONS,
    INCREMENTAL_EXTENSIONS,
    _run_subprocess,
    run_format_check,
    run_format_files,
    run_lint,
    run_lint_files,
    run_security,
    run_tests,
    run_typecheck,
)


class TestConstants:
    """Tests for constants."""

    def test_code_extensions_is_frozenset(self):
        """Test CODE_EXTENSIONS is a frozenset."""
        assert isinstance(CODE_EXTENSIONS, frozenset)
        assert ".py" in CODE_EXTENSIONS
        assert ".js" in CODE_EXTENSIONS
        assert ".rs" in CODE_EXTENSIONS

    def test_incremental_extensions_is_frozenset(self):
        """Test INCREMENTAL_EXTENSIONS is a frozenset."""
        assert isinstance(INCREMENTAL_EXTENSIONS, frozenset)
        assert ".py" in INCREMENTAL_EXTENSIONS
        assert ".ts" in INCREMENTAL_EXTENSIONS

    def test_incremental_subset_of_code(self):
        """Test INCREMENTAL_EXTENSIONS is subset of CODE_EXTENSIONS."""
        assert INCREMENTAL_EXTENSIONS.issubset(CODE_EXTENSIONS)

    def test_python_in_both(self):
        """Test Python is in both extension sets."""
        assert ".py" in CODE_EXTENSIONS
        assert ".py" in INCREMENTAL_EXTENSIONS

    def test_basic_checks_registry(self):
        """Test BASIC_CHECKS registry contains expected checks."""
        assert "lint" in BASIC_CHECKS
        assert "format" in BASIC_CHECKS
        assert "typecheck" in BASIC_CHECKS
        assert "test" in BASIC_CHECKS
        assert "security" in BASIC_CHECKS
        assert callable(BASIC_CHECKS["lint"])
        assert callable(BASIC_CHECKS["format"])
        assert callable(BASIC_CHECKS["typecheck"])
        assert callable(BASIC_CHECKS["test"])
        assert callable(BASIC_CHECKS["security"])


class TestRunSubprocess:
    """Tests for _run_subprocess function."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_success(self, mock_run):
        """Test successful subprocess run."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="success output",
            stderr="",
        )
        passed, output = _run_subprocess(["echo", "test"], timeout=10, description="Test")
        assert passed is True
        assert "success output" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_failure(self, mock_run):
        """Test failed subprocess run."""
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="error output",
        )
        passed, output = _run_subprocess(["false"], timeout=10, description="Test")
        assert passed is False
        assert "error output" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_timeout(self, mock_run):
        """Test subprocess timeout."""
        mock_run.side_effect = subprocess.TimeoutExpired("cmd", 10)
        passed, output = _run_subprocess(["sleep", "100"], timeout=1, description="Test")
        assert passed is False
        assert "timed out" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_command_not_found(self, mock_run):
        """Test command not found."""
        mock_run.side_effect = FileNotFoundError()
        passed, output = _run_subprocess(["nonexistent"], timeout=10, description="Test")
        assert passed is False
        assert "command not found" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_combined_stdout_stderr(self, mock_run):
        """Test combined stdout and stderr."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="stdout content",
            stderr="stderr content",
        )
        passed, output = _run_subprocess(["cmd"], timeout=10, description="Test")
        assert passed is True
        assert "stdout content" in output
        assert "stderr content" in output


class TestRunLint:
    """Tests for run_lint function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_lint(self, mock_run):
        """Test run_lint calls correct command."""
        mock_run.return_value = (True, "lint output")
        passed, output = run_lint()
        assert passed is True
        assert output == "lint output"
        mock_run.assert_called_once_with(
            ["ruff", "check", "."],
            timeout=120,
            description="Lint",
        )


class TestRunFormatCheck:
    """Tests for run_format_check function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_format_check(self, mock_run):
        """Test run_format_check calls correct command."""
        mock_run.return_value = (True, "format output")
        passed, output = run_format_check()
        assert passed is True
        assert output == "format output"
        mock_run.assert_called_once_with(
            ["ruff", "format", "--check", "."],
            timeout=120,
            description="Format",
        )


class TestRunTypecheck:
    """Tests for run_typecheck function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    @patch("tools.scripts.hooks.basic_checks.sys.executable", "python")
    def test_run_typecheck(self, mock_run):
        """Test run_typecheck calls correct command."""
        mock_run.return_value = (True, "typecheck output")
        passed, output = run_typecheck()
        assert passed is True
        assert output == "typecheck output"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "python"
        assert "-m" in args
        assert "mypy" in args
        assert "tools/scripts/" in args
        assert "--ignore-missing-imports" in args


class TestRunTests:
    """Tests for run_tests function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    @patch("tools.scripts.hooks.basic_checks.sys.executable", "python")
    def test_run_tests(self, mock_run):
        """Test run_tests calls correct command."""
        mock_run.return_value = (True, "test output")
        passed, output = run_tests()
        assert passed is True
        assert output == "test output"
        mock_run.assert_called_once()
        args = mock_run.call_args[0][0]
        assert args[0] == "python"
        assert "-m" in args
        assert "pytest" in args
        assert "tests/" in args
        assert "--cov=tools/scripts" in args
        assert "--tb=short" in args


class TestRunSecurity:
    """Tests for run_security function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_security_pass(self, mock_run):
        """Test run_security when both checks pass."""
        mock_run.side_effect = [
            (True, "bandit output"),  # bandit
            (True, "audit output"),  # pip-audit
        ]
        passed, output = run_security()
        assert passed is True
        assert "bandit output" in output
        assert "audit output" in output
        assert mock_run.call_count == 2

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_security_bandit_fail(self, mock_run):
        """Test run_security when bandit fails."""
        mock_run.side_effect = [
            (False, "bandit failed"),
            (True, "audit output"),
        ]
        passed, output = run_security()
        assert passed is False
        assert "bandit failed" in output

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_security_audit_fail(self, mock_run):
        """Test run_security when pip-audit fails."""
        mock_run.side_effect = [
            (True, "bandit output"),
            (False, "audit failed"),
        ]
        passed, output = run_security()
        assert passed is False
        assert "audit failed" in output


class TestRunLintFiles:
    """Tests for run_lint_files function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_lint_files_with_paths(self, mock_run):
        """Test run_lint_files with file paths."""
        mock_run.return_value = (True, "lint output")
        paths = ["src/file1.py", "src/file2.py"]
        passed, output = run_lint_files(paths)
        assert passed is True
        mock_run.assert_called_once_with(
            ["ruff", "check", "src/file1.py", "src/file2.py"],
            timeout=60,
            description="Lint",
        )

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_lint_files_empty(self, mock_run):
        """Test run_lint_files with empty list."""
        passed, output = run_lint_files([])
        assert passed is True
        assert "No Python files to lint" in output
        mock_run.assert_not_called()


class TestRunFormatFiles:
    """Tests for run_format_files function."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_format_files_with_paths(self, mock_run):
        """Test run_format_files with file paths."""
        mock_run.return_value = (True, "format output")
        paths = ["src/file1.py", "src/file2.py"]
        passed, output = run_format_files(paths)
        assert passed is True
        mock_run.assert_called_once_with(
            ["ruff", "format", "--check", "src/file1.py", "src/file2.py"],
            timeout=60,
            description="Format",
        )

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_format_files_empty(self, mock_run):
        """Test run_format_files with empty list."""
        passed, output = run_format_files([])
        assert passed is True
        assert "No Python files to format-check" in output
        mock_run.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

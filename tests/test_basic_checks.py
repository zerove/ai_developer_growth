"""Tests for hooks/basic_checks.py (65% → target 85%)."""

from __future__ import annotations

import subprocess
from unittest.mock import MagicMock, patch

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
    """Tests for module constants."""

    def test_code_extensions_is_frozenset(self) -> None:
        assert isinstance(CODE_EXTENSIONS, frozenset)

    def test_incremental_extensions_is_frozenset(self) -> None:
        assert isinstance(INCREMENTAL_EXTENSIONS, frozenset)

    def test_incremental_subset_of_code(self) -> None:
        """INCREMENTAL is a subset of CODE extensions."""
        assert INCREMENTAL_EXTENSIONS.issubset(CODE_EXTENSIONS)

    def test_python_in_both(self) -> None:
        assert ".py" in CODE_EXTENSIONS
        assert ".py" in INCREMENTAL_EXTENSIONS

    def test_basic_checks_registry(self) -> None:
        """BASIC_CHECKS contains all expected check names."""
        assert "lint" in BASIC_CHECKS
        assert "format" in BASIC_CHECKS
        assert "typecheck" in BASIC_CHECKS
        assert "test" in BASIC_CHECKS
        assert "security" in BASIC_CHECKS
        assert len(BASIC_CHECKS) == 5


class TestRunSubprocess:
    """Tests for _run_subprocess helper."""

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_success(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="ok", stderr="")
        passed, output = _run_subprocess(["echo", "hello"])
        assert passed is True
        assert "ok" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_failure(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="error")
        passed, output = _run_subprocess(["cmd"])
        assert passed is False
        assert "error" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="cmd", timeout=1)
        passed, output = _run_subprocess(["cmd"], timeout=1, description="Test")
        assert passed is False
        assert "timed out" in output
        assert "Test" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_command_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        passed, output = _run_subprocess(["nonexistent-cmd"], description="MyCheck")
        assert passed is False
        assert "command not found" in output
        assert "MyCheck" in output

    @patch("tools.scripts.hooks.basic_checks.subprocess.run")
    def test_combined_stdout_stderr(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="out", stderr="err")
        _, output = _run_subprocess(["cmd"])
        assert "out" in output
        assert "err" in output


class TestRunLint:
    """Tests for run_lint and related."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_lint_calls_correct_cmd(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_lint()
        assert passed is True
        args = mock_sub.call_args
        assert args[0][0] == ["ruff", "check", "."]

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_format_check(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_format_check()
        assert passed is True
        args = mock_sub.call_args
        assert "format" in args[0][0]

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_typecheck(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_typecheck()
        assert passed is True

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_tests(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_tests()
        assert passed is True

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_security(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "clean")
        passed, output = run_security()
        assert passed is True
        assert "bandit" in output
        assert "pip-audit" in output
        assert mock_sub.call_count == 2

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_run_security_bandit_fails(self, mock_sub: MagicMock) -> None:
        mock_sub.side_effect = [(False, "issue found"), (True, "clean")]
        passed, output = run_security()
        assert passed is False


class TestRunLintFiles:
    """Tests for run_lint_files and run_format_files."""

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_lint_files_with_paths(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_lint_files(["a.py", "b.py"])
        assert passed is True
        cmd = mock_sub.call_args[0][0]
        assert "a.py" in cmd
        assert "b.py" in cmd

    def test_lint_files_empty(self) -> None:
        passed, msg = run_lint_files([])
        assert passed is True
        assert "No Python files" in msg

    @patch("tools.scripts.hooks.basic_checks._run_subprocess")
    def test_format_files_with_paths(self, mock_sub: MagicMock) -> None:
        mock_sub.return_value = (True, "")
        passed, _ = run_format_files(["a.py"])
        assert passed is True

    def test_format_files_empty(self) -> None:
        passed, msg = run_format_files([])
        assert passed is True
        assert "No Python files" in msg

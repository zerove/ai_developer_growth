"""Tests for incremental_checks hook module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks.incremental_checks import (
    _check_code_files,
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_pre_commit_checks,
)


class TestGetChangedFiles:
    """Tests for get_changed_files function."""

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_success(self, mock_run):
        """Test successful retrieval of changed files."""
        mock_run.return_value = MagicMock(
            stdout="src/file1.py\nsrc/file2.py\n",
            returncode=0,
        )
        files = get_changed_files("HEAD")
        assert len(files) == 2
        assert files[0].name == "file1.py"
        assert files[1].name == "file2.py"

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_fallback(self, mock_run):
        """Test fallback to other refs."""
        mock_run.side_effect = [
            MagicMock(returncode=1, stderr="error"),  # HEAD fails
            MagicMock(returncode=1, stderr="error"),  # origin/main fails
            MagicMock(stdout="src/file.py\n", returncode=0),  # origin/master works
        ]
        files = get_changed_files("HEAD")
        assert len(files) == 1
        assert files[0].name == "file.py"

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_no_changes(self, mock_run):
        """Test when no changes."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        files = get_changed_files("HEAD")
        assert files == []

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_timeout(self, mock_run):
        """Test timeout handling."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("git", 30)
        files = get_changed_files("HEAD")
        assert files == []

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_changed_files_file_not_found(self, mock_run):
        """Test git not found."""
        mock_run.side_effect = FileNotFoundError()
        files = get_changed_files("HEAD")
        assert files == []


class TestGetStagedFiles:
    """Tests for get_staged_files function."""

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_staged_files_success(self, mock_run):
        """Test successful retrieval of staged files."""
        mock_run.return_value = MagicMock(
            stdout="src/file1.py\nsrc/file2.py\n",
            returncode=0,
        )
        files = get_staged_files()
        assert len(files) == 2

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_staged_files_empty(self, mock_run):
        """Test when no staged files."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        files = get_staged_files()
        assert files == []

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_staged_files_timeout(self, mock_run):
        """Test timeout handling."""
        from subprocess import TimeoutExpired

        mock_run.side_effect = TimeoutExpired("git", 30)
        files = get_staged_files()
        assert files == []

    @patch("tools.scripts.hooks.incremental_checks.subprocess.run")
    def test_get_staged_files_file_not_found(self, mock_run):
        """Test git not found."""
        mock_run.side_effect = FileNotFoundError()
        files = get_staged_files()
        assert files == []


class TestRunDiffChecks:
    """Tests for run_diff_checks function."""

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_run_diff_checks_no_changes(self, mock_get):
        """Test when no changed files."""
        mock_get.return_value = []
        passed, output = run_diff_checks("HEAD")
        assert passed is True
        assert "No changed files" in output

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    def test_run_diff_checks_no_code_files(self, mock_get):
        """Test when no code files in changes."""
        mock_get.return_value = [Path("README.md"), Path("docs/guide.md")]
        passed, output = run_diff_checks("HEAD")
        assert passed is True
        assert "No code files" in output

    @patch("tools.scripts.hooks.incremental_checks.get_changed_files")
    @patch("tools.scripts.hooks.incremental_checks._check_code_files")
    def test_run_diff_checks_with_files(self, mock_check, mock_get, tmp_path: Path):
        """Test with code files."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_get.return_value = [test_file]
        mock_check.return_value = (True, "All checks passed")

        passed, output = run_diff_checks("HEAD")
        assert passed is True
        mock_check.assert_called_once()


class TestRunPreCommitChecks:
    """Tests for run_pre_commit_checks function."""

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    def test_run_pre_commit_no_staged(self, mock_get):
        """Test when no staged files."""
        mock_get.return_value = []
        passed, output = run_pre_commit_checks()
        assert passed is True
        assert "No staged files" in output

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    def test_run_pre_commit_no_code_files(self, mock_get):
        """Test when no code files staged."""
        mock_get.return_value = [Path("README.md"), Path("docs/guide.md")]
        passed, output = run_pre_commit_checks()
        assert passed is True
        assert "No code files" in output

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    @patch("tools.scripts.hooks.incremental_checks._check_code_files")
    @patch("tools.scripts.hooks.scope_guard.ScopeGuardHook")
    @patch("tools.scripts.audit_attestation.AuditAttestationLedger")
    def test_run_pre_commit_with_files(self, mock_ledger, mock_scope, mock_check, mock_get, tmp_path: Path):
        """Test with staged code files."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_get.return_value = [test_file]
        mock_check.return_value = (True, "All checks passed")
        mock_scope_instance = MagicMock()
        mock_scope_instance.check_git_diff.return_value = (True, "Scope check passed")
        mock_scope.return_value = mock_scope_instance

        mock_ledger_instance = MagicMock()
        mock_ledger.return_value = mock_ledger_instance

        passed, output = run_pre_commit_checks()
        assert passed is True
        mock_ledger_instance.record_trace.assert_called_once()

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    @patch("tools.scripts.hooks.incremental_checks._check_code_files")
    @patch("tools.scripts.hooks.scope_guard.ScopeGuardHook")
    @patch("tools.scripts.audit_attestation.AuditAttestationLedger")
    def test_run_pre_commit_scope_fail(self, mock_ledger, mock_scope, mock_check, mock_get, tmp_path: Path):
        """Test when scope guard fails."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_get.return_value = [test_file]
        mock_check.return_value = (True, "All checks passed")
        mock_scope_instance = MagicMock()
        mock_scope_instance.check_git_diff.return_value = (
            False,
            "Scope Guard Warning: Large diff",
        )
        mock_scope.return_value = mock_scope_instance

        mock_ledger_instance = MagicMock()
        mock_ledger.return_value = mock_ledger_instance

        passed, output = run_pre_commit_checks()
        assert passed is False
        assert "Scope Guard Warning" in output

    @patch("tools.scripts.hooks.incremental_checks.get_staged_files")
    @patch("tools.scripts.hooks.incremental_checks._check_code_files")
    @patch("tools.scripts.hooks.scope_guard.ScopeGuardHook")
    def test_run_pre_commit_exception_handling(self, mock_scope, mock_check, mock_get, tmp_path: Path):
        """Test exception handling in scope guard."""
        test_file = tmp_path / "test.py"
        test_file.write_text("print('hello')")

        mock_get.return_value = [test_file]
        mock_check.return_value = (True, "All checks passed")
        mock_scope_instance = MagicMock()
        mock_scope_instance.check_git_diff.side_effect = Exception("Scope error")
        mock_scope.return_value = mock_scope_instance

        passed, output = run_pre_commit_checks()
        # Should still pass the checks even if scope guard fails
        assert passed is True


class TestCheckCodeFiles:
    """Tests for _check_code_files function."""

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_all_pass(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test all checks pass."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=True, issues=[])

        files = [Path("src/file1.py"), Path("src/file2.ts")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is True
        assert "✅ All 2 Test files pass checks" in output
        mock_lint.assert_called_once()
        mock_fmt.assert_called_once()

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_lint_fail(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test lint fails."""
        mock_lint.return_value = (False, "lint error")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=True, issues=[])

        files = [Path("src/file1.py")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is False
        assert "❌ Lint errors:" in output
        assert "lint error" in output

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_format_fail(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test format fails."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (False, "format error")
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=True, issues=[])

        files = [Path("src/file1.py")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is False
        assert "❌ Format errors" in output

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_language_rules_fail(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test language rules fail."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=False, issues=[MagicMock(), MagicMock()])

        files = [Path("src/file1.py")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is False
        assert "❌ src/file1.py: 2 violations" in output

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_no_py_files(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test with no Python files (skips lint/format)."""
        mock_detect.return_value = "typescript"
        mock_validate.return_value = MagicMock(passed=True, issues=[])

        files = [Path("src/file1.ts"), Path("src/file2.js")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is True
        mock_lint.assert_not_called()
        mock_fmt.assert_not_called()
        mock_detect.assert_called()
        mock_validate.assert_called()

    @patch("tools.scripts.hooks.incremental_checks.run_lint_files")
    @patch("tools.scripts.hooks.incremental_checks.run_format_files")
    @patch("tools.scripts.hooks.incremental_checks.detect_language_from_file")
    @patch("tools.scripts.hooks.incremental_checks.validate_file")
    def test_check_code_files_unknown_lang(self, mock_validate, mock_detect, mock_fmt, mock_lint):
        """Test with unknown language (skips language rules)."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (True, "")
        mock_detect.return_value = None

        files = [Path("src/file1.py")]
        passed, output = _check_code_files(files, label="Test")

        assert passed is True
        mock_validate.assert_not_called()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Tests for pre_push hook module."""

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks.pre_push import (
    _check_code_files,
    _check_language_rules,
    _matches_skip_pattern,
    get_changed_files_in_unpushed_commits,
    get_unpushed_commits,
    install_pre_push_hook,
    load_skip_patterns,
    run_pre_push_check,
)


class TestLoadSkipPatterns:
    """Tests for load_skip_patterns function."""

    def test_load_skip_patterns_exists(self, tmp_path: Path):
        """Test loading skip patterns from config."""
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text("skip_patterns:\n  - '**/tests/**/*.py'\n  - '**/demo/**/*.py'\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = load_skip_patterns()
            assert "**/tests/**/*.py" in patterns
            assert "**/demo/**/*.py" in patterns
        finally:
            os.chdir(old_cwd)

    def test_load_skip_patterns_no_config(self, tmp_path: Path):
        """Test when config doesn't exist."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = load_skip_patterns()
            assert patterns == []
        finally:
            os.chdir(old_cwd)

    def test_load_skip_patterns_invalid_yaml(self, tmp_path: Path):
        """Test handling invalid YAML."""
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text("invalid: yaml: [")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = load_skip_patterns()
            assert patterns == []
        finally:
            os.chdir(old_cwd)

    def test_load_skip_patterns_empty_config(self, tmp_path: Path):
        """Test empty config."""
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "config.yml"
        config_file.write_text("other_key: value\n")

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            patterns = load_skip_patterns()
            assert patterns == []
        finally:
            os.chdir(old_cwd)


class TestMatchesSkipPattern:
    """Tests for _matches_skip_pattern function."""

    def test_match_relative_path(self):
        """Test matching relative path."""
        filepath = Path("src/tests/test_file.py")
        patterns = ["**/tests/*.py"]
        assert _matches_skip_pattern(filepath, patterns) is True

    def test_match_absolute_path(self):
        """Test matching absolute path."""
        filepath = Path("/home/user/project/src/tests/test_file.py")
        patterns = ["**/tests/*.py"]
        assert _matches_skip_pattern(filepath, patterns) is True

    def test_match_basename(self):
        """Test matching basename."""
        filepath = Path("src/tests/test_file.py")
        patterns = ["test_*.py"]
        assert _matches_skip_pattern(filepath, patterns) is True

    def test_no_match(self):
        """Test no match."""
        filepath = Path("src/main.py")
        patterns = ["**/tests/**/*.py"]
        assert _matches_skip_pattern(filepath, patterns) is False

    def test_empty_patterns(self):
        """Test empty patterns list."""
        filepath = Path("src/tests/test_file.py")
        assert _matches_skip_pattern(filepath, []) is False


class TestGetUnpushedCommits:
    """Tests for get_unpushed_commits function."""

    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_unpushed_commits_success(self, mock_run):
        """Test successful retrieval."""
        mock_run.side_effect = [
            MagicMock(stdout="main\n", returncode=0),  # branch detection
            MagicMock(stdout="abc123 Commit 1\ndef456 Commit 2\n", returncode=0),  # log
        ]
        commits = get_unpushed_commits()
        assert commits == ["abc123", "def456"]

    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_unpushed_commits_remote_not_exist(self, mock_run):
        """Test when remote branch doesn't exist."""
        mock_run.side_effect = [
            MagicMock(stdout="main\n", returncode=0),
            MagicMock(returncode=1, stderr="fatal: bad revision"),  # remote log fails
            MagicMock(stdout="abc123 Commit 1\n", returncode=0),  # all commits
        ]
        commits = get_unpushed_commits()
        assert commits == ["abc123"]

    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_unpushed_commits_no_commits(self, mock_run):
        """Test when no unpushed commits."""
        mock_run.side_effect = [
            MagicMock(stdout="main\n", returncode=0),
            MagicMock(stdout="", returncode=0),
        ]
        commits = get_unpushed_commits()
        assert commits == []

    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_unpushed_commits_timeout(self, mock_run):
        """Test timeout handling."""
        from subprocess import TimeoutExpired
        mock_run.side_effect = TimeoutExpired("git", 10)
        commits = get_unpushed_commits()
        assert commits == []

    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_unpushed_commits_file_not_found(self, mock_run):
        """Test git not found."""
        mock_run.side_effect = FileNotFoundError()
        commits = get_unpushed_commits()
        assert commits == []


class TestGetChangedFilesInUnpushedCommits:
    """Tests for get_changed_files_in_unpushed_commits function."""

    @patch("tools.scripts.hooks.pre_push.get_unpushed_commits")
    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_changed_files_success(self, mock_run, mock_get_commits):
        """Test successful retrieval."""
        mock_get_commits.return_value = ["abc123", "def456"]
        mock_run.return_value = MagicMock(
            stdout="src/file1.py\nsrc/file2.py\n",
            returncode=0,
        )
        files = get_changed_files_in_unpushed_commits()
        assert len(files) == 2
        assert files[0].name == "file1.py"

    @patch("tools.scripts.hooks.pre_push.get_unpushed_commits")
    def test_get_changed_files_no_commits(self, mock_get_commits):
        """Test when no commits."""
        mock_get_commits.return_value = []
        files = get_changed_files_in_unpushed_commits()
        assert files == []

    @patch("tools.scripts.hooks.pre_push.get_unpushed_commits")
    @patch("tools.scripts.hooks.pre_push.subprocess.run")
    def test_get_changed_files_error(self, mock_run, mock_get_commits):
        """Test error handling."""
        mock_get_commits.return_value = ["abc123"]
        mock_run.return_value = MagicMock(returncode=1, stderr="error")
        files = get_changed_files_in_unpushed_commits()
        assert files == []


class TestCheckCodeFiles:
    """Tests for _check_code_files function."""

    @patch("tools.scripts.hooks.basic_checks.run_lint_files")
    @patch("tools.scripts.hooks.basic_checks.run_format_files")
    def test_check_code_files_pass(self, mock_fmt, mock_lint):
        """Test both checks pass."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (True, "")
        files = [Path("src/file1.py"), Path("src/file2.py")]
        result = _check_code_files(files)
        assert result is True

    @patch("tools.scripts.hooks.basic_checks.run_lint_files")
    @patch("tools.scripts.hooks.basic_checks.run_format_files")
    def test_check_code_files_lint_fail(self, mock_fmt, mock_lint):
        """Test lint fails."""
        mock_lint.return_value = (False, "lint error")
        mock_fmt.return_value = (True, "")
        files = [Path("src/file1.py")]
        result = _check_code_files(files)
        assert result is False

    @patch("tools.scripts.hooks.basic_checks.run_lint_files")
    @patch("tools.scripts.hooks.basic_checks.run_format_files")
    def test_check_code_files_format_fail(self, mock_fmt, mock_lint):
        """Test format fails."""
        mock_lint.return_value = (True, "")
        mock_fmt.return_value = (False, "format error")
        files = [Path("src/file1.py")]
        result = _check_code_files(files)
        assert result is False

    def test_check_code_files_no_py_files(self):
        """Test with no Python files."""
        files = [Path("src/file.js"), Path("src/file.ts")]
        result = _check_code_files(files)
        assert result is True


class TestCheckLanguageRules:
    """Tests for _check_language_rules function."""

    @patch("tools.scripts.validate_language_rules.detect_language_from_file")
    @patch("tools.scripts.validate_language_rules.validate_file")
    @patch("tools.scripts.hooks.pre_push.load_skip_patterns")
    def test_check_language_rules_pass(self, mock_load, mock_validate, mock_detect):
        """Test all files pass."""
        mock_load.return_value = []
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=True, issues=[])
        files = [Path("src/file1.py")]
        passed, skipped = _check_language_rules(files)
        assert passed is True
        assert skipped == []

    @patch("tools.scripts.validate_language_rules.detect_language_from_file")
    @patch("tools.scripts.validate_language_rules.validate_file")
    @patch("tools.scripts.hooks.pre_push.load_skip_patterns")
    def test_check_language_rules_fail(self, mock_load, mock_validate, mock_detect):
        """Test file fails validation."""
        mock_load.return_value = []
        mock_detect.return_value = "python"
        mock_validate.return_value = MagicMock(passed=False, issues=[MagicMock()])
        files = [Path("src/file1.py")]
        passed, skipped = _check_language_rules(files)
        assert passed is False
        assert skipped == []

    @patch("tools.scripts.validate_language_rules.detect_language_from_file")
    @patch("tools.scripts.validate_language_rules.validate_file")
    @patch("tools.scripts.hooks.pre_push.load_skip_patterns")
    def test_check_language_rules_skipped(self, mock_load, mock_validate, mock_detect):
        """Test file skipped by pattern."""
        mock_load.return_value = ["**/tests/*.py"]
        mock_detect.return_value = "python"
        files = [Path("tests/test_file.py")]
        passed, skipped = _check_language_rules(files)
        assert passed is True
        assert len(skipped) == 1

    @patch("tools.scripts.validate_language_rules.detect_language_from_file")
    @patch("tools.scripts.hooks.pre_push.load_skip_patterns")
    def test_check_language_rules_unknown_lang(self, mock_load, mock_detect):
        """Test unknown language."""
        mock_load.return_value = []
        mock_detect.return_value = None
        files = [Path("src/file.xyz")]
        passed, skipped = _check_language_rules(files)
        assert passed is True
        assert skipped == []


class TestRunPrePushCheck:
    """Tests for run_pre_push_check function."""

    @patch("tools.scripts.hooks.pre_push.get_unpushed_commits")
    def test_run_pre_push_check_no_commits(self, mock_get_commits):
        """Test no unpushed commits."""
        mock_get_commits.return_value = []
        result = run_pre_push_check()
        assert result == 0

    @patch("tools.scripts.hooks.pre_push.get_unpushed_commits")
    @patch("tools.scripts.hooks.pre_push.get_changed_files_in_unpushed_commits")
    def test_run_pre_push_check_no_code_files(self, mock_get_files, mock_get_commits):
        """Test no code files changed."""
        mock_get_commits.return_value = ["abc123"]
        mock_get_files.return_value = [Path("README.md"), Path("docs/guide.md")]
        result = run_pre_push_check()
        assert result == 0


class TestInstallPrePushHook:
    """Tests for install_pre_push_hook function."""

    def test_install_pre_push_hook_not_git_repo(self, tmp_path: Path):
        """Test when not in git repo."""
        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = install_pre_push_hook()
            assert result is False
        finally:
            os.chdir(old_cwd)

    def test_install_pre_push_hook_success(self, tmp_path: Path):
        """Test successful installation."""
        git_dir = tmp_path / ".git"
        git_dir.mkdir()
        hooks_dir = git_dir / "hooks"
        hooks_dir.mkdir()

        old_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = install_pre_push_hook()
            assert result is True
            hook_file = hooks_dir / "pre-push"
            assert hook_file.exists()
            content = hook_file.read_text()
            assert "ADG Governance pre-push hook" in content
        finally:
            os.chdir(old_cwd)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

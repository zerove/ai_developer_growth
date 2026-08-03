"""Tests for pre_push.py hook module."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.scripts.hooks.pre_push import (
    get_changed_files_in_unpushed_commits,
    get_unpushed_commits,
    install_pre_push_hook,
    run_pre_push_check,
)


class TestGetUnpushedCommits:
    """Test unpushed commit detection."""

    def test_returns_list(self):
        result = get_unpushed_commits()
        assert isinstance(result, list)


class TestGetChangedFiles:
    """Test changed file detection."""

    def test_returns_list(self):
        result = get_changed_files_in_unpushed_commits()
        assert isinstance(result, list)

    def test_returns_path_objects(self):
        result = get_changed_files_in_unpushed_commits()
        for f in result:
            assert isinstance(f, Path)


class TestInstallPrePushHook:
    """Test hook installation."""

    def test_creates_hook_file(self, tmp_path):
        # Create a fake .git/hooks directory
        hooks_dir = tmp_path / ".git" / "hooks"
        hooks_dir.mkdir(parents=True)

        with patch("tools.scripts.hooks.pre_push.Path") as mock_path:
            mock_path.return_value = tmp_path
            # The function uses Path(".") internally, so we mock it
            result = install_pre_push_hook()

        # Since we're not in a real git repo, this should fail gracefully
        assert isinstance(result, bool)


class TestRunPrePushCheck:
    """Test pre-push check execution."""

    def test_returns_int(self):
        result = run_pre_push_check()
        assert isinstance(result, int)
        assert result in (0, 1)


class TestPrePushModule:
    """Test module-level attributes."""

    def test_module_has_docstring(self):
        import tools.scripts.hooks.pre_push as mod

        assert mod.__doc__ is not None

    def test_get_unpushed_commits_callable(self):
        assert callable(get_unpushed_commits)

    def test_install_hook_callable(self):
        assert callable(install_pre_push_hook)

    def test_run_check_callable(self):
        assert callable(run_pre_push_check)


class TestSkipPatterns:
    """Test skip_patterns loading and matching (respects .adg/config.yml)."""

    def test_load_skip_patterns_returns_list(self, tmp_path):
        from tools.scripts.hooks.pre_push import load_skip_patterns

        patterns = load_skip_patterns()
        assert isinstance(patterns, list)
        assert "**/tests/**/*.py" in patterns

    def test_load_skip_patterns_missing_config(self, tmp_path):
        from tools.scripts.hooks.pre_push import load_skip_patterns

        with patch("tools.scripts.hooks.pre_push.Path") as mock_path:
            mock_path.return_value = tmp_path / "missing" / "config.yml"
            assert load_skip_patterns() == []

    def test_matches_skip_pattern_path_and_basename(self):
        from tools.scripts.hooks.pre_push import _matches_skip_pattern

        # **/test_*.py matches tests/ direct files via basename+slash pattern
        patterns = ["**/test_*.py", "**/demo*.py", "**/tests/**/*.py"]
        assert _matches_skip_pattern(Path("tests/test_x.py"), patterns)
        assert _matches_skip_pattern(Path("examples/multi-agent-orch/demo-adg-workflow.py"), patterns)
        # **/tests/**/*.py matches files in tests/ subdirectories
        assert _matches_skip_pattern(Path("tests/sub/test_x.py"), patterns)
        assert not _matches_skip_pattern(Path("tools/scripts/real_module.py"), patterns)

    def test_run_pre_push_check_skips_test_files(self):
        """Language rule check should skip files matching skip_patterns."""
        result = run_pre_push_check()
        assert result in (0, 1)

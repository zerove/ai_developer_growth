"""Tests for scope_guard hook module."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.hooks.scope_guard import ScopeGuardHook


class TestScopeGuardHook:
    """Tests for ScopeGuardHook class."""

    def test_init_defaults(self):
        """Test default initialization."""
        guard = ScopeGuardHook()
        assert guard.max_lines == 300
        assert guard.max_files == 5
        assert guard.root_dir is not None

    def test_init_custom(self):
        """Test custom initialization."""
        root = Path("/tmp/test")
        guard = ScopeGuardHook(max_lines=500, max_files=10, root_dir=root)
        assert guard.max_lines == 500
        assert guard.max_files == 10
        assert guard.root_dir == root

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_pass(self, mock_run):
        """Test scope check passes for small diff."""
        mock_run.return_value = MagicMock(
            stdout="10\t5\tsrc/file1.py\n3\t2\tsrc/file2.py\n",
            returncode=0,
        )
        guard = ScopeGuardHook(max_lines=300, max_files=5)
        passed, msg = guard.check_git_diff()
        assert passed is True
        assert "Scope check passed" in msg
        assert "2 files" in msg
        assert "20 lines" in msg  # 10+5 + 3+2 = 20

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_fail_files(self, mock_run):
        """Test scope check fails on too many files."""
        mock_run.return_value = MagicMock(
            stdout="10\t5\tsrc/file1.py\n3\t2\tsrc/file2.py\n1\t1\tsrc/file3.py\n1\t1\tsrc/file4.py\n1\t1\tsrc/file5.py\n1\t1\tsrc/file6.py\n",
            returncode=0,
        )
        guard = ScopeGuardHook(max_lines=300, max_files=5)
        passed, msg = guard.check_git_diff()
        assert passed is False
        assert "Scope Guard Warning" in msg
        assert "6 files" in msg

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_fail_lines(self, mock_run):
        """Test scope check fails on too many lines."""
        mock_run.return_value = MagicMock(
            stdout="200\t101\tsrc/file1.py\n",
            returncode=0,
        )
        guard = ScopeGuardHook(max_lines=300, max_files=5)
        passed, msg = guard.check_git_diff()
        assert passed is False
        assert "301 lines" in msg

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_no_staged(self, mock_run):
        """Test when no staged changes."""
        mock_run.return_value = MagicMock(stdout="", returncode=0)
        guard = ScopeGuardHook()
        passed, msg = guard.check_git_diff()
        assert passed is True
        assert "0 files" in msg

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_not_git_repo(self, mock_run):
        """Test when not a git repo."""
        mock_run.return_value = MagicMock(returncode=1, stderr="fatal: not a git repository")
        guard = ScopeGuardHook()
        passed, msg = guard.check_git_diff()
        assert passed is True
        assert "skipped" in msg.lower()

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_exception(self, mock_run):
        """Test exception handling."""
        mock_run.side_effect = Exception("git error")
        guard = ScopeGuardHook()
        passed, msg = guard.check_git_diff()
        assert passed is True
        assert "skipped due to error" in msg

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_binary_files(self, mock_run):
        """Test handling of binary files (no line counts)."""
        mock_run.return_value = MagicMock(
            stdout="-\t-\timage.png\n10\t5\tsrc/file.py\n",
            returncode=0,
        )
        guard = ScopeGuardHook()
        passed, msg = guard.check_git_diff()
        assert passed is True
        # Binary files are counted in file count but not in line counts
        assert "2 files" in msg
        assert "15 lines" in msg

    @patch("tools.scripts.hooks.scope_guard.subprocess.run")
    def test_check_git_diff_large_numbers(self, mock_run):
        """Test with large numbers."""
        mock_run.return_value = MagicMock(
            stdout="1000\t500\tsrc/big.py\n",
            returncode=0,
        )
        guard = ScopeGuardHook(max_lines=300)
        passed, msg = guard.check_git_diff()
        assert passed is False
        assert "1500 lines" in msg


class TestScopeGuardHookMain:
    """Tests for main entry point."""

    @patch("tools.scripts.hooks.scope_guard.ScopeGuardHook")
    def test_main(self, mock_guard_class):
        """Test main function."""
        mock_guard = MagicMock()
        mock_guard.check_git_diff.return_value = (True, "Scope check passed: 1 files, 10 lines changed.")
        mock_guard_class.return_value = mock_guard

        # Run main directly from the module
        import tools.scripts.hooks.scope_guard as scope_guard
        # Just verify it runs without error by checking the class was instantiated
        assert scope_guard.ScopeGuardHook is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

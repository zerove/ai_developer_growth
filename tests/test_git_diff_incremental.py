"""Tests for git_diff_incremental.py (30% → target 80%)."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.git_diff_incremental import (
    get_git_changed_files,
    get_git_staged_files,
    get_git_untracked_files,
    get_incremental_files,
    main,
)


class TestGetGitChangedFiles:
    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="file1.py\nfile2.rs\n", stderr=""
        )
        # Need files to exist for path check
        (tmp_path / "file1.py").touch()
        (tmp_path / "file2.rs").touch()
        files = get_git_changed_files("HEAD", str(tmp_path))
        assert len(files) == 2

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_nonzero_fallback(self, mock_run: MagicMock, tmp_path: Path) -> None:
        """When ref not found, falls back to HEAD."""
        mock_run.side_effect = [
            MagicMock(returncode=128, stdout="", stderr="fatal: bad ref"),
            MagicMock(returncode=0, stdout="fallback.py\n", stderr=""),
        ]
        (tmp_path / "fallback.py").touch()
        files = get_git_changed_files("bad-ref", str(tmp_path))
        assert len(files) == 1

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_empty_output(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        files = get_git_changed_files()
        assert files == []

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        files = get_git_changed_files()
        assert files == []

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_git_not_found(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = FileNotFoundError
        files = get_git_changed_files()
        assert files == []

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_nonexistent_files_filtered(self, mock_run: MagicMock) -> None:
        """Files that don't exist on disk are filtered out."""
        mock_run.return_value = MagicMock(
            returncode=0, stdout="exists.py\nmissing.py\n", stderr=""
        )
        files = get_git_changed_files()
        # Only existing files should be returned
        for f in files:
            assert f.exists()


class TestGetGitUntrackedFiles:
    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(
            returncode=0, stdout="new_file.py\n", stderr=""
        )
        (tmp_path / "new_file.py").touch()
        files = get_git_untracked_files(str(tmp_path))
        assert len(files) == 1

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert get_git_untracked_files() == []

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_timeout(self, mock_run: MagicMock) -> None:
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="git", timeout=30)
        assert get_git_untracked_files() == []


class TestGetGitStagedFiles:
    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_success(self, mock_run: MagicMock, tmp_path: Path) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="staged.py\n", stderr="")
        (tmp_path / "staged.py").touch()
        files = get_git_staged_files(str(tmp_path))
        assert len(files) == 1

    @patch("tools.scripts.git_diff_incremental.subprocess.run")
    def test_empty(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="", stderr="")
        assert get_git_staged_files() == []


class TestGetIncrementalFiles:
    @patch("tools.scripts.git_diff_incremental.get_git_changed_files")
    @patch("tools.scripts.git_diff_incremental.get_git_staged_files")
    @patch("tools.scripts.git_diff_incremental.get_git_untracked_files")
    def test_with_ref(
        self, mock_untracked: MagicMock, mock_staged: MagicMock, mock_changed: MagicMock
    ) -> None:
        mock_changed.return_value = [Path("a.py")]
        mock_staged.return_value = [Path("b.py")]
        mock_untracked.return_value = [Path("c.py")]
        files = get_incremental_files(ref="HEAD~1")
        assert len(files) == 1  # Only changed files when ref is provided
        mock_changed.assert_called_once()

    @patch("tools.scripts.git_diff_incremental.get_git_changed_files")
    @patch("tools.scripts.git_diff_incremental.get_git_staged_files")
    @patch("tools.scripts.git_diff_incremental.get_git_untracked_files")
    def test_without_ref(
        self, mock_untracked: MagicMock, mock_staged: MagicMock, mock_changed: MagicMock
    ) -> None:
        mock_staged.return_value = [Path("a.py")]
        mock_untracked.return_value = [Path("b.py")]
        files = get_incremental_files()
        assert len(files) == 2
        mock_changed.assert_not_called()

    @patch("tools.scripts.git_diff_incremental.get_git_changed_files")
    @patch("tools.scripts.git_diff_incremental.get_git_staged_files")
    @patch("tools.scripts.git_diff_incremental.get_git_untracked_files")
    def test_deduplication(
        self, mock_untracked: MagicMock, mock_staged: MagicMock, mock_changed: MagicMock
    ) -> None:
        """Same file from staged and untracked is deduplicated."""
        mock_staged.return_value = [Path("same.py")]
        mock_untracked.return_value = [Path("same.py")]
        files = get_incremental_files()
        assert len(files) == 1


class TestMain:
    def test_no_args(self) -> None:
        with patch("sys.argv", ["git_diff_incremental"]):
            result = main()
        assert result == 0

    @patch("tools.scripts.git_diff_incremental.get_incremental_files")
    def test_json_output(
        self, mock_get: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_get.return_value = [Path("test.py")]
        with patch("sys.argv", ["git_diff_incremental", "--json"]):
            result = main()
        assert result == 0
        output = capsys.readouterr().out
        assert "test.py" in output

    @patch("tools.scripts.git_diff_incremental.get_incremental_files")
    def test_verbose(
        self, mock_get: MagicMock, capsys: pytest.CaptureFixture[str]
    ) -> None:
        mock_get.return_value = [Path("a.py"), Path("b.py")]
        with patch("sys.argv", ["git_diff_incremental", "--verbose"]):
            result = main()
        assert result == 0

    @patch("tools.scripts.git_diff_incremental.get_incremental_files")
    def test_supported_only(self, mock_get: MagicMock) -> None:
        mock_get.return_value = [Path("test.py"), Path("test.xyz")]
        with patch("sys.argv", ["git_diff_incremental", "--supported-only"]):
            result = main()
        assert result == 0

    @patch("tools.scripts.git_diff_incremental.get_incremental_files")
    def test_error_handling(self, mock_get: MagicMock) -> None:
        mock_get.side_effect = RuntimeError("git error")
        with patch("sys.argv", ["git_diff_incremental"]):
            with pytest.raises(SystemExit):
                main()

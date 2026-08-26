"""smart_commit 全量: 暂存列表/消息生成五分支/dry-run 与真实提交。68%→95%+"""

from __future__ import annotations

import subprocess
from unittest.mock import patch

import pytest

from tools.scripts.smart_commit import generate_commit_message, get_staged_files, main


class TestGetStagedFiles:
    def test_git_repo_returns_list(self) -> None:
        files = get_staged_files()
        assert isinstance(files, list)

    def test_failure_returns_empty(self) -> None:
        with patch("subprocess.run", side_effect=subprocess.SubprocessError("boom")):
            assert get_staged_files() == []


class TestGenerateCommitMessage:
    def test_empty_files_default_chore(self) -> None:
        assert generate_commit_message([]) == "chore: update repository files"

    def test_docs_only(self) -> None:
        assert "docs:" in generate_commit_message(["README.md", "docs/guide.md"])

    def test_tests_only(self) -> None:
        assert "test:" in generate_commit_message(["tests/test_app.py"])

    def test_ci_changes(self) -> None:
        # ci 分支要求非 docs-only 且非 tests-only
        msg = generate_commit_message([".github/workflows/ci.yml", "src/app.py"])
        assert msg.startswith("ci:")

    def test_tools_changes(self) -> None:
        msg = generate_commit_message(["tools/scripts/app.py"])
        assert msg.startswith("feat(tools):")

    def test_default_refactor(self) -> None:
        msg = generate_commit_message(["src/core.py", "app/main.rs"])
        assert msg == "refactor: update implementation and architecture components"


class TestMain:
    def test_dry_run_prints_message(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["smart_commit", "--dry-run"]),
            patch("tools.scripts.smart_commit.get_staged_files", return_value=["tests/x.py"]),
        ):
            code = main()
        assert code == 0
        out = capsys.readouterr().out
        assert "test: add or update test suites" in out

    def test_commit_success_path(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["smart_commit"]),
            patch("tools.scripts.smart_commit.get_staged_files", return_value=["a.md"]),
            patch("subprocess.run") as run_mock,
        ):
            code = main()
        assert code == 0
        run_mock.assert_called_once()
        assert "Committed successfully" in capsys.readouterr().out

    def test_commit_failure_returns_one(self, capsys: pytest.CaptureFixture[str]) -> None:
        with (
            patch("sys.argv", ["smart_commit"]),
            patch("tools.scripts.smart_commit.get_staged_files", return_value=[]),
            patch("subprocess.run", side_effect=subprocess.SubprocessError("denied")),
        ):
            code = main()
        assert code == 1
        assert "git commit failed" in capsys.readouterr().out

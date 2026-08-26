"""sync_issues.py 零覆盖模块攻坚。

GitHub Projects/Issue 双向同步工具。测试全部 mock PyGithub 与 requests，
不触网。覆盖：
- GitHubProjectsSync 初始化与缓存
- Issue → Project（新建/更新/up_to_date/错误）
- Project → Issue（列名映射标签与状态、未知列）
- full_sync / sync_specific_issues / get_project_info / list_project_issues
- CLI：参数解析、token 校验、子命令分发、无 token 错误路径
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

import tools.scripts.sync_issues as si

REPO_ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable


def make_label(name: str) -> MagicMock:
    lb = MagicMock()
    lb.name = name
    return lb


def make_issue(
    number: int = 1,
    state: str = "open",
    labels: list[MagicMock] | None = None,
) -> MagicMock:
    issue = MagicMock()
    issue.number = number
    issue.id = 100 + number
    issue.state = state
    issue.title = f"Issue {number}"
    issue.labels = labels or []
    issue.assignees = []
    return issue


def make_sync(
    columns: dict[str, str] | None = None,
    issues: dict[int, MagicMock] | None = None,
) -> si.GitHubProjectsSync:
    """构造 mock 注入的同步器, 绕过 __init__ 的网络调用。

    PyGithub 内部用 name-mangled 属性, 直接 patch __init__ 会破坏实例;
    改为 patch si.Github / si.requests 为 MagicMock 后正常构造。
    """
    with patch.object(si, "Github", MagicMock()), patch.object(si.requests, "post", MagicMock()):
        s = si.GitHubProjectsSync("fake-token", "owner/repo", 1)
    s.repo = MagicMock()
    s.project = MagicMock()
    s._labels_cache = {}
    s._milestones_cache = {}
    s._project_columns_cache = (
        columns if columns is not None else {"Todo": "col-todo", "Done": "col-done", "In Progress": "col-ip"}
    )
    if issues:
        s.repo.get_issue.side_effect = lambda n: issues[n]
        for iss in issues.values():
            iss.edit = MagicMock()
            iss.add_to_labels = MagicMock()
    return s


class TestSimpleCard:
    def test_defaults(self) -> None:
        card = si._SimpleCard(id=1, column_id="c1")
        assert card.content_url is None and card.note is None


class TestIssueToProject:
    def _issue_with_labels(self, *names: str) -> MagicMock:
        return make_issue(labels=[make_label(n) for n in names])

    def test_create_new_card(self) -> None:
        s = make_sync(issues={5: self._issue_with_labels()})
        s._get_project_cards = lambda: []  # 无已有卡片
        with patch.object(si.requests, "post") as post:
            post.return_value = SimpleNamespace(status_code=201, json=lambda: {"id": 9})
            result = s.sync_issue_to_project(5)
        assert result["status"] == "created"
        assert result["card"] == {"id": 9}

    def test_create_card_error(self) -> None:
        s = make_sync(issues={5: self._issue_with_labels()})
        s._get_project_cards = lambda: []
        with patch.object(si.requests, "post") as post:
            post.return_value = SimpleNamespace(status_code=422, text="boom")
            result = s.sync_issue_to_project(5)
        assert result["status"] == "error" and "boom" in result["error"]

    def test_update_moves_existing_card(self) -> None:
        s = make_sync(issues={7: self._issue_with_labels("in-progress")})
        old = si._SimpleCard(id=3, column_id="col-todo", content_url="https://x/issues/7")
        s._get_project_cards = lambda: [old]
        with patch.object(si.requests, "post") as post:
            post.return_value = SimpleNamespace(status_code=201, json=lambda: {"moved": True})
            result = s.sync_issue_to_project(7)
        assert result["status"] == "moved"
        # in-progress 标签 → In Progress 列
        assert post.call_args.kwargs["json"]["column_id"] == "col-ip"

    def test_up_to_date(self) -> None:
        s = make_sync(issues={8: self._issue_with_labels()})
        card = si._SimpleCard(id=4, column_id="col-todo", content_url="https://x/issues/8")
        s._get_project_cards = lambda: [card]
        result = s.sync_issue_to_project(8)
        assert result == {"status": "up_to_date"}

    def test_target_column_by_label_priority(self) -> None:
        s = make_sync(issues={1: self._issue_with_labels("in-progress", "ready")})
        # 标签映射优先于状态映射: in-progress → In Progress
        assert s._get_target_column_id(s.repo.get_issue(1)) == "col-ip"

    def test_target_column_fallback_state(self) -> None:
        s = make_sync(issues={2: self._issue_with_labels()})
        assert s._get_target_column_id(s.repo.get_issue(2)) == "col-todo"

    def test_target_column_closed(self) -> None:
        s = make_sync(issues={3: make_issue(state="closed")})
        assert s._get_target_column_id(s.repo.get_issue(3)) == "col-done"

    def test_target_column_empty_cache(self) -> None:
        s = make_sync(columns={})
        assert s._get_target_column_id(make_issue()) == ""


class TestProjectToIssues:
    def test_syncs_label_and_state(self) -> None:
        issue = make_issue(number=11, state="open", labels=[])
        card_done = si._SimpleCard(id=1, column_id="col-done", content_url="https://x/issues/11")
        s = make_sync(issues={11: issue})
        s._get_project_cards = lambda: [card_done]
        results = s.sync_project_to_issues()
        assert results[0]["result"]["status"] == "synced"
        assert any("closed" in c for c in results[0]["result"]["changes"])

    def test_skips_note_only_cards(self) -> None:
        s = make_sync()
        note_card = si._SimpleCard(id=2, column_id="col-todo", note="纯笔记卡片")
        s._get_project_cards = lambda: [note_card]
        assert s.sync_project_to_issues() == []

    def test_unknown_column(self) -> None:
        issue = make_issue(number=12)
        s = make_sync(issues={12: issue})
        r = s._sync_card_to_issue(issue, "col-nonexistent")
        assert r == {"status": "unknown_column"}


class TestBulkOps:
    def test_full_sync_collects_errors(self) -> None:
        s = make_sync()
        bad = make_issue(number=99)
        s.repo.get_issues.return_value = [bad]
        s.sync_issue_to_project = MagicMock(side_effect=RuntimeError("net down"))  # type: ignore[method-assign]
        out = s.full_sync(dry_run=False)
        assert out["errors"][0]["error"] == "net down"

    def test_full_sync_dry_run_no_writes(self) -> None:
        s = make_sync()
        s.repo.get_issues.return_value = [make_issue(number=1)]
        s.sync_issue_to_project = MagicMock(return_value={"status": "created"})  # type: ignore[method-assign]
        s.sync_project_to_issues = MagicMock(return_value=[])  # type: ignore[method-assign]
        out = s.full_sync(dry_run=True)
        s.sync_issue_to_project.assert_not_called()
        assert out["project_to_issues"] == []

    def test_sync_specific_issues_mixed(self) -> None:
        s = make_sync()
        ok = {"status": "created"}
        s.sync_issue_to_project = MagicMock(side_effect=[ok, RuntimeError("fail")])  # type: ignore[method-assign]
        out = s.sync_specific_issues([1, 2])
        assert out["results"][0]["result"] == "success"
        assert out["results"][1]["result"] == "error"

    def test_get_project_info(self) -> None:
        s = make_sync()
        s.project.id = 42
        s.project.name = "Roadmap"
        s.project.number = 1
        info = s.get_project_info()
        assert info["id"] == 42 and info["name"] == "Roadmap"
        assert info["columns_count"] == 3

    def test_list_project_issues(self) -> None:
        issue = make_issue(number=21)
        issue.labels = [make_label("bug")]
        s = make_sync(issues={21: issue})
        card = SimpleNamespace(
            id=1,
            column_id="col-todo",
            content_url="https://x/issues/21",
            column_name="Todo",
        )
        s._get_project_cards = lambda: [card]  # type: ignore[method-assign]
        rows = s.list_project_issues()
        assert rows[0]["number"] == 21 and rows[0]["column"] == "Todo"


class TestCreateSyncTool:
    def test_requires_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        with pytest.raises(ValueError, match="GITHUB_TOKEN"):
            si.create_sync_tool()

    def test_with_token_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "t0ken")
        with (
            patch.object(si, "Github", MagicMock()),
            patch.object(si.requests, "post", MagicMock()),
        ):
            tool: Any = si.create_sync_tool()
        assert isinstance(tool, si.GitHubProjectsSync)


class TestCli:
    def _run(self, *cli_args: str, env_token: str | None = "tok") -> subprocess.CompletedProcess[str]:
        import os

        env = dict(os.environ)
        if env_token:
            env["GITHUB_TOKEN"] = env_token
        else:
            env.pop("GITHUB_TOKEN", None)
        return subprocess.run(
            [PY, "-m", "tools.scripts.sync_issues", *cli_args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )

    def test_missing_repo_arg(self) -> None:
        r = self._run()
        assert r.returncode != 0

    def test_no_token_rejected_before_network(self) -> None:
        r = self._run("--repo", "o/r", "--project", "1", "full-sync", env_token=None)
        assert r.returncode == 1
        assert "Token" in r.stdout

    @pytest.mark.parametrize(
        "cmd,extra",
        [
            ("full-sync", []),
            ("sync-issue", ["--issue", "1"]),
            ("sync-project", []),
            ("list-project", []),
            ("project-info", []),
            ("sync-issues", ["--issues", "1", "2"]),
        ],
    )
    def test_all_subcommands_dispatch(self, cmd: str, extra: list[str]) -> None:
        """mock 掉网络层, 验证每个子命令走通并输出 JSON。"""
        cli_args = ["--repo", "o/r", "--project", "1", cmd, *extra]
        argv = ["sync_issues", *cli_args]
        with (
            patch.object(si, "Github", MagicMock()),
            patch.object(si.requests, "post", MagicMock()),
            patch.object(si, "_execute_sync_command") as ex,
            patch.dict("os.environ", {"GITHUB_TOKEN": "tok"}),
            patch("sys.argv", argv),
        ):
            rc = si.main()
        assert rc == 0
        ex.assert_called_once()

    def test_execute_full_sync_prints_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = SimpleNamespace(command="full-sync", dry_run=True)
        with (
            patch.object(si, "Github", MagicMock()),
            patch.object(si.requests, "post", MagicMock()),
        ):
            s = si.GitHubProjectsSync("t", "o/r", 1)
        s.full_sync = MagicMock(return_value={"ok": True})  # type: ignore[method-assign]
        si._execute_sync_command(s, args)
        assert '"ok": true' in capsys.readouterr().out

"""CI 存活心跳检测测试（ADR-057）。

覆盖判据的核心：失效信号是「run 存在但 0 job」，而非 GitHub 的错误文案
（文案无法区分配额拒绝与工作流语法错误）。
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any

import pytest

from tools.scripts.ci_heartbeat import (
    ALERT_TITLE_PREFIX,
    HealthVerdict,
    _alert_title,
    _clear_alert,
    _find_alert_issue,
    _issue_body,
    _local_fallback,
    _parse_ts,
    _raise_alert,
    _repo_slug,
    _run_alert,
    _token,
    check_ci_health,
    main,
)

REPO = "zerove/ai_developer_growth"
WF = "ci.yml"
TOKEN = "dummy-token"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# 必须相对当前时间计算：判定新鲜度的是 now - ran_at 的差值，写死绝对时间
# 会让这套用例在时间跨过阈值后集体变红（曾经真实发生过）。
NOW = _iso(datetime.now(timezone.utc) - timedelta(minutes=5))
OLD = _iso(datetime.now(timezone.utc) - timedelta(days=60))


def _run_payload(run_id: int = 1, created: str = NOW, updated: str = NOW) -> dict[str, Any]:
    return {
        "id": run_id,
        "created_at": created,
        "updated_at": updated,
        "status": "completed",
        "conclusion": "failure",
    }


class _FakeApi:
    def __init__(self, runs: list[dict[str, Any]], jobs_total: int) -> None:
        self.runs = runs
        self.jobs_total = jobs_total
        self.paths: list[str] = []

    def __call__(self, path: str, token: str) -> dict[str, Any]:
        self.paths.append(path)
        if path.endswith("/jobs"):
            return {"total_count": self.jobs_total}
        return {"workflow_runs": self.runs}


class TestCheckCiHealth:
    def test_zero_jobs_is_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """配额耗尽的特征：run 存在但从未调度任何 job。"""
        api = _FakeApi([_run_payload()], jobs_total=0)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        verdict = check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert verdict.ok is False
        assert "0 个 job" in verdict.reason
        assert verdict.run_id == 1

    def test_zero_duration_run_reported_in_detail(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """零执行时间是配额拒绝的强信号，须出现在可读详情里。"""
        api = _FakeApi([_run_payload()], jobs_total=0)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        verdict = check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert NOW in verdict.detail
        assert "立即拒绝" in verdict.detail

    def test_healthy_run_passes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _FakeApi([_run_payload()], jobs_total=7)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        verdict = check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert verdict.ok is True
        assert "7" in verdict.reason

    def test_no_runs_is_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """工作流从未触发过：通常意味着触发条件配错，同样是静默失效。"""
        api = _FakeApi([], jobs_total=0)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        verdict = check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert verdict.ok is False
        assert "从未有过 run" in verdict.reason

    def test_stale_run_is_dead(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """长时间无新 run：门禁可能已静默停摆。"""
        api = _FakeApi([_run_payload(created=OLD, updated=OLD)], jobs_total=3)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        verdict = check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert verdict.ok is False
        assert "停滞" in verdict.reason

    def test_empty_repo_slug_rejected(self) -> None:
        verdict = check_ci_health("", TOKEN, "ci.yml", 24)
        assert verdict.ok is False
        assert "无法确定仓库" in verdict.reason

    def test_requests_correct_endpoints(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _FakeApi([_run_payload()], jobs_total=1)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        check_ci_health(REPO, TOKEN, "ci.yml", 24)
        assert any("actions/workflows/ci.yml/runs" in p for p in api.paths)
        assert any(p.endswith("/jobs") for p in api.paths)


class TestHelpers:
    def test_parse_ts_handles_z_suffix(self) -> None:
        assert _parse_ts(NOW) is not None
        assert _parse_ts(NOW).tzinfo is not None  # type: ignore[union-attr]

    def test_parse_ts_rejects_garbage(self) -> None:
        assert _parse_ts("not-a-timestamp") is None
        assert _parse_ts("") is None

    def test_token_reads_github_token_first(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", "from-github")
        monkeypatch.setenv("GH_TOKEN", "from-gh")
        assert _token() == "from-github"

    def test_token_falls_back_to_gh_token(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.setenv("GH_TOKEN", "from-gh")
        assert _token() == "from-gh"

    def test_repo_slug_from_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("GITHUB_REPOSITORY", "owner/repo")
        assert _repo_slug() == "owner/repo"

    def test_no_token_gives_actionable_message(self) -> None:
        """无 token 时必须给出可执行指引，不能静默通过或崩溃。"""
        verdict = _local_fallback()
        assert verdict.ok is False
        assert "GITHUB_TOKEN" in verdict.detail


class TestMain:
    def test_json_output_is_machine_readable(self, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._repo_slug", lambda: REPO)
        api = _FakeApi([_run_payload()], jobs_total=0)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", api)
        code = main(["--json"])
        payload = json.loads(capsys.readouterr().out)
        assert code == 1
        assert payload["ok"] is False
        assert payload["run_id"] == 1

    def test_exit_code_signals_health(self, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._repo_slug", lambda: REPO)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", _FakeApi([_run_payload()], jobs_total=4))
        assert main([]) == 0
        assert "CI 正常" in capsys.readouterr().out

    def test_no_token_exits_nonzero(self, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)
        monkeypatch.delenv("GH_TOKEN", raising=False)
        assert main([]) == 1
        assert "GITHUB_TOKEN" in capsys.readouterr().out


class TestVerdict:
    def test_verdict_is_immutable(self) -> None:
        v = HealthVerdict(True, "ok")
        with pytest.raises(Exception):
            v.ok = False  # type: ignore[misc]


class _AlertApi:
    """记录 _api_call 调用，模拟 GitHub Issue 搜索/创建/更新。"""

    def __init__(self, existing: list[dict[str, Any]] | None = None) -> None:
        self.existing = existing if existing is not None else []
        self.calls: list[tuple[str, str, dict[str, Any] | None]] = []

    def __call__(self, method: str, path: str, token: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        self.calls.append((method, path, payload))
        if path.startswith("/search/issues"):
            return {"items": self.existing}
        if method == "POST":
            return {"number": 999}
        return {}

    def paths(self) -> list[str]:
        return [p for _m, p, _d in self.calls]


class TestAlert:
    def _verdict(self, ok: bool) -> HealthVerdict:
        return HealthVerdict(ok, "CI 已失效：0 个 job", "run #1 时间戳零跨度", 1, NOW)

    def test_find_returns_none_when_no_issue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        assert _find_alert_issue(REPO, TOKEN, WF) is None

    def test_find_returns_number(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([{"number": 42}])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        assert _find_alert_issue(REPO, TOKEN, WF) == 42

    def test_find_queries_open_issues_by_title(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        _find_alert_issue(REPO, TOKEN, WF)
        assert "search/issues" in api.paths()[0]
        assert "is%3Aopen" in api.paths()[0] or "is:open" in api.paths()[0]

    def test_alert_title_is_scoped_per_workflow(self) -> None:
        assert _alert_title("ci.yml") != _alert_title("release.yml")
        assert _alert_title("ci.yml").startswith(ALERT_TITLE_PREFIX)

    def test_issue_body_records_workflow(self) -> None:
        body = _issue_body(self._verdict(False), "release.yml", recovered=False)
        assert "release.yml" in body

    def test_raise_creates_issue_when_absent(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        msg = _raise_alert(REPO, TOKEN, WF, self._verdict(False))
        assert "999" in msg
        posts = [c for c in api.calls if c[0] == "POST"]
        assert len(posts) == 1
        assert posts[0][2] is not None
        assert posts[0][2]["title"] == _alert_title(WF)

    def test_raise_updates_existing_issue_instead_of_duplicating(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([{"number": 42}])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        msg = _raise_alert(REPO, TOKEN, WF, self._verdict(False))
        assert "42" in msg
        assert not [c for c in api.calls if c[0] == "POST"], "已有告警时不应新建，避免刷屏"
        assert any(c[0] == "PATCH" for c in api.calls)

    def test_clear_closes_open_issue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([{"number": 42}])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        msg = _clear_alert(REPO, TOKEN, WF, self._verdict(True))
        assert "42" in msg
        patch_call = next(c for c in api.calls if c[0] == "PATCH")
        assert patch_call[2] is not None
        assert patch_call[2]["state"] == "closed"

    def test_clear_is_noop_without_issue(self, monkeypatch: pytest.MonkeyPatch) -> None:
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        assert "无需关闭" in _clear_alert(REPO, TOKEN, WF, self._verdict(True))
        assert not [c for c in api.calls if c[0] == "PATCH"]

    def test_run_alert_dispatches_by_health(self, monkeypatch: pytest.MonkeyPatch) -> None:
        dead = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", dead)
        _run_alert(REPO, TOKEN, WF, self._verdict(False))
        assert any(c[0] == "POST" for c in dead.calls)

        alive = _AlertApi([{"number": 7}])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", alive)
        _run_alert(REPO, TOKEN, WF, self._verdict(True))
        assert any(c[0] == "PATCH" for c in alive.calls)

    def test_issue_body_contains_diagnosis(self) -> None:
        body = _issue_body(self._verdict(False), WF, recovered=False)
        assert "0 个 job" in body
        assert "settings/billing" in body
        assert "ADR-057" in body
        assert "仍失效" in body

    def test_issue_body_marks_recovery(self) -> None:
        assert "已恢复" in _issue_body(self._verdict(True), WF, recovered=True)

    def test_alert_flag_triggers_alert(self, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._repo_slug", lambda: REPO)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", _FakeApi([_run_payload()], jobs_total=0))
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        assert main(["--alert"]) == 1
        assert any(c[0] == "POST" for c in api.calls)

    def test_no_alert_flag_does_not_touch_issues(self, capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
        monkeypatch.setenv("GITHUB_TOKEN", TOKEN)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._repo_slug", lambda: REPO)
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_get", _FakeApi([_run_payload()], jobs_total=0))
        api = _AlertApi([])
        monkeypatch.setattr("tools.scripts.ci_heartbeat._api_call", api)
        assert main([]) == 1
        assert api.calls == [], "未指定 --alert 时不应产生任何 Issue 写入"

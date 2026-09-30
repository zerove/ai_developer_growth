"""CI 存活心跳检测测试（ADR-057）。

覆盖判据的核心：失效信号是「run 存在但 0 job」，而非 GitHub 的错误文案
（文案无法区分配额拒绝与工作流语法错误）。
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tools.scripts.ci_heartbeat import (
    HealthVerdict,
    _local_fallback,
    _parse_ts,
    _repo_slug,
    _token,
    check_ci_health,
    main,
)

REPO = "zerove/ai_developer_growth"
TOKEN = "dummy-token"

NOW = "2026-09-29T13:55:27Z"
OLD = "2026-08-01T00:00:00Z"


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

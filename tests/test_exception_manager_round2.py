"""exception_manager 第二轮: webhook 线程/到期告警全分支/GitOps 双向/Enhanced 集成。

覆盖 62%→80%+: mock urllib/subprocess/git, 不发真实网络请求。
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.exception_manager import (
    ApprovalAction,
    ApprovalWorkflow,
    EnhancedExceptionManager,
    ExceptionRequest,
    ExceptionStatus,
    ExpirationManager,
    GitOpsSync,
)


def make_req(
    status: ExceptionStatus = ExceptionStatus.APPROVED,
    expires: str | None = None,
) -> ExceptionRequest:
    req = ExceptionRequest(
        id="req-1",
        rule_id="no-any",
        paths=["src/**"],
        reason="legacy",
        severity="high",
        requested_severity="medium",
        expires=expires or (datetime.utcnow() + timedelta(days=7)).isoformat(),
        created_by="alice",
        created_at=datetime.utcnow().isoformat(),
        reviewers=["bob"],
    )
    req.status = status
    return req


# ── ApprovalWorkflow 通知与边界 ──────────────────────────────


class TestApprovalWorkflowNotifications:
    def test_webhook_thread_spawned_on_create(self) -> None:
        wf = ApprovalWorkflow(notification_webhook="http://hook.test/x")
        with patch("tools.scripts.exception_manager.threading.Thread") as thread_mock:
            req = wf.create_request("rule", ["p"], "why", "high", "low", None, "alice")
            thread_mock.assert_called_once()
        assert req.id in {r.id for r in wf.list_requests()}

    def test_send_webhook_noop_without_url(self) -> None:
        wf = ApprovalWorkflow()
        wf._send_webhook("evt", {})  # 不抛异常即可
        wf._notify_request_created(wf.create_request("rule", ["p"], "why", "high", "low", None, "a"))

    def test_review_unknown_request_raises(self) -> None:
        wf = ApprovalWorkflow()
        with pytest.raises(ValueError, match="not found"):
            wf.review_request("ghost", ApprovalAction.APPROVE, "rev")

    def test_double_review_raises(self) -> None:
        wf = ApprovalWorkflow()
        req = wf.create_request("rule", ["p"], "why", "high", "low", None, "a")
        wf.review_request(req.id, ApprovalAction.REJECT, "rev", "no")
        with pytest.raises(ValueError, match="already"):
            wf.review_request(req.id, ApprovalAction.APPROVE, "rev")

    def test_auto_approve_owner_and_non_owner(self) -> None:
        wf = ApprovalWorkflow(auto_approve_owners=["owner"])
        req = wf.create_request("rule", ["p"], "why", "high", "low", None, "owner")
        assert wf.auto_approve_if_owner(req) is True
        other = wf.create_request("rule2", ["p"], "why", "high", "low", None, "stranger")
        assert wf.auto_approve_if_owner(other) is False

    def test_approval_history_filtering(self) -> None:
        wf = ApprovalWorkflow()
        r1 = wf.create_request("r1", ["p"], "why", "h", "l", None, "a")
        r2 = wf.create_request("r2", ["p"], "why", "h", "l", None, "a")
        wf.review_request(r1.id, ApprovalAction.APPROVE, "rev")
        wf.review_request(r2.id, ApprovalAction.REJECT, "rev")
        assert len(wf.get_approval_history(r1.id)) == 1


# ── ExpirationManager 全分支 ─────────────────────────────────


class TestExpirationBranches:
    def _mgr(self, **kw: object) -> ExpirationManager:
        return ExpirationManager(**kw)  # type: ignore[arg-type]

    def test_pending_and_mark_notified(self) -> None:
        mgr = self._mgr(alert_days=[1])
        soon = (datetime.utcnow() + timedelta(days=1, hours=1)).isoformat()
        alerts = mgr.check_expirations([make_req(expires=soon)])
        assert alerts and mgr.get_pending_alerts()
        mgr.mark_alert_notified(alerts[0])
        assert mgr.get_pending_alerts() == []
        assert alerts[0].notified_at is not None

    def test_invalid_expires_skipped(self) -> None:
        mgr = self._mgr(auto_revoke=False)
        assert mgr.check_expirations([make_req(expires="not-a-date")]) == []

    def test_non_approved_or_no_expiry_skipped(self) -> None:
        mgr = self._mgr()
        pending = make_req(status=ExceptionStatus.PENDING)
        no_exp = make_req(expires=None)
        assert mgr.check_expirations([pending, no_exp]) == []

    def test_alert_dedup_across_calls(self) -> None:
        mgr = self._mgr(alert_days=[3])
        soon = (datetime.utcnow() + timedelta(days=3, hours=12)).isoformat()
        first = mgr.check_expirations([make_req(expires=soon)])
        second = mgr.check_expirations([make_req(expires=soon)])
        assert len(first) == 1 and second == []

    def test_alert_webhook_failure_swallowed(self) -> None:
        mgr = self._mgr(alert_days=[1], notification_webhook="http://hook.test/a")
        soon = (datetime.utcnow() + timedelta(days=1, hours=2)).isoformat()
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            alerts = mgr.check_expirations([make_req(expires=soon)])  # 不抛异常
        assert alerts

    def test_expired_notification_path(self) -> None:
        mgr = self._mgr(auto_revoke=True, notification_webhook="http://hook.test/e")
        past = (datetime.utcnow() - timedelta(days=2)).isoformat()
        req = make_req(expires=past)
        with patch("urllib.request.urlopen", side_effect=OSError("down")):
            mgr.check_expirations([req])  # 触发 _notify_expired 异常吞噬
        assert req.status == ExceptionStatus.EXPIRED


# ── GitOpsSync ───────────────────────────────────────────────


class TestGitOpsSync:
    def test_round_trip_yaml(self, tmp_path: Path) -> None:
        sync = GitOpsSync(repo_path=tmp_path)
        reqs = [make_req()]
        assert sync.sync_to_git(reqs) is True
        loaded = sync.sync_from_git()
        assert loaded and loaded[0].status == ExceptionStatus.APPROVED
        assert loaded[0].id == "req-1"

    def test_sync_from_missing_file(self, tmp_path: Path) -> None:
        sync = GitOpsSync(repo_path=tmp_path)
        assert sync.sync_from_git() == []

    def test_sync_to_git_auto_commit_off(self, tmp_path: Path) -> None:
        sync = GitOpsSync(repo_path=tmp_path, auto_commit=False)
        with patch("subprocess.run") as run_mock:
            assert sync.sync_to_git([make_req()]) is True
            run_mock.assert_not_called()

    def test_git_commit_runs_subprocess(self, tmp_path: Path) -> None:
        sync = GitOpsSync(repo_path=tmp_path)
        ok = MagicMock(returncode=0)
        with patch("tools.scripts.exception_manager.subprocess.run", return_value=ok) as run_mock:
            sync.sync_to_git([make_req()])
        commands = [c.args[0][0] for c in run_mock.call_args_list]
        assert "git" in commands

    def test_pull_latest_success_and_failure(self, tmp_path: Path) -> None:
        sync = GitOpsSync(repo_path=tmp_path)
        with patch("tools.scripts.exception_manager.subprocess.run"):
            assert sync.pull_latest() is True
        import subprocess as sp

        boom = sp.CalledProcessError(1, "git")
        boom.stderr = b"boom"
        with patch("tools.scripts.exception_manager.subprocess.run", side_effect=boom):
            assert sync.pull_latest() is False

    def test_sync_from_corrupt_yaml(self, tmp_path: Path) -> None:
        (tmp_path / ".jcode").mkdir()
        (tmp_path / ".jcode" / "exceptions.yaml").write_text("{ broken: [")
        sync = GitOpsSync(repo_path=tmp_path)
        assert sync.sync_from_git() == []


# ── EnhancedExceptionManager 集成 ────────────────────────────


class TestEnhancedManager:
    def test_load_from_config_and_get(self, tmp_path: Path) -> None:
        cfg = tmp_path / "governance.yaml"
        import yaml

        req = make_req()
        cfg.write_text(yaml.dump({"exceptions": [{**req.to_dict(), "status": "approved"}]}))
        mgr = EnhancedExceptionManager(config_path=cfg)
        assert mgr.get_request("req-1") is not None
        assert len(mgr.get_all_requests()) == 1

    def test_load_corrupt_config_tolerated(self, tmp_path: Path) -> None:
        cfg = tmp_path / "gov.yaml"
        cfg.write_text("{ bad yaml [")
        mgr = EnhancedExceptionManager(config_path=cfg)  # 不抛异常
        assert mgr.get_all_requests() == []

    def test_full_lifecycle_with_gitops(self, tmp_path: Path) -> None:
        gitops = GitOpsSync(repo_path=tmp_path)
        mgr = EnhancedExceptionManager(
            config_path=tmp_path / ".jcode" / "gov.yaml",
            gitops=gitops,
        )
        req = mgr.request_exception(
            rule_id="SEC-001",
            paths=["lib/**"],
            reason="temp",
            severity="high",
            requested_severity="medium",
            expires=(datetime.utcnow() + timedelta(days=10)).isoformat(),
            created_by="dev",
        )
        assert mgr.approve_exception(req.id, "sec-team") is True
        assert mgr.get_active_exceptions()[0].id == req.id
        report = mgr.generate_audit_report()
        assert report["total_requests"] == 1
        assert report["by_status"]["approved"] == 1

    def test_reject_returns_true_and_revoked_flow(self, tmp_path: Path) -> None:
        mgr = EnhancedExceptionManager(config_path=tmp_path / "cfg.yaml")
        req = mgr.request_exception("R", ["p"], "why", "h", "m", None, "dev")
        assert mgr.reject_exception(req.id, "rev") is True
        r2 = mgr.request_exception("R2", ["p"], "why", "h", "m", None, "dev")
        assert mgr.revoke_exception(r2.id) is True
        assert mgr.revoke_exception("ghost") is False

    def test_check_expirations_delegates(self, tmp_path: Path) -> None:
        mgr = EnhancedExceptionManager(config_path=tmp_path / "cfg.yaml")
        assert mgr.check_expirations() == []

    def test_save_config_creates_parents(self, tmp_path: Path) -> None:
        cfg = tmp_path / "deep" / "nested" / "cfg.yaml"
        mgr = EnhancedExceptionManager(config_path=cfg)
        mgr.request_exception("R", ["p"], "why", "h", "m", None, "d")
        assert cfg.exists()

    def test_gitops_init_sync_merges(self, tmp_path: Path) -> None:
        gitops = GitOpsSync(repo_path=tmp_path)
        gitops.sync_to_git([make_req()])
        mgr = EnhancedExceptionManager(
            config_path=tmp_path / "cfg.yaml",
            gitops=gitops,
        )
        assert any(r.id == "req-1" for r in mgr.get_all_requests())

    def test_factory_function(self, tmp_path: Path) -> None:
        from tools.scripts.exception_manager import create_enhanced_manager

        mgr = create_enhanced_manager(
            config_path=tmp_path / "c.yaml",
            repo_path=tmp_path,
            required_approvals=2,
            auto_approve_owners=["o"],
            notification_webhook="http://h",
            alert_days=[5],
        )
        assert isinstance(mgr, EnhancedExceptionManager)

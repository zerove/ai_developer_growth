"""Tests for exception manager"""

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from tools.scripts.exception_manager import (
    ApprovalAction,
    ApprovalWorkflow,
    EnhancedExceptionManager,
    ExceptionRequest,
    ExceptionStatus,
    ExpirationManager,
    create_enhanced_manager,
)


class TestExceptionRequest:
    """Test ExceptionRequest dataclass"""

    def test_create_request(self):
        req = ExceptionRequest(
            id="test-123",
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
            created_at=datetime.utcnow().isoformat(),
        )
        assert req.id == "test-123"
        assert req.rule_id == "R001"
        assert req.status == ExceptionStatus.PENDING

    def test_to_dict(self):
        req = ExceptionRequest(
            id="test-123",
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
            created_at=datetime.utcnow().isoformat(),
        )
        data = req.to_dict()
        assert data["id"] == "test-123"
        assert data["rule_id"] == "R001"
        assert data["status"] == "pending"

    def test_from_dict(self):
        data = {
            "id": "test-123",
            "rule_id": "R001",
            "paths": ["src/**/*.py"],
            "reason": "Test reason",
            "severity": "error",
            "requested_severity": "warning",
            "expires": None,
            "created_by": "test-user",
            "created_at": datetime.utcnow().isoformat(),
            "status": "pending",
        }
        req = ExceptionRequest.from_dict(data)
        assert req.id == "test-123"
        assert req.status == ExceptionStatus.PENDING


class TestApprovalWorkflow:
    """Test ApprovalWorkflow"""

    def test_create_request(self):
        workflow = ApprovalWorkflow()
        req = workflow.create_request(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        assert req.id in workflow._requests
        assert req.status == ExceptionStatus.PENDING

    def test_approve_request(self):
        workflow = ApprovalWorkflow()
        req = workflow.create_request(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        result = workflow.review_request(req.id, ApprovalAction.APPROVE, "reviewer", "Approved")
        assert result is True
        assert req.status == ExceptionStatus.APPROVED
        assert req.approved_by == "reviewer"

    def test_reject_request(self):
        workflow = ApprovalWorkflow()
        req = workflow.create_request(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        result = workflow.review_request(req.id, ApprovalAction.REJECT, "reviewer", "Not needed")
        assert result is False
        assert req.status == ExceptionStatus.REJECTED
        assert req.rejection_reason == "Not needed"

    def test_list_requests(self):
        workflow = ApprovalWorkflow()
        workflow.create_request("R001", ["src/a.py"], "Reason 1", "error", "warning", None, "user1")
        workflow.create_request("R002", ["src/b.py"], "Reason 2", "warning", "info", None, "user2")
        requests = workflow.list_requests()
        assert len(requests) == 2

    def test_list_requests_by_status(self):
        workflow = ApprovalWorkflow()
        req1 = workflow.create_request("R001", ["src/a.py"], "Reason 1", "error", "warning", None, "user1")
        workflow.create_request("R002", ["src/b.py"], "Reason 2", "warning", "info", None, "user2")
        workflow.review_request(req1.id, ApprovalAction.APPROVE, "reviewer", "Approved")
        pending = workflow.list_requests(ExceptionStatus.PENDING)
        approved = workflow.list_requests(ExceptionStatus.APPROVED)
        assert len(pending) == 1
        assert len(approved) == 1


class TestExpirationManager:
    """Test ExpirationManager"""

    def test_check_expirations_no_expiring(self):
        manager = ExpirationManager(alert_days=[30, 7, 1])
        req = ExceptionRequest(
            id="test-123",
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test",
            severity="error",
            requested_severity="warning",
            expires=(datetime.utcnow() + timedelta(days=60)).isoformat(),
            created_by="test-user",
            created_at=datetime.utcnow().isoformat(),
            status=ExceptionStatus.APPROVED,
        )
        alerts = manager.check_expirations([req])
        assert len(alerts) == 0

    def test_check_expirations_alert_1_day(self):
        manager = ExpirationManager(alert_days=[30, 7, 1])
        # Use a fixed future time that will be exactly 1 day from "now" in the test
        # We need to mock datetime.utcnow for this test
        req = ExceptionRequest(
            id="test-123",
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test",
            severity="error",
            requested_severity="warning",
            expires=(datetime.utcnow() + timedelta(days=1, hours=1)).isoformat(),  # Add 1 hour to ensure it's > 0 days
            created_by="test-user",
            created_at=datetime.utcnow().isoformat(),
            status=ExceptionStatus.APPROVED,
        )
        alerts = manager.check_expirations([req])
        assert len(alerts) == 1
        assert alerts[0].days_until_expiry == 1

    def test_auto_revoke_expired(self):
        manager = ExpirationManager(alert_days=[30, 7, 1], auto_revoke=True)
        req = ExceptionRequest(
            id="test-123",
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test",
            severity="error",
            requested_severity="warning",
            expires=(datetime.utcnow() - timedelta(days=1)).isoformat(),
            created_by="test-user",
            created_at=datetime.utcnow().isoformat(),
            status=ExceptionStatus.APPROVED,
        )
        manager.check_expirations([req])
        assert req.status == ExceptionStatus.EXPIRED


class TestEnhancedExceptionManager:
    """Test EnhancedExceptionManager"""

    def setup_method(self):
        self.temp_dir = tempfile.mkdtemp()
        self.config_path = Path(self.temp_dir) / "governance.yaml"

    def teardown_method(self):
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_request_exception(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req = manager.request_exception(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        assert req.id in manager._requests
        assert req.status == ExceptionStatus.PENDING
        assert self.config_path.exists()

    def test_approve_exception(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req = manager.request_exception(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        result = manager.approve_exception(req.id, "reviewer", "Approved")
        assert result is True
        assert req.status == ExceptionStatus.APPROVED

    def test_reject_exception(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req = manager.request_exception(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        result = manager.reject_exception(req.id, "reviewer", "Rejected")
        assert result is True
        assert req.status == ExceptionStatus.REJECTED

    def test_revoke_exception(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req = manager.request_exception(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        manager.approve_exception(req.id, "reviewer", "Approved")
        result = manager.revoke_exception(req.id)
        assert result is True
        assert req.status == ExceptionStatus.REVOKED

    def test_get_active_exceptions(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req1 = manager.request_exception("R001", ["src/a.py"], "Reason 1", "error", "warning", None, "user1")
        manager.request_exception("R002", ["src/b.py"], "Reason 2", "warning", "info", None, "user2")
        manager.approve_exception(req1.id, "reviewer", "Approved")
        active = manager.get_active_exceptions()
        assert len(active) == 1
        assert active[0].id == req1.id

    def test_persistence(self):
        """Test that exceptions persist across manager instances"""
        manager1 = EnhancedExceptionManager(config_path=self.config_path)
        req = manager1.request_exception(
            rule_id="R001",
            paths=["src/**/*.py"],
            reason="Test reason",
            severity="error",
            requested_severity="warning",
            expires=None,
            created_by="test-user",
        )
        manager1.approve_exception(req.id, "reviewer", "Approved")

        # Create new manager with same config
        manager2 = EnhancedExceptionManager(config_path=self.config_path)
        requests = manager2.get_all_requests()
        assert len(requests) == 1
        assert requests[0].id == req.id
        assert requests[0].status == ExceptionStatus.APPROVED

    def test_generate_audit_report(self):
        manager = EnhancedExceptionManager(config_path=self.config_path)
        req = manager.request_exception("R001", ["src/a.py"], "Reason 1", "error", "warning", None, "user1")
        manager.approve_exception(req.id, "reviewer", "Approved")
        report = manager.generate_audit_report()
        assert report["total_requests"] == 1
        assert report["by_status"]["approved"] == 1
        assert len(report["requests"]) == 1


class TestCreateEnhancedManager:
    """Test create_enhanced_manager factory"""

    def test_create_with_defaults(self):
        manager = create_enhanced_manager()
        assert isinstance(manager, EnhancedExceptionManager)
        assert manager.approval is not None
        assert manager.expiration is not None

    def test_create_with_custom_params(self):
        manager = create_enhanced_manager(
            required_approvals=2,
            auto_approve_owners=["owner1", "owner2"],
            notification_webhook="http://webhook",
            alert_days=[14, 7, 3],
        )
        assert manager.approval.required_approvals == 2
        assert manager.approval.auto_approve_owners == ["owner1", "owner2"]
        assert manager.expiration.alert_days == [14, 7, 3]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

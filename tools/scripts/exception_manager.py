"""
Baseline/Exception Manager - 增强版

核心增强功能:
- 例外审批流 (申请 → 审核 → 批准/拒绝)
- 到期告警 (提前 N 天通知)
- GitOps 同步 (双向同步例外规则到 Git 仓库)
- 审计日志
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# 数据模型层已拆到 _exception_models.py, 这里显式 re-export 保持公开 API 与导入路径不变
from ._exception_models import (
    ApprovalAction as ApprovalAction,
)
from ._exception_models import (
    ApprovalRecord as ApprovalRecord,
)
from ._exception_models import (
    ExceptionRequest as ExceptionRequest,
)
from ._exception_models import (
    ExceptionStatus as ExceptionStatus,
)
from ._exception_models import (
    ExpirationAlert as ExpirationAlert,
)

__all__ = [
    "ExceptionStatus",
    "ApprovalAction",
    "ExceptionRequest",
    "ApprovalRecord",
    "ExpirationAlert",
    "ApprovalWorkflow",
    "ExpirationManager",
    "GitOpsSync",
    "EnhancedExceptionManager",
    "create_enhanced_manager",
]

logger = logging.getLogger(__name__)


class ApprovalWorkflow:
    """例外审批工作流"""

    def __init__(
        self,
        required_approvals: int = 1,
        auto_approve_owners: list[str] | None = None,
        notification_webhook: str | None = None,
    ):
        self.required_approvals = required_approvals
        self.auto_approve_owners = auto_approve_owners or []
        self.notification_webhook = notification_webhook
        self._requests: dict[str, ExceptionRequest] = {}
        self._approval_records: list[ApprovalRecord] = []

    def create_request(
        self,
        rule_id: str,
        paths: list[str],
        reason: str,
        severity: str,
        requested_severity: str,
        expires: str | None,
        created_by: str,
        reviewers: list[str] | None = None,
    ) -> ExceptionRequest:
        """创建例外申请"""
        req = ExceptionRequest(
            id=str(uuid.uuid4())[:8],
            rule_id=rule_id,
            paths=paths,
            reason=reason,
            severity=severity,
            requested_severity=requested_severity,
            expires=expires,
            created_by=created_by,
            created_at=datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            reviewers=reviewers or [],
        )
        self._requests[req.id] = req
        self._notify_request_created(req)
        return req

    def review_request(
        self,
        request_id: str,
        action: ApprovalAction,
        reviewer: str,
        comment: str = "",
    ) -> bool:
        """审核例外申请"""
        req = self._requests.get(request_id)
        if not req:
            raise ValueError(f"Request not found: {request_id}")

        if req.status != ExceptionStatus.PENDING:
            raise ValueError(f"Request already {req.status.value}")

        record = ApprovalRecord(
            request_id=request_id,
            action=action,
            reviewer=reviewer,
            comment=comment,
        )
        self._approval_records.append(record)

        if action == ApprovalAction.APPROVE:
            req.status = ExceptionStatus.APPROVED
            req.approved_by = reviewer
            req.approved_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
            self._notify_request_approved(req)
        elif action == ApprovalAction.REJECT:
            req.status = ExceptionStatus.REJECTED
            req.rejection_reason = comment
            self._notify_request_rejected(req, comment)

        return req.status == ExceptionStatus.APPROVED

    def auto_approve_if_owner(self, req: ExceptionRequest) -> bool:
        """如果是代码所有者自动批准"""
        if req.created_by in self.auto_approve_owners:
            return self.review_request(req.id, ApprovalAction.APPROVE, req.created_by, "Auto-approved by owner")
        return False

    def get_request(self, request_id: str) -> ExceptionRequest | None:
        return self._requests.get(request_id)

    def list_requests(self, status: ExceptionStatus | None = None) -> list[ExceptionRequest]:
        requests = list(self._requests.values())
        if status:
            requests = [r for r in requests if r.status == status]
        return sorted(requests, key=lambda r: r.created_at, reverse=True)

    def get_approval_history(self, request_id: str) -> list[ApprovalRecord]:
        return [r for r in self._approval_records if r.request_id == request_id]

    def _notify_request_created(self, req: ExceptionRequest) -> None:
        if self.notification_webhook:
            self._send_webhook("exception_created", req.to_dict())

    def _notify_request_approved(self, req: ExceptionRequest) -> None:
        if self.notification_webhook:
            self._send_webhook("exception_approved", req.to_dict())

    def _notify_request_rejected(self, req: ExceptionRequest, reason: str) -> None:
        if self.notification_webhook:
            self._send_webhook("exception_rejected", {**req.to_dict(), "rejection_reason": reason})

    def _send_webhook(self, event: str, data: dict[str, Any]) -> None:
        """发送 Webhook 通知 (异步)"""
        webhook_url = self.notification_webhook
        if not webhook_url:
            return
        from tools.scripts.webhook_safety import is_safe_webhook_url

        if not is_safe_webhook_url(webhook_url):
            logger.warning(f"Webhook notification blocked (unsafe URL): {webhook_url}")
            return

        def _send() -> None:
            try:
                import urllib.request

                payload = json.dumps({"event": event, "data": data}).encode()
                req = urllib.request.Request(
                    webhook_url,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)  # nosec B310
            except Exception as e:
                logger.warning(f"Webhook notification failed: {e}")

        threading.Thread(target=_send, daemon=True).start()


class ExpirationManager:
    """到期管理器"""

    def __init__(
        self,
        alert_days: list[int] | None = None,
        notification_webhook: str | None = None,
        auto_revoke: bool = True,
    ):
        self.alert_days = alert_days or [30, 14, 7, 3, 1]
        self.notification_webhook = notification_webhook
        self.auto_revoke = auto_revoke
        self._alerts: dict[str, ExpirationAlert] = {}

    def _is_eligible_for_expiration_check(self, req: ExceptionRequest) -> bool:
        """判断 req 是否可处理: 已批准 + 有 expires 字段.

        V2.18 P3-5 拆分: 从 check_expirations (C=11) 抽出.
        """
        return req.status == ExceptionStatus.APPROVED and bool(req.expires)

    def _collect_expiration_alerts(self, req: ExceptionRequest, now: datetime, alerts: list[ExpirationAlert]) -> None:
        """收集 req 的过期告警, 按 alert_days 列表匹配.

        V2.18 P3-5 拆分: 从 check_expirations (C=11) 抽出.
        V2.20 P4-27 拆分: 抽 _parse_expiry_date 收口 None + ValueError 守卫,
        _emit_single_alert 收口告警构造 + 去重 + 发送.
        告警去重: 同一 req + alert_day 只触发一次 (self._alerts 索引).
        """
        exp_date = self._parse_expiry_date(req.expires)
        if exp_date is None:
            return
        days_left = (exp_date - now).days

        for alert_day in self.alert_days:
            self._emit_single_alert(req, alert_day, days_left, alerts)

    def _parse_expiry_date(self, expires: str | None) -> datetime | None:
        """解析 expires 字符串为 datetime, 失败返 None.

        Args:
            expires: ISO 格式日期字符串 (None 时直接返 None)

        Returns:
            datetime 对象或 None
        """
        if expires is None:
            return None
        try:
            return datetime.fromisoformat(expires)
        except ValueError:
            return None

    def _emit_single_alert(
        self,
        req: ExceptionRequest,
        alert_day: int,
        days_left: int,
        alerts: list[ExpirationAlert],
    ) -> None:
        """为单个 alert_day 触发告警 (含去重 + 发送).

        Args:
            req: 例外请求
            alert_day: 告警天数阈值
            days_left: 距过期天数
            alerts: 告警列表 (in-place append)
        """
        if days_left != alert_day:
            return
        alert_id = f"{req.id}-{alert_day}d"
        if alert_id in self._alerts:
            return
        expires = req.expires
        assert expires is not None  # narrow: caller (_collect) already checked
        alert = ExpirationAlert(
            request_id=req.id,
            rule_id=req.rule_id,
            paths=req.paths,
            expires_at=expires,
            days_until_expiry=days_left,
            severity=req.requested_severity,
        )
        self._alerts[alert_id] = alert
        alerts.append(alert)
        self._send_alert(alert)

    def _auto_revoke_if_expired(self, req: ExceptionRequest, now: datetime) -> None:
        """若已过期且启用 auto_revoke, 撤销 req 状态.

        V2.18 P3-5 拆分: 从 check_expirations (C=11) 抽出.
        V2.20 P4-28 拆分: 抽 _is_revokeable 收口 4 守卫 (auto_revoke/expires/已过期/APPROVED),
        主函数仅守卫 + 副作用.
        """
        if not self._is_revokeable(req, now):
            return
        req.status = ExceptionStatus.EXPIRED
        self._notify_expired(req)

    def _is_revokeable(self, req: ExceptionRequest, now: datetime) -> bool:
        """判断 req 是否应被自动撤销 (auto_revoke 开启 + 已过期 + APPROVED).

        Args:
            req: 例外请求
            now: 当前 UTC 时间

        Returns:
            True if 应撤销
        """
        if not self.auto_revoke:
            return False
        if not req.expires:
            return False
        try:
            exp_date = datetime.fromisoformat(req.expires)
        except ValueError:
            return False
        if (exp_date - now).days >= 0:
            return False
        return req.status == ExceptionStatus.APPROVED

    def check_expirations(self, requests: list[ExceptionRequest]) -> list[ExpirationAlert]:
        """检查即将到期的例外 (orchestrator).

        V2.18 P3-5 拆分: 从 C=11 / 50 行主函数拆出 3 个 helper.
        主函数仅负责: 遍历 → 过滤 → 收集告警 → 自动撤销.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        alerts: list[ExpirationAlert] = []

        for req in requests:
            if not self._is_eligible_for_expiration_check(req):
                continue
            self._collect_expiration_alerts(req, now, alerts)
            self._auto_revoke_if_expired(req, now)

        return alerts

    def get_pending_alerts(self) -> list[ExpirationAlert]:
        return [a for a in self._alerts.values() if not a.notified]

    def mark_alert_notified(self, alert: ExpirationAlert) -> None:
        alert.notified = True
        alert.notified_at = datetime.now(timezone.utc).replace(tzinfo=None).isoformat()
        self._send_alert(alert)  # 重发确认

    def _send_alert(self, alert: ExpirationAlert) -> None:
        if self.notification_webhook:
            from tools.scripts.webhook_safety import is_safe_webhook_url

            if not is_safe_webhook_url(self.notification_webhook):
                logger.warning(f"Expiration alert webhook blocked (unsafe URL): {self.notification_webhook}")
                return
            try:
                import urllib.request

                payload = json.dumps(
                    {
                        "event": "exception_expiring",
                        "data": asdict(alert),
                    }
                ).encode()
                req = urllib.request.Request(
                    self.notification_webhook,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(req, timeout=5)  # nosec B310
            except Exception as e:
                logger.warning(f"Expiration alert webhook failed: {e}")

    def _notify_expired(self, req: ExceptionRequest) -> None:
        if self.notification_webhook:
            from tools.scripts.webhook_safety import is_safe_webhook_url

            if not is_safe_webhook_url(self.notification_webhook):
                logger.warning(f"Expiration notification blocked (unsafe URL): {self.notification_webhook}")
                return
            try:
                import urllib.request

                payload = json.dumps(
                    {
                        "event": "exception_expired",
                        "data": req.to_dict(),
                    }
                ).encode()
                http_req = urllib.request.Request(
                    self.notification_webhook,
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                urllib.request.urlopen(http_req, timeout=5)  # nosec B310
            except Exception as e:
                logger.warning(f"Expiration notification failed: {e}")


class GitOpsSync:
    """GitOps 同步器 - 双向同步例外规则到 Git 仓库"""

    def __init__(
        self,
        repo_path: Path,
        exceptions_file: str = ".jcode/exceptions.yaml",
        branch: str = "main",
        remote: str = "origin",
        auto_commit: bool = True,
        auto_push: bool = False,
    ):
        self.repo_path = repo_path
        self.exceptions_file = repo_path / exceptions_file
        self.branch = branch
        self.remote = remote
        self.auto_commit = auto_commit
        self.auto_push = auto_push

    def sync_to_git(self, requests: list[ExceptionRequest]) -> bool:
        """将例外同步到 Git 仓库"""
        try:
            # 确保目录存在
            self.exceptions_file.parent.mkdir(parents=True, exist_ok=True)

            # 生成 YAML 内容
            import yaml

            data: dict[str, Any] = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "exceptions": [
                    {**req.to_dict(), "status": req.status.value}
                    for req in requests
                    if req.status == ExceptionStatus.APPROVED
                ],
            }

            # 写入文件
            with open(self.exceptions_file, "w") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)

            # Git 提交
            if self.auto_commit:
                exception_count = len(data["exceptions"])
                self._git_commit(f"chore: sync exceptions ({exception_count} rules)")

            return True
        except Exception as e:
            logger.error(f"GitOps sync to git failed: {e}")
            return False

    def sync_from_git(self) -> list[ExceptionRequest]:
        """从 Git 仓库同步例外.

        V2.20 P4-15 拆分: 抽 _load_git_yaml_exceptions 收口 yaml 读取 + 遍历,
        _parse_git_exception 收口 status 转换 + from_dict + 强制 APPROVED.
        主函数仅负责 try/except 包裹.
        """
        try:
            return self._load_git_yaml_exceptions()
        except Exception as e:
            logger.error(f"GitOps sync from git failed: {e}")
            return []

    def _load_git_yaml_exceptions(self) -> list[ExceptionRequest]:
        """从 Git YAML 文件读取 exceptions, 解析为 Request 列表."""
        if not self.exceptions_file.exists():
            return []
        import yaml

        with open(self.exceptions_file) as f:
            data = yaml.safe_load(f)

        if not data or "exceptions" not in data:
            return []

        return [self._parse_git_exception(exc) for exc in data["exceptions"]]

    def _parse_git_exception(self, exc_data: dict[str, object]) -> ExceptionRequest:
        """解析单条 Git exception (status 转换 + 强制 APPROVED + from_dict).

        Args:
            exc_data: exception dict

        Returns:
            ExceptionRequest 对象 (status=APPROVED)
        """
        if "status" in exc_data and isinstance(exc_data["status"], str):
            exc_data["status"] = ExceptionStatus(exc_data["status"])
        req = ExceptionRequest.from_dict(exc_data)
        req.status = ExceptionStatus.APPROVED  # Git 中的默认为已批准
        return req

    def pull_latest(self) -> bool:
        """拉取最新代码"""
        try:
            subprocess.run(
                ["git", "pull", self.remote, self.branch],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            return True
        except subprocess.CalledProcessError as e:
            logger.error(f"Git pull failed: {e.stderr.decode()}")
            return False

    def _git_commit(self, message: str) -> None:
        """Git 提交"""
        try:
            subprocess.run(
                ["git", "add", str(self.exceptions_file.relative_to(self.repo_path))],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            subprocess.run(
                ["git", "commit", "-m", message],
                cwd=self.repo_path,
                check=True,
                capture_output=True,
            )
            if self.auto_push:
                subprocess.run(
                    ["git", "push", self.remote, self.branch],
                    cwd=self.repo_path,
                    check=True,
                    capture_output=True,
                )
        except subprocess.CalledProcessError as e:
            logger.error(f"Git commit failed: {e.stderr.decode()}")


class EnhancedExceptionManager:
    """增强版例外管理器 - 整合审批流、到期管理、GitOps"""

    def __init__(
        self,
        config_path: Path | None = None,
        gitops: GitOpsSync | None = None,
        approval_workflow: ApprovalWorkflow | None = None,
        expiration_manager: ExpirationManager | None = None,
    ):
        self.config_path = config_path or Path(".jcode/governance.yaml")
        self.gitops = gitops
        self.approval = approval_workflow or ApprovalWorkflow()
        self.expiration = expiration_manager or ExpirationManager()
        self._requests: dict[str, ExceptionRequest] = {}

        # Share requests with approval workflow
        self.approval._requests = self._requests

        # 从配置加载
        self._load_from_config()

        # 从 GitOps 同步
        if self.gitops:
            self._sync_from_gitops()

    def _load_from_config(self) -> None:
        """从配置文件加载例外.

        V2.20 P4-13 拆分: 抽 _load_yaml_exceptions 收口 yaml 读取 + 遍历,
        _parse_exception_entry 收口 status 转换 + from_dict.
        主函数仅负责 try/except 包裹.
        """
        try:
            self._load_yaml_exceptions()
        except Exception as e:
            logger.warning(f"Failed to load exceptions from config: {e}")

    def _load_yaml_exceptions(self) -> None:
        """从 YAML 配置文件读取 exceptions 列表, 解析并存储.

        V2.20 P4-32 拆分: 抽 _read_exceptions_yaml 收口 yaml 读取 + 守卫,
        _import_exceptions_dict 收口遍历 + 存储.
        主函数仅 2 段委托.
        """
        data = self._read_exceptions_yaml()
        if data is None:
            return
        entries = data.get("exceptions", [])
        if isinstance(entries, list):
            self._import_exceptions_dict(entries)

    def _read_exceptions_yaml(self) -> dict[str, object] | None:
        """读取 YAML 配置文件并解析为 dict (None if 文件不存在或解析失败).

        Returns:
            解析后的 dict 或 None
        """
        if not self.config_path.exists():
            return None
        import yaml

        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        if not data or "exceptions" not in data:
            return None
        return data

    def _import_exceptions_dict(self, entries: list[dict[str, object]]) -> None:
        """导入 exceptions 列表, 解析并存储到 self._requests.

        Args:
            entries: exception entry 列表
        """
        for exc in entries:
            req = self._parse_exception_entry(exc)
            if req is not None:
                self._requests[req.id] = req

    def _parse_exception_entry(self, exc: dict[str, object]) -> ExceptionRequest | None:
        """解析单条 exception entry (status 转换 + from_dict).

        Args:
            exc: exception dict

        Returns:
            ExceptionRequest 对象, 解析失败返 None
        """
        if "status" in exc and isinstance(exc["status"], str):
            exc["status"] = ExceptionStatus(exc["status"])
        return ExceptionRequest.from_dict(exc)

    def _sync_from_gitops(self) -> None:
        """从 GitOps 同步"""
        if not self.gitops:
            return
        try:
            git_requests = self.gitops.sync_from_git()
            for req in git_requests:
                if req.id not in self._requests:
                    self._requests[req.id] = req
        except Exception as e:
            logger.warning(f"GitOps sync failed: {e}")

    def request_exception(
        self,
        rule_id: str,
        paths: list[str],
        reason: str,
        severity: str,
        requested_severity: str,
        expires: str | None,
        created_by: str,
        reviewers: list[str] | None = None,
    ) -> ExceptionRequest:
        """申请例外"""
        req = self.approval.create_request(
            rule_id=rule_id,
            paths=paths,
            reason=reason,
            severity=severity,
            requested_severity=requested_severity,
            expires=expires,
            created_by=created_by,
            reviewers=reviewers,
        )
        self._requests[req.id] = req

        # 自动批准检查
        self.approval.auto_approve_if_owner(req)

        # 保存配置
        self.save_config()

        # 同步到 GitOps
        self._sync_to_gitops()

        return req

    def approve_exception(self, request_id: str, reviewer: str, comment: str = "") -> bool:
        """批准例外"""
        result = self.approval.review_request(request_id, ApprovalAction.APPROVE, reviewer, comment)
        if result:
            self.save_config()
            self._sync_to_gitops()
        return result

    def reject_exception(self, request_id: str, reviewer: str, comment: str = "") -> bool:
        """拒绝例外"""
        result = self.approval.review_request(request_id, ApprovalAction.REJECT, reviewer, comment)
        if result:
            self.save_config()
            self._sync_to_gitops()
        return not result  # 返回 True 表示操作成功（拒绝了）

    def revoke_exception(self, request_id: str) -> bool:
        """撤销例外"""
        req = self._requests.get(request_id)
        if not req:
            return False
        req.status = ExceptionStatus.REVOKED
        self.save_config()
        self._sync_to_gitops()
        return True

    def check_expirations(self) -> list[ExpirationAlert]:
        """检查到期情况"""
        return self.expiration.check_expirations(list(self._requests.values()))

    def get_active_exceptions(self) -> list[ExceptionRequest]:
        """获取当前有效的例外.

        V2.20 P4-16 拆分: 抽 _is_active_request 收口 APPROVED 守卫 + 过期检查,
        主函数仅负责遍历 + 收集.
        """
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        active: list[ExceptionRequest] = []
        for req in self._requests.values():
            if self._is_active_request(req, now):
                active.append(req)
        return active

    def _is_active_request(self, req: ExceptionRequest, now: datetime) -> bool:
        """判断 req 是否当前有效 (APPROVED + 未过期).

        Args:
            req: 例外请求
            now: 当前 UTC 时间

        Returns:
            True if APPROVED 且未过期, 否则 False
        """
        if req.status != ExceptionStatus.APPROVED:
            return False
        if not req.expires:
            return True
        try:
            if datetime.fromisoformat(req.expires) < now:
                req.status = ExceptionStatus.EXPIRED
                return False
        except ValueError:
            pass
        return True

    def get_all_requests(self) -> list[ExceptionRequest]:
        return list(self._requests.values())

    def get_request(self, request_id: str) -> ExceptionRequest | None:
        return self._requests.get(request_id)

    def save_config(self) -> None:
        """保存配置文件"""
        try:
            import yaml

            data = {
                "version": 1,
                "updated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
                "exceptions": [{**req.to_dict(), "status": req.status.value} for req in self._requests.values()],
            }
            self.config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.config_path, "w") as f:
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
        except Exception as e:
            logger.error(f"Failed to save config: {e}")

    def _sync_to_gitops(self) -> None:
        if self.gitops:
            self.gitops.sync_to_git(list(self._requests.values()))

    def generate_audit_report(self) -> dict[str, Any]:
        """生成审计报告.

        V2.20 P4-14 拆分: 抽 _build_status_breakdown 收口 by_status 统计,
        _build_requests_summary 收口 requests + approval_history 列表.
        主函数仅负责 metadata + 3 段委托.
        """
        return {
            "generated_at": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(),
            "total_requests": len(self._requests),
            "by_status": self._build_status_breakdown(),
            "pending_review": self._count_pending(),
            "expiring_soon": len(self.expiration.get_pending_alerts()),
            "requests": [r.to_dict() for r in self._requests.values()],
            "approval_history": [r.to_dict() for r in self.approval._approval_records],
        }

    def _build_status_breakdown(self) -> dict[str, int]:
        """按 status 分组统计 request 数量.

        Returns:
            {status_value: count}
        """
        return {
            status.value: sum(1 for r in self._requests.values() if r.status == status) for status in ExceptionStatus
        }

    def _count_pending(self) -> int:
        """统计 PENDING 状态 request 数量.

        Returns:
            PENDING 状态计数
        """
        return sum(1 for r in self._requests.values() if r.status == ExceptionStatus.PENDING)


def create_enhanced_manager(
    config_path: Path | None = None,
    repo_path: Path | None = None,
    required_approvals: int = 1,
    auto_approve_owners: list[str] | None = None,
    notification_webhook: str | None = None,
    alert_days: list[int] | None = None,
) -> EnhancedExceptionManager:
    """工厂函数：创建增强版例外管理器"""
    gitops = None
    if repo_path:
        gitops = GitOpsSync(repo_path=repo_path)

    approval = ApprovalWorkflow(
        required_approvals=required_approvals,
        auto_approve_owners=auto_approve_owners,
        notification_webhook=notification_webhook,
    )

    expiration = ExpirationManager(
        alert_days=alert_days,
        notification_webhook=notification_webhook,
    )

    return EnhancedExceptionManager(
        config_path=config_path,
        gitops=gitops,
        approval_workflow=approval,
        expiration_manager=expiration,
    )

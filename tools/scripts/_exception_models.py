"""Exception Manager 数据模型层。

数据类 (ExceptionStatus / ApprovalAction / ExceptionRequest / ApprovalRecord /
ExpirationAlert) 从 exception_manager.py 拆出 (facade re-export 模式)。
依赖方向: 工作流类 → 本模块, 本模块不 import facade。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any


class ExceptionStatus(StrEnum):
    """例外状态"""

    PENDING = "pending"  # 待审批
    APPROVED = "approved"  # 已批准
    REJECTED = "rejected"  # 已拒绝
    EXPIRED = "expired"  # 已过期
    REVOKED = "revoked"  # 已撤销


class ApprovalAction(StrEnum):
    """审批动作"""

    APPROVE = "approve"
    REJECT = "reject"
    REQUEST_CHANGES = "request_changes"


@dataclass
class ExceptionRequest:
    """例外申请"""

    id: str
    rule_id: str
    paths: list[str]
    reason: str
    severity: str  # 原始严重性
    requested_severity: str  # 请求降级后的严重性
    expires: str | None
    created_by: str
    created_at: str
    status: ExceptionStatus = ExceptionStatus.PENDING
    approved_by: str | None = None
    approved_at: str | None = None
    rejection_reason: str | None = None
    reviewers: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ExceptionRequest:
        # Convert status string to enum
        if "status" in data and isinstance(data["status"], str):
            data["status"] = ExceptionStatus(data["status"])
        return cls(**data)


@dataclass
class ApprovalRecord:
    """审批记录"""

    request_id: str
    action: ApprovalAction
    reviewer: str
    comment: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).replace(tzinfo=None).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ExpirationAlert:
    """到期告警"""

    request_id: str
    rule_id: str
    paths: list[str]
    expires_at: str
    days_until_expiry: int
    severity: str
    notified: bool = False
    notified_at: str | None = None

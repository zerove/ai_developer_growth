"""ADG CLI notify command - 通知分发。

统一复用 tools.chat_integration 的三平台 Notifier 实现，
避免与库层双轨维护。CLI 层只做平台选择与错误提示。
"""

from __future__ import annotations

import sys

from tools.scripts.adg_cli.core import Issue


def _send_slack_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to Slack (via chat_integration)."""
    from tools.chat_integration import SlackNotifier

    ok = SlackNotifier(webhook_url).send_report(issues, language, project)
    if not ok:
        print("Warning: Slack notification failed", file=sys.stderr)
    return ok


def _send_dingtalk_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to DingTalk (via chat_integration)."""
    from tools.chat_integration import DingTalkNotifier

    ok = DingTalkNotifier(webhook_url).send_report(issues, language, project)
    if not ok:
        print("Warning: DingTalk notification failed", file=sys.stderr)
    return ok


def _send_feishu_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to Feishu (via chat_integration)."""
    from tools.chat_integration import FeishuNotifier

    ok = FeishuNotifier(webhook_url).send_report(issues, language, project)
    if not ok:
        print("Warning: Feishu notification failed", file=sys.stderr)
    return ok

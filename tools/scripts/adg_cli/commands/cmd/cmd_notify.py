from __future__ import annotations

import argparse
import sys
from typing import Any

from ._shared import (
    SKIP_EXTENSIONS,
    Issue,
    Path,
    _detect_language_from_file,
    _send_dingtalk_notification,
    _send_slack_notification,
    check_file,
    detect_language,
    load_rules_for_language,
)


def cmd_notify(args: argparse.Namespace) -> int:
    """Send governance report via webhook (V2.21 P5-36 拆分: 抽 _collect_issues + _dispatch_webhook)."""
    target = Path(args.path).resolve()

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules and check
    rules = load_rules_for_language(language)
    all_issues = _collect_issues(target, rules)

    # Send notification
    return _dispatch_webhook(args.webhook, all_issues, language, getattr(args, "project", "."))


def _collect_issues(target: Path, rules: dict[str, Any]) -> list[Issue]:
    """单文件 or 目录递归, 收集 issues (模块级 helper).

    Args:
        target: 文件或目录路径
        rules: 规则字典

    Returns:
        全部 issue 列表
    """
    if target.is_file():
        return check_file(target, rules)
    all_issues: list[Issue] = []
    for fp in target.rglob("*"):
        if fp.is_file() and fp.suffix not in SKIP_EXTENSIONS:
            if _detect_language_from_file(fp):
                all_issues.extend(check_file(fp, rules))
    return all_issues


def _dispatch_webhook(webhook_url: str, all_issues: list[Issue], language: str, project_name: str) -> int:
    """分派 webhook (slack/dingtalk, 模块级 helper).

    Args:
        webhook_url: webhook URL (slack:// or dingtalk://)
        all_issues: issue 列表
        language: 检测到的语言
        project_name: 项目名

    Returns:
        exit code (0 成功, 1 失败)
    """
    if webhook_url.startswith("slack://"):
        url = webhook_url.replace("slack://", "https://hooks.slack.com/services/")
        success = _send_slack_notification(url, all_issues, language, project_name)
    elif webhook_url.startswith("dingtalk://"):
        url = webhook_url.replace("dingtalk://", "https://oapi.dingtalk.com/robot/send?access_token=")
        success = _send_dingtalk_notification(url, all_issues, language, project_name)
    else:
        print(
            "Error: Unknown webhook scheme. Use slack:// or dingtalk://",
            file=sys.stderr,
        )
        return 1

    if success:
        print("✅ Notification sent successfully")
        return 0
    print("", file=sys.stderr)
    return 1

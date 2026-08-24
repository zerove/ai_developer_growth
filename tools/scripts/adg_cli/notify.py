from __future__ import annotations

import json
import sys

from tools.scripts.adg_cli.core import Issue


def _send_slack_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to Slack."""
    import time
    import urllib.request

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    color = "#36a64f" if error_count == 0 else "#ff0000"

    payload = {
        "attachments": [
            {
                "color": color,
                "title": f"ADG Governance Report - {project}",
                "text": f"Language: {language}\nErrors: {error_count} | Warnings: {warning_count} | Info: {info_count}",
                "fields": [
                    {
                        "title": "Status",
                        "value": "✅ Passed" if error_count == 0 else "❌ Failed",
                        "short": True,
                    },
                    {"title": "Total Issues", "value": str(len(issues)), "short": True},
                ],
                "footer": "ADG CLI",
                "ts": int(time.time()),
            }
        ],
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)  # nosec - webhook URL from config
        return True
    except Exception as e:
        print(f"Warning: Slack notification failed: {e}", file=sys.stderr)
        return False


def _send_dingtalk_notification(webhook_url: str, issues: list[Issue], language: str, project: str) -> bool:
    """Send issues notification to DingTalk."""
    import urllib.request

    error_count = sum(1 for i in issues if i.severity == "error")
    warning_count = sum(1 for i in issues if i.severity == "warning")
    info_count = sum(1 for i in issues if i.severity == "info")

    status = "✅ 通过" if error_count == 0 else "❌ 失败"

    payload = {
        "msgtype": "markdown",
        "markdown": {
            "title": f"ADG 治理报告 - {project}",
            "text": f"## ADG 治理报告\n\n"
            f"**项目**: {project}\n"
            f"**语言**: {language}\n"
            f"**状态**: {status}\n\n"
            f"---\n\n"
            f"**错误**: {error_count}\n"
            f"**警告**: {warning_count}\n"
            f"**信息**: {info_count}\n"
            f"**总计**: {len(issues)}\n",
        },
    }

    try:
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            webhook_url,
            data=data,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)  # nosec - webhook URL from config
        return True
    except Exception as e:
        print(f"Warning: DingTalk notification failed: {e}", file=sys.stderr)
        return False

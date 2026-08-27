from __future__ import annotations

import argparse
import sys

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
    """Send governance report via webhook."""
    target = Path(args.path).resolve()

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    # Load rules and check
    rules = load_rules_for_language(language)
    all_issues: list[Issue] = []

    if target.is_file():
        all_issues = check_file(target, rules)
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and fp.suffix not in SKIP_EXTENSIONS:
                if _detect_language_from_file(fp):
                    all_issues.extend(check_file(fp, rules))

    # Send notification
    webhook_url = args.webhook
    project_name = getattr(args, "project", ".")

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
    else:
        print("", file=sys.stderr)
        return 1

    return 0

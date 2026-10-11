from __future__ import annotations

import argparse
import sys

from ._shared import (
    Any,
    Issue,
    Path,
    _attach_docs_to_issues,
    _check_files_parallel,
    _check_python_complexity,
    _collect_check_files,
    _format_human,
    _format_json,
    _format_sarif,
    _make_check_error_issue,
    _record_trend,
    _send_dingtalk_notification,
    _send_slack_notification,
    check_file,
    load_framework_rules,
    load_project_config,
    load_rules_for_language,
)


def _handle_post_check_actions(all_issues: list[Issue], target: Path, language: str, args: argparse.Namespace) -> None:
    """Handle post-check actions: docs, trend recording, notifications."""
    # Attach knowledge base docs if requested
    if getattr(args, "with_docs", False):
        _attach_docs_to_issues(all_issues)

    # Record trend if requested
    if getattr(args, "trend", False):
        _record_trend(target if target.is_dir() else target.parent, all_issues, language)

    # Send notification if requested
    notify_url = getattr(args, "notify", None)
    if notify_url:
        project_name = getattr(args, "project", ".")
        if notify_url.startswith("slack://"):
            webhook_url = notify_url.replace("slack://", "https://hooks.slack.com/services/")
            _send_slack_notification(webhook_url, all_issues, language, project_name)
        elif notify_url.startswith("dingtalk://"):
            webhook_url = notify_url.replace("dingtalk://", "https://oapi.dingtalk.com/robot/send?access_token=")
            _send_dingtalk_notification(webhook_url, all_issues, language, project_name)


def _load_and_merge_rules(language: str, framework: str | None, project_config: dict[str, Any]) -> dict[str, Any]:
    """Load rules and merge with framework and custom rules."""
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    # Add custom rules from project config
    custom_rules = project_config.get("custom_rules", [])
    if custom_rules:
        rules["anti_patterns"].extend(custom_rules)

    # Apply severity overrides
    severity_overrides = project_config.get("severity_overrides", {})
    for rule in rules["anti_patterns"]:
        if rule["id"] in severity_overrides:
            rule["severity"] = severity_overrides[rule["id"]]

    return rules


def _output_results(
    all_issues: list[Issue],
    language: str,
    framework: str | None,
    files_count: int,
    args: argparse.Namespace,
) -> None:
    """Output check results in requested format."""
    sarif = getattr(args, "sarif", False)
    if sarif:
        print(_format_sarif(all_issues, language, framework))
    elif args.json:
        print(_format_json(all_issues, language, framework, files_count))
    else:
        print(_format_human(all_issues, language, framework, files_count))


def _prepare_check_config(
    target: Path, args: argparse.Namespace, project_config: dict[str, Any]
) -> tuple[str, str | None, list[Path]]:
    """Prepare configuration for check command."""
    files, detected = _collect_check_files(target, args, project_config)

    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, "framework", None) or detected.get("framework")

    # Use framework hint from config if not detected
    if not framework:
        framework = project_config.get("framework_hints", {}).get(language)

    return language, framework, files


def _run_checks(files: list[Path], rules: dict[str, Any], severity: str, jobs: int) -> list[Issue]:
    """Run checks on files, either parallel or sequential.

    单个文件检查失败会变成 `check-error` error 级 Issue（ADR-078），
    保证并行与串行对同一输入给出相同的退出码。
    """
    if jobs > 1 and len(files) > 1:
        return _check_files_parallel(files, rules, severity, jobs)
    else:
        all_issues: list[Issue] = []
        for fp in files:
            try:
                all_issues.extend(check_file(fp, rules, severity))
            except Exception as exc:  # noqa: BLE001 - 崩溃必须留痕, 不得静默跳过
                all_issues.append(_make_check_error_issue(fp, exc))
        return all_issues


def _run_complexity_checks(files: list[Path], severity: str, max_cc: int) -> list[Issue]:
    """Run cyclomatic complexity gate on Python files (--complexity)."""
    all_issues: list[Issue] = []
    for fp in files:
        if fp.suffix != ".py":
            continue
        try:
            content = fp.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        all_issues.extend(_check_python_complexity(fp, content.split("\n"), severity, max_cc))
    return all_issues


def cmd_check(args: argparse.Namespace) -> int:
    """Check code against rules."""
    target = Path(args.path).resolve()

    # Load project configuration
    project_config = load_project_config(target if target.is_dir() else target.parent)

    language, framework, files = _prepare_check_config(target, args, project_config)

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return 1

    if not files:
        return 0

    # Load rules
    rules = _load_and_merge_rules(language, framework, project_config)

    # Check files
    jobs = getattr(args, "jobs", 1)
    all_issues = _run_checks(files, rules, args.severity, jobs)

    # Cyclomatic complexity gate (--complexity)
    if getattr(args, "complexity", False):
        max_cc = getattr(args, "max_cc", 10)
        all_issues.extend(_run_complexity_checks(files, args.severity, max_cc))

    # Output
    _output_results(all_issues, language, framework, len(files), args)

    # Handle post-check actions
    _handle_post_check_actions(all_issues, target, language, args)

    has_errors = any(i.severity == "error" for i in all_issues)
    return 1 if has_errors else 0

from __future__ import annotations

import argparse
import sys

from tools.scripts.app_config import get_setting

from ._shared import (
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

_DEFAULT_JOBS = 4


def _resolve_jobs(args: argparse.Namespace) -> int:
    """解析并行度：显式 --jobs > [tool.adg].jobs > 4。

    - 显式 `--jobs N`（N > 0）优先，用户指定即生效；
    - 未指定或 <=0 时读 `[tool.adg].jobs`（`app_config.get_setting`）；
    - 配置非法（非数字、<=0）回退默认 4，不让脏配置阻断检查。
    """
    explicit = getattr(args, "jobs", None)
    if explicit is not None:
        try:
            parsed_explicit = int(explicit)
        except (TypeError, ValueError):
            parsed_explicit = 0
        if parsed_explicit > 0:
            return parsed_explicit

    try:
        configured = int(str(get_setting("jobs", default=_DEFAULT_JOBS)).strip())
    except (TypeError, ValueError):
        return _DEFAULT_JOBS
    return configured if configured > 0 else _DEFAULT_JOBS


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
        else:
            print("Warning: Unsupported --notify scheme; use slack:// or dingtalk://", file=sys.stderr)


# severity_overrides 的禁用值 (大小写不敏感): 命中即 enabled=False。
# 语义契约: 禁用必须走 enabled, 而非把 severity 设成未知值 ——
# 未知 severity 在 _severity_rank 中只映射为 rank-3, 规则仍会执行与展示。
_RULE_DISABLE_VALUES = {"off", "ignore", "disabled"}


def _normalize_custom_rule(rule: object, language: str) -> dict[str, object] | None:
    """校验并净化单条 custom rule；无效或不适用时返回 None。"""
    if not isinstance(rule, dict):
        return None
    raw_id = rule.get("id")
    rule_id = raw_id.strip() if isinstance(raw_id, str) else ""
    if not rule_id or any(ch.isspace() for ch in rule_id):
        print(
            f"Warning: Skipping custom rule with invalid id ({raw_id!r}); id must be non-empty without whitespace",
            file=sys.stderr,
        )
        return None
    rule_lang = str(rule.get("language") or "").strip().lower()
    if rule_lang and rule_lang != language.strip().lower():
        return None
    # ReDoS/危险 pattern 防护：与 rule_loader._drop_dangerous_patterns 同策略
    from tools.scripts.rules_engine.regex_cache import guard_pattern

    pattern = rule.get("pattern")
    exclude_pattern = rule.get("exclude_pattern")
    if isinstance(pattern, str) and guard_pattern(pattern, f"adg_cli/custom_rules#{rule_id}"):
        return None
    normalized: dict[str, object] = rule
    if isinstance(exclude_pattern, str) and guard_pattern(exclude_pattern, f"adg_cli/custom_rules#{rule_id}#exclude"):
        normalized = {**rule}
        normalized.pop("exclude_pattern", None)
    return normalized


def _apply_severity_overrides(rules: dict[str, object], project_config: dict[str, object]) -> None:
    """severity_overrides: 普通值改 severity; 禁用值置 enabled=False。"""
    severity_overrides = project_config.get("severity_overrides", {})
    if not isinstance(severity_overrides, dict):
        return
    anti_patterns = rules.get("anti_patterns", [])
    if not isinstance(anti_patterns, list):
        return
    for rule in anti_patterns:
        if not isinstance(rule, dict):
            continue
        override = severity_overrides.get(rule.get("id"))
        if override is None:
            continue
        # YAML 1.1 把裸 off/on/yes/no 解析成 bool: PyYAML 路径下
        # `severity_overrides: {x: off}` 到达此处是 False 而非字符串 "off",
        # 必须同时按 False 处理, 否则 else 分支会把 severity 设成 bool
        if override is False or (isinstance(override, str) and override.strip().lower() in _RULE_DISABLE_VALUES):
            rule["enabled"] = False
        else:
            rule["severity"] = override


def _load_and_merge_rules(language: str, framework: str | None, project_config: dict[str, object]) -> dict[str, object]:
    """Load rules and merge with framework and custom rules."""
    rules: dict[str, object] = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        anti_patterns = rules.get("anti_patterns")
        if isinstance(anti_patterns, list):
            anti_patterns.extend(fw_rules.get("anti_patterns", []))

    # 自定义规则 language 字段语义 (契约):
    #   无 language / 空 → 适用所有语言; 有值 → 必须与当前扫描语言一致
    custom_rules = project_config.get("custom_rules", [])
    if isinstance(custom_rules, list):
        anti_patterns = rules.get("anti_patterns")
        if isinstance(anti_patterns, list):
            for rule in custom_rules:
                normalized = _normalize_custom_rule(rule, language)
                if normalized is not None:
                    anti_patterns.append(normalized)

    _apply_severity_overrides(rules, project_config)
    return rules


def _output_results(
    all_issues: list[Issue],
    language: str,
    framework: str | None,
    files_count: int,
    jobs: int,
    args: argparse.Namespace,
) -> None:
    """Output check results in requested format."""
    sarif = getattr(args, "sarif", False)
    if sarif:
        print(_format_sarif(all_issues, language, framework))
    elif args.json:
        check_errors = sum(1 for i in all_issues if getattr(i, "rule_id", "") in ("check-error", "file-check-error"))
        meta = {
            "files_checked": files_count,
            "jobs": jobs,
            "check_errors": check_errors,
            "failed_files": check_errors,  # ADR-078: check-error 表示文件检查失败/未可信检查
            # adg check 使用 adg_cli.check 路径（非 rules_engine checker cache）；无缓存能力时显式标记
            "cache_supported": False,
            "cache_engine": None,
            "cache_degraded": None,
            "cache_hits": None,
            "cache_misses": None,
            "cache_hit_rate": None,
            "cache_reason": "adg_cli_path_no_rules_engine_cache",
        }
        print(_format_json(all_issues, language, framework, files_count, meta=meta))
    else:
        print(_format_human(all_issues, language, framework, files_count))


def _prepare_check_config(
    target: Path, args: argparse.Namespace, project_config: dict[str, object]
) -> tuple[str, str | None, list[Path]]:
    """Prepare configuration for check command."""
    files, detected = _collect_check_files(target, args, project_config)

    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, "framework", None) or detected.get("framework")

    # Use framework hint from config if not detected
    if not framework:
        hints = project_config.get("framework_hints", {})
        if isinstance(hints, dict):
            framework = hints.get(language)

    return language, framework, files


def _run_checks(files: list[Path], rules: dict[str, object], severity: str, jobs: int) -> list[Issue]:
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

    # Check files（P-01: 默认按 [tool.adg].jobs 并行，而非硬编码串行）
    jobs = _resolve_jobs(args)
    all_issues = _run_checks(files, rules, args.severity, jobs)

    # Cyclomatic complexity gate (--complexity)
    if getattr(args, "complexity", False):
        max_cc = getattr(args, "max_cc", 10)
        all_issues.extend(_run_complexity_checks(files, args.severity, max_cc))

    # Output
    _output_results(all_issues, language, framework, len(files), jobs, args)

    # Handle post-check actions
    _handle_post_check_actions(all_issues, target, language, args)

    has_errors = any(i.severity == "error" for i in all_issues)
    return 1 if has_errors else 0

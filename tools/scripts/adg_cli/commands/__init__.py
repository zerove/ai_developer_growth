from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from tools.scripts.adg_cli.check import _check_files_parallel, _collect_check_files, check_directory, check_file
from tools.scripts.adg_cli.core import (
    _DEFAULT_PRE_COMMIT_HOOK,
    _DEFAULT_PRE_PUSH_HOOK,
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    Issue,
    _attach_docs_to_issues,
    load_project_config,
)
from tools.scripts.adg_cli.detect import _detect_language_from_file, detect_language
from tools.scripts.adg_cli.fix import fix_directory, fix_file
from tools.scripts.adg_cli.format import (
    _RESET,
    _SEVERITY_COLORS,
    _count_issues,
    _format_human,
    _format_json,
    _format_sarif,
    _print_report_text,
)
from tools.scripts.adg_cli.notify import _send_dingtalk_notification, _send_slack_notification
from tools.scripts.adg_cli.rule_author import _RULE_TEMPLATE, _create_rule_interactive, _test_rule, _validate_rule
from tools.scripts.adg_cli.rules import load_framework_rules, load_rules_for_language
from tools.scripts.adg_cli.trend import (
    _TREND_DATA_FILE,
    _format_trend_report,
    _load_trend_data,
    _record_trend,
)


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


def _run_checks(files: list[Path], rules: dict[str, Any], severity: str, jobs: int) -> list[Issue]:
    """Run checks on files, either parallel or sequential."""
    if jobs > 1 and len(files) > 1:
        return _check_files_parallel(files, rules, severity, jobs)
    else:
        all_issues: list[Issue] = []
        for fp in files:
            all_issues.extend(check_file(fp, rules, severity))
        return all_issues


def _output_results(
    all_issues: list[Issue], language: str, framework: str | None, files_count: int, args: argparse.Namespace
) -> None:
    """Output check results in requested format."""
    sarif = getattr(args, "sarif", False)
    if sarif:
        print(_format_sarif(all_issues, language, framework))
    elif args.json:
        print(_format_json(all_issues, language, framework, files_count))
    else:
        print(_format_human(all_issues, language, framework, files_count))


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

    # Output
    _output_results(all_issues, language, framework, len(files), args)

    # Handle post-check actions
    _handle_post_check_actions(all_issues, target, language, args)

    has_errors = any(i.severity == "error" for i in all_issues)
    return 1 if has_errors else 0


def _print_fix_header(target: Path, language: str | None) -> None:
    """Print the fix command header."""
    print(f"\n\033[1m\033[36m{'=' * 60}\033[0m")
    print("\033[1m\033[36m  ADG 🔧 Auto-fix\033[0m")
    print(f"\033[1m\033[36m{'=' * 60}\033[0m\n")

    print(f"\033[1mTarget:\033[0m {target}")
    if language:
        print(f"\033[1mLanguage:\033[0m {language}")
    print()


def _print_fix_results(stats: dict[str, Any]) -> None:
    """Print fix results."""
    print("\033[1mResults:\033[0m")
    print(f"  Files modified: {stats['files']}")
    print(f"  Rules applied:  {stats['fixed']}")
    print(f"  Rules skipped:  {stats['skipped']}")
    print(f"  Errors:         {stats['errors']}")
    print()

    if stats["fixed"] > 0:
        print("\033[32m\033[1m✅ Fixes applied successfully\033[0m")
    elif stats["errors"] > 0:
        print("\033[31m\033[1m❌ Some errors occurred\033[0m")
    else:
        print("\033[33m\033[1m⚠️  No automatic fixes available\033[0m")
        print("   Some issues require manual fixes.")


def _run_fix(target: Path, language: str | None) -> dict[str, Any]:
    """Run fix on target and return stats."""
    if target.is_file():
        stats = fix_file(target)
        stats["files"] = 1 if stats["fixed"] > 0 else 0
    else:
        stats = fix_directory(target, language)
    return stats


def cmd_fix(args: argparse.Namespace) -> int:
    """Apply automatic fixes to code files."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language")

    if args.json:
        stats = _run_fix(target, language)
        print(json.dumps(stats, indent=2))
    else:
        _print_fix_header(target, language)
        stats = _run_fix(target, language)
        _print_fix_results(stats)

    return 0 if stats["errors"] == 0 else 1


def cmd_rule(args: argparse.Namespace) -> int:
    """Handle rule authoring commands."""
    rule_cmd = getattr(args, "rule_command", None)

    if rule_cmd == "create":
        return _cmd_rule_create(args)
    elif rule_cmd == "test":
        return _cmd_rule_test(args)
    elif rule_cmd == "validate":
        return _cmd_rule_validate(args)
    else:
        print("Usage: adg rule {create|test|validate}", file=sys.stderr)
        return 1


def _cmd_rule_create(args: argparse.Namespace) -> int:
    """Create a new rule interactively."""
    rule = _create_rule_interactive()

    if not rule:
        print("Rule creation cancelled.", file=sys.stderr)
        return 1

    # Validate
    errors = _validate_rule(rule)
    if errors:
        print("Rule validation failed:", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        return 1

    # Output
    output_path = getattr(args, "output", None)
    if output_path:
        yaml_content = _RULE_TEMPLATE.format(**rule)
        Path(output_path).write_text(yaml_content)
        print(f"Rule saved to: {output_path}")
    else:
        print("\nGenerated rule:")
        print(_RULE_TEMPLATE.format(**rule))

    return 0


def _load_rule_from_yaml(rule_file: Path) -> dict[str, Any]:
    """Load rule from YAML file, with fallback parsing."""
    try:
        import yaml

        with open(rule_file) as f:
            data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
    except ImportError:
        # Fallback: try simple parsing
        content = rule_file.read_text()
        rule_data = {"pattern": "", "message": ""}
        for line in content.split("\n"):
            if "pattern:" in line:
                rule_data["pattern"] = line.split("pattern:")[1].strip().strip('"')
            elif "message:" in line:
                rule_data["message"] = line.split("message:")[1].strip().strip('"')
        return rule_data


def _collect_test_files(target: Path) -> list[Path]:
    """Collect test files from target path."""
    if target.is_file():
        return [target]

    test_files = []
    for fp in target.rglob("*"):
        if fp.is_file() and fp.suffix in (".py", ".js", ".ts", ".go", ".rs", ".java"):
            test_files.append(fp)
    return test_files


def _print_test_results(results: dict[str, Any]) -> None:
    """Print test results."""
    print(f"\nRule: {results['rule_id']}")
    print(f"Files tested: {results['files_tested']}")
    print(f"Matches found: {len(results['matches'])}")

    if results["matches"]:
        print("\nMatches:")
        for match in results["matches"][:20]:  # Limit to 20
            print(f"  {match['file']}:{match['line']}: {match['match']}")

    if results["errors"]:
        print("\nErrors:")
        for e in results["errors"]:
            print(f"  - {e}")


def _cmd_rule_test(args: argparse.Namespace) -> int:
    """Test a rule against files."""
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    # Load rule from YAML
    rule_data = _load_rule_from_yaml(rule_file)

    if not rule_data.get("pattern"):
        print("Error: No pattern found in rule file", file=sys.stderr)
        return 1

    # Get test files
    target = Path(args.path)
    test_files = _collect_test_files(target)

    if not test_files:
        print("No test files found.", file=sys.stderr)
        return 1

    # Test the rule
    results = _test_rule(rule_data, test_files)

    # Output
    _print_test_results(results)

    return 0 if not results["errors"] else 1


def _cmd_rule_validate(args: argparse.Namespace) -> int:
    """Validate a rule file."""
    rule_file = Path(args.rule_file)
    if not rule_file.exists():
        print(f"Error: Rule file not found: {rule_file}", file=sys.stderr)
        return 1

    # Load rule
    try:
        import yaml

        with open(rule_file) as f:
            rule = yaml.safe_load(f)
    except ImportError:
        content = rule_file.read_text()
        rule = {}
        for line in content.split("\n"):
            if "pattern:" in line:
                rule["pattern"] = line.split("pattern:")[1].strip().strip('"')
            elif "message:" in line:
                rule["message"] = line.split("message:")[1].strip().strip('"')
            elif "severity:" in line:
                rule["severity"] = line.split("severity:")[1].strip()
            elif "category:" in line:
                rule["category"] = line.split("category:")[1].strip()
            elif "id:" in line and not line.strip().startswith("#"):
                rule["id"] = line.split("id:")[1].strip()

    # Validate
    errors = _validate_rule(rule)

    if errors:
        print(f"\n❌ Validation failed for: {rule_file}")
        for e in errors:
            print(f"  - {e}")
        return 1
    else:
        print(f"\n✅ Validation passed for: {rule_file}")
        return 0


def cmd_trend(args: argparse.Namespace) -> int:
    """Show quality trend dashboard."""
    project_dir = Path(args.path).resolve()

    if getattr(args, "clear", False):
        trend_file = project_dir / _TREND_DATA_FILE
        if trend_file.exists():
            trend_file.unlink()
            print("Trend history cleared.")
        else:
            print("No trend history to clear.")
        return 0

    trend_data = _load_trend_data(project_dir)

    if getattr(args, "json", False):
        print(_format_trend_report(trend_data, output_json=True))
    else:
        print(_format_trend_report(trend_data))

    return 0


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
        print("Error: Unknown webhook scheme. Use slack:// or dingtalk://", file=sys.stderr)
        return 1

    if success:
        print("✅ Notification sent successfully")
    else:
        print("", file=sys.stderr)
        return 1

    return 0


def cmd_detect(args: argparse.Namespace) -> int:
    """Detect project language and framework."""
    target = Path(args.path).resolve()
    result = detect_language(target)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(f"Language:  {result['language']}")
        print(f"Framework: {result.get('framework') or 'N/A'}")
        print(f"Confidence: {result['confidence']}")

    return 0


def cmd_list_rules(args: argparse.Namespace) -> int:
    """List rules for a specific language."""
    rules = load_rules_for_language(args.lang)
    patterns = rules.get("anti_patterns", [])

    if args.json:
        print(json.dumps(patterns, indent=2, ensure_ascii=False))
        return 0

    print(f"Rules for: {args.lang}")
    print(f"Total: {len(patterns)} anti-patterns\n")

    # Group by severity
    for severity in ("error", "warning", "info"):
        group = [p for p in patterns if p.get("severity") == severity]
        if group:
            color = _SEVERITY_COLORS.get(severity, "")
            print(f"{color}{'=' * 60}")
            print(f"  {severity.upper()} ({len(group)} rules)")
            print(f"{'=' * 60}{_RESET}")
            for p in group:
                print(f"  {p.get('id', 'unknown'):30s}  {p.get('name', '')}")
                if p.get("message"):
                    print(f"  {' ' * 30}  → {p['message']}")
            print()

    return 0


def _collect_report_issues(target: Path, rules: dict[str, Any]) -> tuple[list[Issue], int]:
    """Collect issues for report generation."""
    all_issues: list[Issue] = []
    files_checked = 0

    if target.is_file():
        all_issues = check_file(target, rules)
        files_checked = 1
    else:
        for fp in target.rglob("*"):
            if fp.is_file() and any(part not in SKIP_DIRS for part in fp.parts):
                if fp.suffix not in SKIP_EXTENSIONS:
                    if _detect_language_from_file(fp):
                        all_issues.extend(check_file(fp, rules))
                        files_checked += 1

    return all_issues, files_checked


def _build_json_report(
    language: str,
    framework: str | None,
    files_checked: int,
    all_issues: list[Issue],
    severity_counts: dict[str, int],
    category_counts: dict[str, int],
    top_files: list[tuple[str, int]],
    passed: bool,
) -> dict[str, Any]:
    """Build JSON report structure."""
    return {
        "language": language,
        "framework": framework,
        "files_checked": files_checked,
        "total_issues": len(all_issues),
        "severity": severity_counts,
        "categories": category_counts,
        "top_files": [{"file": f, "issues": c} for f, c in top_files],
        "passed": passed,
    }


def _determine_pass_status(severity_counts: dict[str, int], error_threshold: int, warning_threshold: int) -> bool:
    """Determine if report passes based on thresholds."""
    passed = bool(severity_counts["error"] <= error_threshold)
    if warning_threshold >= 0:
        passed = passed and severity_counts["warning"] <= warning_threshold
    return passed


def _validate_report_target(target: Path, args: argparse.Namespace) -> tuple[str, str | None] | None:
    """Validate target and return language/framework, or None if error."""
    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return None

    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")
    framework = getattr(args, "framework", None) or detected.get("framework")

    if language == "unknown":
        print("Error: Could not detect language. Use --lang to specify.", file=sys.stderr)
        return None

    return language, framework


def _load_report_rules(language: str, framework: str | None) -> dict[str, Any]:
    """Load rules for report generation."""
    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))
    return rules


def _output_report(args: argparse.Namespace, report_data: dict[str, Any]) -> None:
    """Output report in requested format."""
    if getattr(args, "json", False):
        report = _build_json_report(
            report_data["language"],
            report_data["framework"],
            report_data["files_checked"],
            [],  # all_issues not needed for count since we have total
            report_data["severity_counts"],
            report_data["category_counts"],
            report_data["top_files"],
            report_data["passed"],
        )
        print(json.dumps(report, indent=2))
    else:
        _print_report_text(
            report_data["target"],
            report_data["language"],
            report_data["framework"],
            report_data["files_checked"],
            report_data["severity_counts"],
            report_data["category_counts"],
            report_data["top_files"],
            report_data["passed"],
            report_data["error_threshold"],
            report_data["warning_threshold"],
        )


def cmd_report(args: argparse.Namespace) -> int:
    """Generate a quality gate report."""
    target = Path(args.path).resolve()

    validation = _validate_report_target(target, args)
    if validation is None:
        return 1
    language, framework = validation

    # Load rules
    rules = _load_report_rules(language, framework)

    # Collect all issues
    all_issues, files_checked = _collect_report_issues(target, rules)
    severity_counts, category_counts, top_files = _count_issues(all_issues)

    # Determine pass/fail
    error_threshold = getattr(args, "error_threshold", 0)
    warning_threshold = getattr(args, "warning_threshold", -1)
    passed = _determine_pass_status(severity_counts, error_threshold, warning_threshold)

    # Build report data
    report_data = {
        "target": target,
        "language": language,
        "framework": framework,
        "files_checked": files_checked,
        "severity_counts": severity_counts,
        "category_counts": category_counts,
        "top_files": top_files,
        "passed": passed,
        "error_threshold": error_threshold,
        "warning_threshold": warning_threshold,
    }

    # Output
    _output_report(args, report_data)

    return 0 if passed else 1


def cmd_install_hooks(args: argparse.Namespace) -> int:
    """Install pre-commit hook into a project."""
    target = Path(args.path).resolve()
    git_dir = target / ".git"

    if not git_dir.exists():
        print(f"Error: Not a git repository: {target}", file=sys.stderr)
        return 1

    hooks_dir = git_dir / "hooks"
    hooks_dir.mkdir(exist_ok=True)

    # Install pre-push hook if requested
    if getattr(args, "pre_push", False):
        hook_path = hooks_dir / "pre-push"
        adg_hook_source = Path.home() / ".config" / "adg" / "hooks" / "pre-push"

        if adg_hook_source.exists():
            hook_path.write_text(adg_hook_source.read_text())
        else:
            hook_path.write_text(_DEFAULT_PRE_PUSH_HOOK)

        hook_path.chmod(0o755)
        print(f"✅ ADG pre-push hook installed: {hook_path}")
        print("   Run 'adg check .' to test manually")
        return 0

    # Default: install pre-commit hook
    hook_path = hooks_dir / "pre-commit"
    adg_hook_source = Path.home() / ".config" / "adg" / "hooks" / "pre-commit"

    # Try to copy from installed hooks first
    if adg_hook_source.exists():
        hook_path.write_text(adg_hook_source.read_text())
    else:
        # Write default hook
        hook_path.write_text(_DEFAULT_PRE_COMMIT_HOOK)

    hook_path.chmod(0o755)
    print(f"✅ ADG pre-commit hook installed: {hook_path}")
    print("   Run 'adg check .' to test manually")
    return 0


def cmd_html_report(args: argparse.Namespace) -> int:
    """Generate HTML quality gate report."""
    from tools.report import save_html_report

    target = Path(args.path).resolve()
    detected = detect_language(target)
    language = args.lang or detected.get("language", "unknown")
    framework = detected.get("framework")

    rules = load_rules_for_language(language)
    if framework:
        fw_rules = load_framework_rules(framework)
        rules["anti_patterns"].extend(fw_rules.get("anti_patterns", []))

    if target.is_file():
        issues = check_file(target, rules)
        files_checked = 1
    else:
        issues = check_directory(target, rules)
        files_checked = len(set(i.file for i in issues))

    output_path = save_html_report(issues, args.output, language, framework, files_checked)
    print(f"HTML report saved to: {output_path}")
    print(f"  Language: {language}")
    print(f"  Issues: {len(issues)}")
    return 0


def cmd_recommend(args: argparse.Namespace) -> int:
    """AI-powered rule recommendations."""
    from tools.ai_recommender import format_recommendations_text, recommend_rules

    target = Path(args.path).resolve()
    result = recommend_rules(target, args.max)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        print(format_recommendations_text(result))

    # Apply: auto-generate .adg/rules.yml
    if getattr(args, "apply", False):
        return _apply_recommendations(target, result)

    return 0


def _load_existing_rules(rules_file: Path) -> dict[str, Any]:
    """Load existing rules from file."""
    existing_rules: dict[str, Any] = {"anti_patterns": []}
    if rules_file.exists():
        try:
            import yaml

            with open(rules_file) as f:
                data = yaml.safe_load(f)
                if data and "anti_patterns" in data:
                    existing_rules = data
        except Exception as exc:
            logging.getLogger(__name__).debug(f"Skipped unreadable rules file {rules_file}: {exc}")
    return existing_rules


def _build_new_rules(result: dict[str, Any], existing_ids: set[str]) -> list[dict[str, Any]]:
    """Build new rules from recommendations."""
    new_rules: list[dict[str, Any]] = []
    for rec in result["recommendations"]:
        if rec["rule_id"] not in existing_ids:
            new_rules.append(
                {
                    "id": rec["rule_id"],
                    "name": rec["name"],
                    "severity": rec["severity"],
                    "category": rec["category"],
                    "message": rec["reason"],
                    "fix_hint": f"Auto-generated from pattern: {rec['example']['code']}",
                }
            )
            existing_ids.add(rec["rule_id"])
    return new_rules


def _save_rules(rules_file: Path, existing_rules: dict[str, Any]) -> None:
    """Save rules to file."""
    import yaml

    existing_rules["config_version"] = "1.0"
    existing_rules["source"] = "auto-generated-by-recommend"

    with open(rules_file, "w") as f:
        yaml.dump(existing_rules, f, sort_keys=False, allow_unicode=True)


def _apply_recommendations(project_dir: Path, result: dict[str, Any]) -> int:
    """Write recommended rules to .adg/rules.yml."""
    rules_dir = project_dir / ".adg"
    rules_dir.mkdir(exist_ok=True)
    rules_file = rules_dir / "rules.yml"

    # Load existing rules if any
    existing_rules = _load_existing_rules(rules_file)
    existing_ids = {r.get("id") for r in existing_rules.get("anti_patterns", [])}

    # Add new recommendations as custom rules
    new_rules = _build_new_rules(result, existing_ids)

    if new_rules:
        existing_rules.setdefault("anti_patterns", []).extend(new_rules)
        _save_rules(rules_file, existing_rules)

        print(f"\n✅ Applied {len(new_rules)} new rules to {rules_file}")
        for r in new_rules:
            print(f"   + {r['id']} ({r['severity']})")
    else:
        print(f"\nℹ️  No new rules to apply (all already exist in {rules_file})")

    return 0


def cmd_pattern_learner(args: argparse.Namespace) -> int:
    """Learn team coding norms from codebase."""
    from tools.scripts.rules_engine.pattern_learner import PatternLearner

    target = Path(args.path).resolve()

    learner = PatternLearner()
    learner.MIN_OCCURRENCES = getattr(args, "min_occurrences", 3)
    patterns = learner.learn_from_directory(target)

    if getattr(args, "json", False):
        import json

        print(json.dumps(patterns, indent=2, ensure_ascii=False))
    else:
        print(f"🔍 AI 分析完成，发现 {len(patterns)} 个模式和建议")
        for p in patterns:
            freq = p.get("frequency", p.get("confidence", 0))
            conf = p.get("confidence", 0)
            ptype = p.get("type", "pattern")
            action = p.get("suggested_action", "")
            if freq > 0 or conf > 0:
                print(f"\n  [{ptype}] {p.get('message', p.get('pattern', ''))}")
                print(f"    置信度: {conf:.0%} | 建议: {action}")

    return 0


def cmd_lsp(args: argparse.Namespace) -> int:
    """Start ADG Language Server."""
    import logging

    from tools.lsp.server import run_stdio_server, run_tcp_server

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    if args.stdio:
        run_stdio_server()
    else:
        run_tcp_server(args.port)
    return 0


def cmd_dashboard(args: argparse.Namespace) -> int:
    """Start web dashboard or generate static HTML."""
    from tools.dashboard import generate_dashboard_html, start_dashboard

    if args.static:
        generate_dashboard_html(args.path, args.static)
        print(f"Static dashboard saved to: {args.static}")
        return 0

    start_dashboard(args.path, args.port, args.host)
    return 0


def cmd_marketplace(args: argparse.Namespace) -> int:
    """Rule pack marketplace operations."""
    from tools.marketplace import format_packs_list, install_pack, list_packs, search_packs, uninstall_pack

    cmd = args.marketplace_command

    if cmd == "list":
        packs = list_packs()
        print(format_packs_list(packs))
    elif cmd == "search":
        packs = search_packs(args.query)
        print(format_packs_list(packs))
    elif cmd == "install":
        result = install_pack(args.pack_id, language=args.lang)
        if result["success"]:
            print(f"✅ Installed pack: {result['pack']}")
            print(f"   Rules installed: {result['rules_installed']}")
            print(f"   Total rules: {result['total_rules']}")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    elif cmd == "uninstall":
        result = uninstall_pack(args.pack_id)
        if result["success"]:
            print(f"✅ Uninstalled pack: removed {result['removed']} rules")
        else:
            print(f"❌ Failed: {result['error']}")
            return 1
    else:
        print("Usage: adg marketplace {list|search|install|uninstall}")
        return 1
    return 0


def cmd_monorepo(args: argparse.Namespace) -> int:
    """Check all projects in a monorepo."""
    from tools.multiproject import MonorepoChecker

    checker = MonorepoChecker(args.path)
    results = checker.check_all()

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        print(checker.generate_report(results))

    return 0 if results["total_summary"]["passed"] else 1


def cmd_bench(args: argparse.Namespace) -> int:
    """Run performance benchmarks."""
    from tools.benchmarks import run_all_benchmarks

    file_counts = [int(x) for x in args.files.split(",")]
    languages = [x.strip() for x in args.languages.split(",")]

    results = run_all_benchmarks(file_counts, languages)

    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    return 0


def cmd_cicd(args: argparse.Namespace) -> int:
    """Generate CI/CD configuration files."""
    from tools.cicd import generate_ci_config

    generate_ci_config(args.platform, args.output)
    print(f"✅ Generated {args.platform} CI/CD config in: {args.output}")
    return 0

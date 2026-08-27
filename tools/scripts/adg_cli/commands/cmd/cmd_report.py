from __future__ import annotations

import argparse
import json
import sys

from ._shared import (
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    Any,
    Issue,
    Path,
    _count_issues,
    _detect_language_from_file,
    _print_report_text,
    check_file,
    detect_language,
    load_framework_rules,
    load_rules_for_language,
)


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


def _determine_pass_status(severity_counts: dict[str, int], error_threshold: int, warning_threshold: int) -> bool:
    """Determine if report passes based on thresholds."""
    passed = bool(severity_counts["error"] <= error_threshold)
    if warning_threshold >= 0:
        passed = passed and severity_counts["warning"] <= warning_threshold
    return passed


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

"""CLI entry point for validate_language_rules.py.

Extracted from validate_language_rules.py for modularity.
Handles argument parsing, incremental mode, auto-fix, and output formatting.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from tools.scripts._common import file_hash_full as _file_hash

from .health import calculate_health_score
from .models import FixResult, ValidationResult
from .pipeline import detect_language_from_file, validate_directory, validate_file


def _load_cache(cache_file: Path) -> dict[str, str]:
    """Load file hash cache from disk."""
    if cache_file.exists():
        try:
            result: dict[str, str] = json.loads(cache_file.read_text())
            return result
        except (json.JSONDecodeError, OSError):
            pass
    return {}


def _save_cache(cache_file: Path, cache: dict[str, str]) -> None:
    """Save file hash cache to disk."""
    try:
        cache_file.write_text(json.dumps(cache))
    except OSError:
        pass


def _get_supported_files(dirpath: Path, exclude: list[str]) -> list[Path]:
    """Get all supported files in a directory."""
    exclude = exclude or [
        "node_modules",
        "target",
        "vendor",
        ".git",
        "__pycache__",
        ".venv",
    ]
    files = []
    for fp in sorted(dirpath.rglob("*")):
        if not fp.is_file():
            continue
        if any(ex in fp.parts for ex in exclude):
            continue
        if detect_language_from_file(fp):
            files.append(fp)
    return files


SEVERITY_ICONS = {"error": "error", "warning": "warning", "info": "info"}


def _print_json_results(results: list[ValidationResult]) -> int:
    """Print validation results in JSON format. Returns exit code."""
    output = {
        "results": [r.to_dict() for r in results],
        "total_files": len(results),
        "total_errors": sum(r.error_count for r in results),
        "total_warnings": sum(r.warning_count for r in results),
        "total_info": sum(r.info_count for r in results),
        "passed": all(r.passed for r in results),
    }
    print(json.dumps(output, indent=2, ensure_ascii=False))
    return 0 if output["passed"] else 1


def _print_text_results(results: list[ValidationResult]) -> int:
    """Print validation results in text format. Returns exit code."""
    total_errors = 0
    total_warnings = 0

    for result in results:
        if not result.issues:
            continue

        print(f"\n  {result.file} ({result.language}, {result.lines_checked} lines)")

        for issue in sorted(result.issues, key=lambda x: (x.severity, x.line)):
            icon = SEVERITY_ICONS.get(issue.severity, "?")
            loc = f":{issue.line}" if issue.line > 0 else ""
            print(f"    {icon} [{issue.rule_id}] {issue.message}{loc}")
            if issue.fix_hint:
                print(f"      -> {issue.fix_hint}")

            if issue.severity == "error":
                total_errors += 1
            elif issue.severity == "warning":
                total_warnings += 1

    # Summary
    print("\n  Summary:")
    print(f"    Files checked: {len(results)}")
    print(f"    Errors:   {total_errors}")
    print(f"    Warnings: {total_warnings}")

    if total_errors > 0:
        print("\n  FAILED - errors must be fixed")
        return 1
    elif total_warnings > 0:
        print("\n  PASSED with warnings")
        return 0
    else:
        print("\n  PASSED - all checks clean")
        return 0


def print_results(results: list[ValidationResult], use_json: bool = False) -> int:
    """Print validation results. Returns exit code (0=pass)."""
    if use_json:
        return _print_json_results(results)
    return _print_text_results(results)


def build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="Language-specific code quality validator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s src/ --lang python
  %(prog)s lib/ --lang typescript --format json -o report.json
  %(prog)s . --auto-detect --format html -o report.html
  %(prog)s main.rs --lang rust --fix --dry-run
  %(prog)s . --auto-detect --max-errors 0 --max-warnings 10
  %(prog)s . --auto-detect --linters ruff mypy
  %(prog)s . --auto-detect --health-score
  %(prog)s . --auto-detect --custom-rules .ai-rules/
        """,
    )
    parser.add_argument("path", type=Path, help="File or directory to validate")
    parser.add_argument(
        "--lang",
        choices=[
            "python",
            "typescript",
            "rust",
            "go",
            "java",
            "kotlin",
            "csharp",
            "php",
            "ruby",
            "cpp",
            "swift",
            "scala",
            "elixir",
            "lua",
            "javascript",
            "zig",
            "r",
            "clojure",
            "haskell",
            "dart",
            "powershell",
            "perl",
            "assembly",
            "fortran",
            "matlab",
            "graphql",
        ],
        help="Language to validate against",
    )
    parser.add_argument(
        "--auto-detect",
        action="store_true",
        help="Auto-detect language from file extensions",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output results as JSON (legacy)",
    )
    parser.add_argument("--fail-on-warnings", action="store_true", help="Exit with error on warnings")
    parser.add_argument(
        "--exclude",
        nargs="*",
        default=["node_modules", "target", "vendor", ".git", "__pycache__", ".venv"],
        help="Directories to exclude",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json", "html", "junit", "sarif"],
        default="text",
        help="Output format (default: text). sarif = GitHub Code Scanning",
    )
    parser.add_argument("-o", "--output", type=Path, help="Write report to file")
    parser.add_argument(
        "--max-errors",
        type=int,
        default=None,
        help="Max allowed errors (exit 1 if exceeded)",
    )
    parser.add_argument(
        "--max-warnings",
        type=int,
        default=None,
        help="Max allowed warnings (exit 1 if exceeded)",
    )
    parser.add_argument("--fix", action="store_true", help="Apply auto-fixes")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what --fix would change without writing",
    )
    parser.add_argument(
        "--custom-rules",
        type=Path,
        help="Directory with custom .yml rules (default: .ai-rules/)",
    )
    parser.add_argument("--health-score", action="store_true", help="Show project health score")
    parser.add_argument(
        "--incremental",
        action="store_true",
        help="Skip files unchanged since last check (uses .rule-cache)",
    )
    parser.add_argument(
        "--changed-files",
        nargs="*",
        type=Path,
        help="Only check these specific files (for incremental)",
    )
    parser.add_argument(
        "--linters",
        nargs="*",
        choices=["ruff", "mypy", "eslint", "golangci-lint"],
        help="Run external linters and aggregate results",
    )
    return parser


def _validate_changed_files(
    changed_files: list[Path],
    language: str | None,
    custom_rules: dict[str, Any] | None,
) -> list[ValidationResult]:
    """校验 --changed-files 给出的文件列表.

    V2.17 P2-5 拆分: 从 _collect_results (D=21) 抽出.
    不存在文件跳过; 语言未指定则自动 detect.
    """
    results: list[ValidationResult] = []
    for fp in changed_files:
        if not fp.exists():
            continue
        lang = language or detect_language_from_file(fp)
        if lang:
            results.append(validate_file(fp, lang, custom_rules=custom_rules))
    return results


def _validate_single_file(
    path: Path,
    language: str | None,
    custom_rules: dict[str, Any] | None,
    incremental: bool,
) -> list[ValidationResult] | None:
    """校验单个文件, 支持 incremental cache.

    V2.17 P2-5 拆分: 从 _collect_results (D=21) 抽出.
    返回 None = 语言无法检测 (错误);
    返回 [] = 文件未变 (incremental 命中);
    返回 [result] = 正常校验结果.
    """
    if language is None:
        language = detect_language_from_file(path)
    if language is None:
        print(
            f"Error: Cannot detect language for {path}. Use --lang.",
            file=sys.stderr,
        )
        return None

    if incremental:
        fh = _file_hash(path)
        cache_file = path.parent / ".rule-cache"
        cache = _load_cache(cache_file)
        if cache.get(str(path)) == fh:
            return []  # File unchanged
        cache[str(path)] = fh
        _save_cache(cache_file, cache)

    return [validate_file(path, language, custom_rules=custom_rules)]


def _validate_directory(
    path: Path,
    language: str | None,
    custom_rules: dict[str, Any] | None,
    auto_detect: bool,
    exclude: Any,
    incremental: bool,
) -> list[ValidationResult] | None:
    """校验目录, 支持 incremental cache 与 auto-detect.

    V2.17 P2-5 拆分: 从 _collect_results (D=21) 抽出.
    返回 None = 参数错误 (无 --lang 也无 --auto-detect).
    """
    if language is None and not auto_detect:
        print("Error: Use --lang or --auto-detect for directories.", file=sys.stderr)
        return None

    results: list[ValidationResult] = []

    if incremental:
        cache_file = path / ".rule-cache"
        cache = _load_cache(cache_file)
        all_files = _get_supported_files(path, exclude)
        changed = [f for f in all_files if _file_hash(f) != cache.get(str(f))]
        for f in all_files:
            cache[str(f)] = _file_hash(f)
        _save_cache(cache_file, cache)
        for fp in changed:
            lang = language or detect_language_from_file(fp)
            if lang:
                results.append(validate_file(fp, lang, custom_rules=custom_rules))
        if not results:
            print("No changed files detected (incremental mode).")
    else:
        results = validate_directory(path, language, exclude, custom_rules=custom_rules)

    return results


def _collect_results(
    args: argparse.Namespace,
    language: str | None,
    custom_rules: dict[str, Any] | None,
) -> list[ValidationResult] | None:
    """Collect validation results based on CLI arguments (orchestrator).

    V2.17 P2-5 拆分: 从 D=21 / 80 行主函数拆出 3 个 collector.
    主函数仅按 args 类型分发:
    - changed_files → _validate_changed_files
    - 单文件      → _validate_single_file
    - 目录        → _validate_directory
    """
    if args.changed_files:
        return _validate_changed_files(args.changed_files, language, custom_rules)
    if args.path.is_file():
        return _validate_single_file(args.path, language, custom_rules, args.incremental)
    return _validate_directory(
        args.path,
        language,
        custom_rules,
        args.auto_detect,
        args.exclude,
        args.incremental,
    )


def _apply_auto_fix(results: list[ValidationResult], dry_run: bool) -> int:
    """Apply auto-fixes. Returns 0 on success, 1 if dry-run with no results."""
    from tools.scripts.fix_applier import apply_fixes

    all_fixes: list[FixResult] = []
    for result in results:
        fp = Path(result.file)
        fixes = apply_fixes(fp, result.issues, dry_run=dry_run)
        all_fixes.extend(fixes)

    if all_fixes:
        action = "Would fix" if dry_run else "Fixed"
        print(f"\n{action} {len(all_fixes)} issue(s):")
        for fix in all_fixes:
            print(f"  {fix.file}:{fix.line} [{fix.rule_id}]")
            print(f"    - {fix.original}")
            print(f"    + {fix.fixed}")

    if dry_run and not results:
        return -1  # Signal: return early
    return 0


def _check_thresholds(
    results: list[ValidationResult],
    max_errors: int | None,
    max_warnings: int | None,
    fail_on_warnings: bool,
) -> int | None:
    """Check threshold constraints. Returns 1 for failure, None for pass."""
    if max_errors is not None:
        total_errors = sum(r.error_count for r in results)
        if total_errors > max_errors:
            print(f"\nFAILED: {total_errors} errors exceeds max-errors={max_errors}")
            return 1

    if max_warnings is not None:
        total_warnings = sum(r.warning_count for r in results)
        if total_warnings > max_warnings:
            print(f"\nFAILED: {total_warnings} warnings exceeds max-warnings={max_warnings}")
            return 1

    if fail_on_warnings and any(r.warning_count > 0 for r in results):
        return 1

    return None


def _load_custom_rules(args: argparse.Namespace, path: Path) -> Any:
    """Load custom rules based on args."""
    from .pipeline import load_custom_rules

    if args.custom_rules:
        return load_custom_rules(args.custom_rules)
    elif args.auto_detect or path.is_dir():
        project_dir = path if path.is_dir() else path.parent
        return load_custom_rules(project_dir)
    return None


def _handle_auto_fix(results: list[ValidationResult], dry_run: bool) -> int | None:
    """Handle auto-fix logic. Returns exit code to indicate exit, None to continue."""
    fix_result = _apply_auto_fix(results, dry_run=dry_run)
    if fix_result == -1:
        return 0
    return None


def _handle_health_score(results: list[ValidationResult]) -> None:
    """Handle health score display."""
    health = calculate_health_score(results)
    print(f"\n  Health Score: {health.score}/100 (Grade: {health.grade})")
    for detail in health.details:
        print(f"    - {detail}")


def _handle_linters(args: argparse.Namespace, path: Path) -> None:
    """Handle linter aggregation."""
    if not args.linters:
        return

    from tools.scripts.linter_runner import run_linter_aggregation

    linter_issues = run_linter_aggregation(path, args.linters)
    if linter_issues:
        print(f"\n  Linter Results ({len(linter_issues)} issues from {', '.join(args.linters)}):")
        for issue in linter_issues[:20]:
            print(f"    [{issue['linter']}] {issue['file']}:{issue['line']} {issue['message']}")
        if len(linter_issues) > 20:
            print(f"    ... and {len(linter_issues) - 20} more")


def _handle_output(results: list[ValidationResult], args: argparse.Namespace) -> int | None:
    """Handle output formats. Returns exit code if handled, None otherwise."""
    if args.format != "text" or args.json_output:
        from tools.scripts.report_generator import write_report

        fmt = "json" if args.json_output else args.format
        content = write_report(results, fmt, args.output)
        if content and not args.output:
            print(content)

        # Check thresholds for non-text formats
        if args.max_errors is not None:
            total_errors = sum(r.error_count for r in results)
            if total_errors > args.max_errors:
                return 1
        if args.max_warnings is not None:
            total_warnings = sum(r.warning_count for r in results)
            if total_warnings > args.max_warnings:
                return 1
        if args.fail_on_warnings and any(r.warning_count > 0 for r in results):
            return 1
        return 0
    return None


def _handle_text_output(results: list[ValidationResult], args: argparse.Namespace) -> int:
    """Handle text output format."""
    exit_code = print_results(results, use_json=False)
    threshold_fail = _check_thresholds(results, args.max_errors, args.max_warnings, args.fail_on_warnings)
    if threshold_fail is not None:
        return threshold_fail
    return exit_code


def main() -> int:
    """Main entry point for validate_language_rules CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}", file=sys.stderr)
        return 1

    language = args.lang

    # Load custom rules
    custom_rules = _load_custom_rules(args, args.path)

    results = _collect_results(args, language, custom_rules)
    if results is None:
        return 1

    # Auto-fix
    fix_exit = _handle_auto_fix(results, args.dry_run)
    if fix_exit is not None:
        return fix_exit

    # Health score
    if args.health_score:
        _handle_health_score(results)

    # Linter aggregation
    _handle_linters(args, args.path)

    # Output handling
    output_exit = _handle_output(results, args)
    if output_exit is not None:
        return output_exit

    return _handle_text_output(results, args)

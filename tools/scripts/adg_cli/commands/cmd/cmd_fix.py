from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.scripts.rules_engine.models import CheckResult as CheckResultLike

import argparse
import json
import subprocess
import sys

from ._shared import (
    SKIP_DIRS_ALL,
    Any,
    Issue,
    Path,
    detect_language,
    fix_directory,
    fix_file,
)


def _collect_python_files(target: Path) -> list[Path]:
    """收集目标路径下全部 Python 文件（跳过 SKIP_DIRS_ALL）。"""
    files: list[Path] = [target] if target.is_file() else []
    if not files:
        for fp in sorted(target.rglob("*.py")):
            rel_parts = fp.relative_to(target).parts
            if any(part in SKIP_DIRS_ALL for part in rel_parts):
                continue
            files.append(fp)
    return files


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


def _render_smart_stats(stats: dict[str, object]) -> str:
    lines = [
        f"Smart fix (AutoFixOrchestrator): scanned {stats['files_scanned']} files",
        f"  fixes applied: {stats['fixes_applied']}",
        f"  errors: {stats['errors']}",
    ]
    return "\n".join(lines)


def _run_fix(target: Path, language: str | None) -> dict[str, Any]:
    """Run fix on target and return stats."""
    if target.is_file():
        stats = fix_file(target)
        stats["files"] = 1 if stats["fixed"] > 0 else 0
    else:
        stats = fix_directory(target, language)
    return stats


def _run_smart_fix(target: Path, language: str | None, as_json: bool) -> int:
    """--smart 模式: AutoFixOrchestrator + 工具级 provider（Ruff）修复 Python 文件。"""
    from tools.scripts.auto_fix import AutoFixOrchestrator, FixSafetyLevel, FixStrategy, RuffFixProvider

    orchestrator = AutoFixOrchestrator(
        strategy=FixStrategy.AUTO,
        safety_level=FixSafetyLevel.SAFE,
        backup=True,
    )
    orchestrator.register_provider(RuffFixProvider())

    files = _collect_python_files(target)
    results, scan_errors = _smart_scan_ruff_issues(files)

    plan = orchestrator.create_plan(results)
    fix_results = orchestrator.execute_plan(plan, Path.cwd())
    total_applied = sum(len(r.applied or []) for r in fix_results)
    total_errors = scan_errors + sum(len(r.errors or []) for r in fix_results)

    stats: dict[str, object] = {
        "mode": "smart",
        "files_scanned": len(files),
        "fixes_applied": total_applied,
        "errors": total_errors,
    }
    print(json.dumps(stats, indent=2) if as_json else _render_smart_stats(stats))
    return 0 if total_errors == 0 else 1


def _smart_scan_ruff_issues(files: list[Path]) -> tuple[list[CheckResultLike], int]:
    """对文件列表跑 ruff check，产出 CheckResult 列表（供 create_plan）。"""
    from tools.scripts.rules_engine.models import CheckResult, Issue

    results: list[CheckResult] = []
    scan_errors = 0
    for f in files:
        try:
            proc = subprocess.run(
                ["ruff", "check", "--output-format=concise", str(f)],
                capture_output=True,
                text=True,
                timeout=60,
            )
        except Exception as exc:  # noqa: BLE001 - 单文件扫描失败不中断整体
            print(f"Warning: ruff scan {f} failed: {exc}", file=sys.stderr)
            scan_errors += 1
            continue
        issues: list[Issue] = []
        for line in (proc.stdout or "").splitlines():
            parts = line.split(":", 4)
            if len(parts) >= 4 and parts[1].isdigit() and parts[2].isdigit():
                code = parts[3].split()[0] if parts[3].split() else "E501"
                issues.append(
                    Issue(
                        rule_id=code,
                        severity="warning",
                        category="style",
                        file=str(f),
                        line=int(parts[1]),
                        column=int(parts[2]),
                        message=parts[-1],
                        fix_hint="ruff --fix",
                    )
                )
        results.append(CheckResult(file=str(f), issues=issues, language="python"))
    return results, scan_errors


def cmd_fix(args: argparse.Namespace) -> int:
    """Apply automatic fixes to code files."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: Path not found: {target}", file=sys.stderr)
        return 1

    # Detect language
    detected = detect_language(target)
    language = args.lang or detected.get("language")

    smart = getattr(args, "smart", False)
    if smart:
        return _run_smart_fix(target, language, args.json)

    if args.json:
        stats = _run_fix(target, language)
        print(json.dumps(stats, indent=2))
    else:
        _print_fix_header(target, language)
        stats = _run_fix(target, language)
        _print_fix_results(stats)

    return 0 if stats["errors"] == 0 else 1

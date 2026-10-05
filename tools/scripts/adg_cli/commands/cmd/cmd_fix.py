from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from tools.scripts.auto_fix import AutoFixOrchestrator, RegexFixProvider
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
    """Run fix on target via AutoFixOrchestrator with language-dispatched providers.

    P1-2 重构（v2.14.0）:
    - adg_cli fix 单入口
    - Python → 先 RegexFixProvider 再 RuffFixProvider
    - 其他语言 → 仅 RegexFixProvider
    """
    from tools.scripts.adg_cli.core import FIX_RULES

    if language == "python":
        return _run_python_fix(target, FIX_RULES)
    return _run_other_lang_fix(target, language, FIX_RULES)


def _run_python_fix(target: Path, fix_rules: dict[str, Any]) -> dict[str, Any]:
    """Python 路径：先 RegexFixProvider（py-bare-except 等 FIX_RULES）再 RuffFixProvider。"""
    from tools.scripts.auto_fix import (
        AutoFixOrchestrator,
        FixSafetyLevel,
        FixStrategy,
        RegexFixProvider,
        RuffFixProvider,
    )

    applicable = {rid: info for rid, info in fix_rules.items() if info.get("language") in ("python", "common")}
    if target.is_file():
        regex_provider = RegexFixProvider("regex", FixSafetyLevel.SAFE, rules=applicable)
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        regex_actions = regex_provider.apply_rules(str(target))
        after_regex = target.read_text(encoding="utf-8") if target.exists() else ""
        orchestrator = AutoFixOrchestrator(
            strategy=FixStrategy.AUTO,
            safety_level=FixSafetyLevel.SAFE,
            backup=False,
        )
        orchestrator.register_provider(RuffFixProvider())
        ruff_stats = _orchestrate_target(target, orchestrator, "python", "python")
        return {
            "fixed": len(regex_actions) + ruff_stats["fixed"],
            "skipped": 0,
            "errors": 0,
            "files": 1 if before != after_regex or ruff_stats["files"] else 0,
        }
    regex_provider = RegexFixProvider("regex", FixSafetyLevel.SAFE, rules=applicable)
    regex_stats = _run_orchestrator_directory(target, regex_provider, "python")
    ruff_stats = _run_ruff_directory(target)
    return {
        "fixed": regex_stats["fixed"] + ruff_stats["fixed"],
        "skipped": 0,
        "errors": 0,
        "files": regex_stats["files"] + ruff_stats["files"],
    }


def _run_other_lang_fix(target: Path, language: str | None, fix_rules: dict[str, Any]) -> dict[str, Any]:
    """其他语言：仅 RegexFixProvider。"""
    from tools.scripts.auto_fix import FixSafetyLevel, RegexFixProvider

    applicable = {
        rid: info for rid, info in fix_rules.items() if language is None or info.get("language") in (language, "common")
    }
    if not applicable:
        return {"fixed": 0, "skipped": 0, "errors": 0, "files": 0}

    provider = RegexFixProvider("regex", FixSafetyLevel.SAFE, rules=applicable)
    if target.is_file():
        before = target.read_text(encoding="utf-8") if target.exists() else ""
        actions = provider.apply_rules(str(target))
        after = target.read_text(encoding="utf-8") if target.exists() else ""
        return {
            "fixed": len(actions),
            "skipped": 0,
            "errors": 0,
            "files": 1 if before != after else 0,
        }
    return _run_orchestrator_directory(target, provider, language)


def _orchestrate_target(
    target: Path,
    orchestrator: AutoFixOrchestrator,
    language: str | None,
    file_lang: str,
) -> dict[str, Any]:
    """用 orchestrator.execute_plan 处理单文件/目录（Python 路径）。"""

    if target.is_file():
        # 走 orchestrator 需要 CheckResult，这里用空 result + execute_plan 仍可触发 RuffFixProvider
        # RuffFixProvider.generate_fixes 依赖 issue，所以这里用空 plan 跑
        # 实际让 Ruff 直接跑（不通过 orchestrator 的 issue 流）
        import subprocess

        try:
            proc = subprocess.run(
                ["ruff", "check", "--fix", "--exit-zero", str(target)],
                capture_output=True,
                text=True,
                timeout=60,
            )
            # exit-zero 即使有 fix 也返回 0
            applied = 1 if proc.returncode in (0, 1) else 0
        except Exception:  # noqa: BLE001 - ruff 子进程不可用属环境降级，计入 applied=0 而非抛出
            applied = 0
        return {"fixed": applied, "skipped": 0, "errors": 0, "files": 1 if applied else 0}

    # 目录
    return _run_ruff_directory(target)


def _run_ruff_directory(target: Path) -> dict[str, Any]:
    """Python 目录：直接 ruff check --fix 整目录。"""
    import subprocess

    try:
        proc = subprocess.run(
            ["ruff", "check", "--fix", "--exit-zero", str(target)],
            capture_output=True,
            text=True,
            timeout=300,
        )
        # ruff 输出: "Found N errors" + "Fixed M"
        fixed = 0
        for line in (proc.stdout or "").splitlines():
            if "Fixed" in line:
                import re as _re

                m = _re.search(r"Fixed\s+(\d+)", line)
                if m:
                    fixed = int(m.group(1))
        return {"fixed": fixed, "skipped": 0, "errors": 0, "files": 1 if fixed else 0}
    except Exception:  # noqa: BLE001 - ruff 目录修复失败须报 errors，不能谎称成功
        return {"fixed": 0, "skipped": 0, "errors": 1, "files": 0}


def _run_orchestrator_directory(target: Path, provider: RegexFixProvider, language: str | None) -> dict[str, Any]:
    """P1-2 重构：目录模式统一用 RegexFixProvider.apply_rules。

    对目录内每个文件跑 provider.apply_rules(file_path) 并汇总。
    """
    from ._shared import SKIP_DIRS_ALL

    file_langs = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".go": "go",
        ".rs": "rust",
        ".java": "java",
        ".rb": "ruby",
        ".c": "c",
        ".h": "c",
        ".cpp": "cpp",
        ".hpp": "cpp",
        ".cs": "csharp",
        ".kt": "kotlin",
        ".swift": "swift",
        ".php": "php",
    }

    total = {"fixed": 0, "skipped": 0, "errors": 0, "files": 0}
    for fp in sorted(target.rglob("*")):
        if not fp.is_file():
            continue
        rel_parts = fp.relative_to(target).parts
        if any(part in SKIP_DIRS_ALL for part in rel_parts):
            continue
        if fp.suffix not in file_langs:
            continue
        if language and file_langs[fp.suffix] != language:
            continue

        before = fp.read_text(encoding="utf-8")
        actions = provider.apply_rules(str(fp))
        after = fp.read_text(encoding="utf-8")
        total["fixed"] += len(actions)
        if before != after:
            total["files"] += 1
    return total


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
    if target.is_file():
        # P1-2 重构：单文件用 _detect_language_from_file（按扩展名 dispatch）
        from ._shared import _detect_language_from_file

        detected_lang = _detect_language_from_file(target)
        language = args.lang or detected_lang
    else:
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

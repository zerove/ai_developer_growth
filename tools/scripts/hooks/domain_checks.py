"""领域检查函数: language-rules, quality-gate, governance-audit."""

from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts._common import get_project_root
from tools.scripts.ai_quality_gate import check_file
from tools.scripts.hooks.basic_checks import CODE_EXTENSIONS
from tools.scripts.rules_engine.logger import logger
from tools.scripts.validate_language_rules import (
    detect_language_from_file,
    validate_directory,
    validate_file,
)

if TYPE_CHECKING:
    from collections.abc import Callable


def _issue_key(issue: dict[str, Any]) -> str:
    """构造问题的稳定标识 (类型 + 消息)，容忍行号漂移。"""
    return f"{issue.get('type', 'unknown')}:{issue.get('message', '')}"


def _count_issues(issues: list[dict[str, Any]]) -> dict[str, int]:
    """按稳定标识统计问题数量。"""
    counts: dict[str, int] = {}
    for issue in issues:
        key = _issue_key(issue)
        counts[key] = counts.get(key, 0) + 1
    return counts


def _load_issue_baseline(baseline_path: Path) -> dict[str, dict[str, int]] | None:
    """加载问题计数基线；文件不存在或损坏时返回 None。"""
    if not baseline_path.exists():
        return None
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except Exception:
        return None
    result: dict[str, dict[str, int]] = {}
    for fpath, issues in data.get("files", {}).items():
        if isinstance(issues, dict):
            result[fpath] = {str(k): int(v) for k, v in issues.items()}
    return result


def _save_issue_baseline(baseline_path: Path, all_results: list[tuple[Path, dict[str, Any]]]) -> None:
    """将当前全部问题写入基线（含存量，保证棘轮只减不增）。"""
    files: dict[str, dict[str, int]] = {}
    for filepath, r in all_results:
        counts = _count_issues(r["issues"])
        if counts:
            files[str(filepath)] = counts
    payload = {"version": 1, "files": files}
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _merge_issue_baseline(
    baseline_path: Path,
    all_results: list[tuple[Path, dict[str, Any]]],
    existing_baseline: dict[str, dict[str, int]],
) -> None:
    """合并式刷新基线。

    局部运行（单文件/子目录）只更新本次检查到的文件，
    未检查文件保留原有计数，避免局部结果覆盖全量基线。
    """
    checked = {str(filepath) for filepath, _ in all_results}
    files: dict[str, dict[str, int]] = {}
    for fpath, counts in existing_baseline.items():
        if fpath not in checked:
            files[fpath] = dict(counts)
    for filepath, r in all_results:
        counts = _count_issues(r["issues"])
        if counts:
            files[str(filepath)] = counts
    payload = {"version": 1, "files": files}
    baseline_path.parent.mkdir(parents=True, exist_ok=True)
    baseline_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def run_language_rules(path: Path, lang: str | None = None) -> tuple[bool, str]:
    """Run language-specific rules validation.

    Args:
        path: File or directory to validate.
        lang: Language override (auto-detected if None).
    """
    if path.is_file():
        language = lang or detect_language_from_file(path)
        if not language:
            return False, f"Cannot detect language for {path}"
        result = validate_file(path, language)
        return result.passed, str(result.to_dict())
    else:
        results = validate_directory(path)
        passed = all(r.passed for r in results)
        output = "\n".join(f"{r.file}: {'PASS' if r.passed else 'FAIL'} ({len(r.issues)} issues)" for r in results)
        return passed, output


def run_quality_gate(
    path: Path,
    *,
    full: bool = False,
    check_annotation: bool = False,
    check_security: bool = False,
    check_type: bool = False,
    check_error: bool = False,
    check_structure: bool = False,
    check_patterns: bool = False,
    format: str = "text",
) -> tuple[bool, str]:
    """Run AI Quality Gate checks.

    Args:
        path: File or directory to check.
        full: Run all checks.
        check_annotation: Check AI annotation patterns.
        check_security: Check security patterns.
        check_type: Check type safety.
        check_error: Check error handling.
        check_structure: Check code structure.
        check_patterns: Run all anti-pattern checks.
        format: Output format ('text' or 'json').
    """
    checks: list[str] = []
    if full or check_patterns:
        checks = [
            "annotation",
            "security",
            "type",
            "error",
            "structure",
            "language_rules",
        ]
    else:
        if check_annotation:
            checks.append("annotation")
        if check_security:
            checks.append("security")
        if check_type:
            checks.append("type")
        if check_error:
            checks.append("error")
        if check_structure:
            checks.append("structure")

    if not checks:
        checks = ["annotation", "security", "type", "error"]

    # Collect files to check
    files_to_check: list[Path] = []
    if path.is_file():
        files_to_check = [path]
    else:
        for ext in CODE_EXTENSIONS:
            files_to_check.extend(path.rglob(f"*{ext}"))

    # 跳过虚拟环境、依赖目录、构建产物与缓存目录
    skip_dir_parts = {
        "__pycache__",
        ".git",
        ".venv",
        "venv",
        "env",
        "node_modules",
        ".tox",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "dist",
        "build",
        "site-packages",
        ".eggs",
        ".coverage",
        # 抗原产物/独立子项目（各有独立校验与发布流程）
        "mutants",
        "site",
        "examples",
        "ai-dev-framework",
    }
    filtered_files = [f for f in files_to_check if not skip_dir_parts.intersection(f.parts)]

    if not filtered_files:
        return True, "No files to check"

    # Run checks on each file
    all_results: list[tuple[Path, dict[str, Any]]] = []
    for filepath in filtered_files:
        lang = detect_language_from_file(filepath)
        if not lang:
            continue
        # 测试代码允许 eval/exec/Any 等测试辅助模式：只做 AI 标注合规检查
        file_checks = ["annotation"] if "tests" in filepath.parts else checks
        result = check_file(filepath, file_checks)
        all_results.append((filepath, result))

    # 基线棘轮: 存量问题豁免，只拦截新增问题
    # - 基线不存在: 记录现状作为起点，本次保持严格判定
    #   （基线随仓库分发后，后续运行才开始豁免存量）
    # - 有新增问题: 失败，基线保持不变
    # - 无新增问题: 通过并用当前状态合并刷新基线（已修复的问题随之移出）
    # 任何基线机制自身的异常都不应阻断门禁，此时退回无基线行为
    # 基线默认放在项目根目录（基于模块位置定位，不受 cwd 影响），
    # 测试可通过 JCODE_QUALITY_BASELINE 环境变量指向临时目录实现隔离
    env_baseline = os.environ.get("JCODE_QUALITY_BASELINE")
    baseline_path = Path(env_baseline) if env_baseline else get_project_root() / ".jcode" / "baseline.json"
    original_results = list(all_results)
    existing_baseline = _load_issue_baseline(baseline_path)
    baseline_exempt = 0
    baseline_note = ""

    try:
        if existing_baseline is None:
            _save_issue_baseline(baseline_path, all_results)
            baseline_note = f"首次运行，已创建质量基线（本次按严格模式判定）: {baseline_path}"
        elif existing_baseline:
            filtered_results: list[tuple[Path, dict[str, Any]]] = []
            for filepath, r in all_results:
                base_counts = existing_baseline.get(str(filepath), {})
                cur_counts: dict[str, int] = {}
                kept_issues: list[dict[str, Any]] = []
                for issue in r["issues"]:
                    key = _issue_key(issue)
                    cur_counts[key] = cur_counts.get(key, 0) + 1
                    if cur_counts[key] <= base_counts.get(key, 0):
                        baseline_exempt += 1
                        continue
                    kept_issues.append(issue)
                new_r = {**r, "issues": kept_issues}
                if kept_issues:
                    new_r["passed"] = False
                elif not r["passed"] and r["issues"]:
                    new_r["passed"] = True
                filtered_results.append((filepath, new_r))
            all_results = filtered_results
            if baseline_exempt:
                baseline_note = f"基线豁免存量问题 {baseline_exempt} 个"
    except Exception as e:  # noqa: BLE001 - 基线失败时退回严格模式
        logger.warning("质量基线处理失败，退回无基线严格模式: %s", e)
        all_results = original_results
        baseline_note = ""

    passed_count = sum(1 for _, r in all_results if r["passed"])
    failed_count = len(all_results) - passed_count
    total_issues = sum(len(r["issues"]) for _, r in all_results)

    # 无新增问题时合并刷新基线，使已修复的存量问题移出基线（棘轮只紧不松）
    if failed_count == 0 and existing_baseline:
        try:
            _merge_issue_baseline(baseline_path, original_results, existing_baseline)
        except Exception as e:  # noqa: BLE001 - 刷新失败不影响本次结果
            logger.warning("质量基线刷新失败: %s", e)

    # Format output
    if format == "json":
        output = json.dumps(
            {
                "summary": {
                    "passed": passed_count,
                    "failed": failed_count,
                    "total_files": len(all_results),
                    "total_issues": total_issues,
                    "baseline_exempt": baseline_exempt,
                },
                "results": [{"file": str(f), **r} for f, r in all_results],
            },
            indent=2,
            ensure_ascii=False,
        )
    else:
        lines = []
        for filepath, result in all_results:
            if result["passed"]:
                lines.append(f"✅ {filepath}")
            else:
                lines.append(f"❌ {filepath} ({len(result['issues'])} issues)")
                for issue in result["issues"][:5]:
                    lines.append(f"   Line {issue['line']}: [{issue['type']}] {issue['message']}")
                if len(result["issues"]) > 5:
                    lines.append(f"   ... and {len(result['issues']) - 5} more")
        lines.append(f"\nSummary: {passed_count} passed, {failed_count} failed, {total_issues} issues")
        if baseline_note:
            lines.append(f"ℹ️  {baseline_note}")
        output = "\n".join(lines)

    # 记录到统一存储（任务7：复用检查历史，供 dashboard/趋势分析使用）
    try:
        from tools.scripts.rules_engine.store import get_connection, record_run

        record_run(
            get_connection(),
            {
                "summary": {
                    "total_files": len(all_results),
                    "errors": total_issues,
                    "warnings": 0,
                    "info": 0,
                    "passed": passed_count,
                    "failed": failed_count,
                },
                "results": [{"file": str(f), **r} for f, r in all_results],
            },
        )
    except Exception as e:  # 存储失败不影响检查结果
        logger.warning("记录质量检查历史失败: %s", e)

    return failed_count == 0, output


def _load_governance_auditor() -> Any:
    """Dynamically load the governance auditor module."""
    spec = importlib.util.spec_from_file_location(
        "governance_auditor",
        Path(__file__).resolve().parent.parent.parent.parent / ".jcode" / "scripts" / "governance-auditor.py",
    )
    if spec is None or spec.loader is None:
        raise ImportError("Failed to load governance_auditor module")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run_governance_audit(
    *,
    full: bool = False,
    validate_docs: bool = False,
    check_ai_sdlc: bool = False,
    audit_hallucination: bool = False,
    check_index: bool = False,
) -> tuple[bool, str]:
    """Run governance audit checks.

    Args:
        full: Run all governance checks.
        validate_docs: Validate governance docs.
        check_ai_sdlc: Check AI-SDLC compliance.
        audit_hallucination: Audit hallucination risks.
        check_index: Check index references.
    """
    ga = _load_governance_auditor()

    checks: list[tuple[str, Callable[[], bool]]] = []
    if full or validate_docs:
        checks.append(("Governance Docs", ga.validate_governance_docs))
    if full or check_ai_sdlc:
        checks.append(("AI-SDLC Compliance", ga.check_ai_sdlc_compliance))
    if full or audit_hallucination:
        checks.append(("Hallucination Risk", ga.audit_hallucination_risks))
    if check_index:

        def _check_index() -> bool:
            result = subprocess.run(
                [
                    sys.executable,
                    ".jcode/scripts/governance-docs-validator.py",
                    "check-index",
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            return result.returncode == 0

        checks.append(("Index References", _check_index))
    if full:
        checks = [
            ("Lint", ga.lint),
            ("Format", ga.format_check),
            ("Type Check", ga.typecheck),
            ("Test", ga.test),
            *checks,
        ]

    if not checks:
        checks = [
            ("Lint", ga.lint),
            ("Format", ga.format_check),
            ("Type Check", ga.typecheck),
            ("Test", ga.test),
            ("Governance Docs", ga.validate_governance_docs),
            ("AI-SDLC Compliance", ga.check_ai_sdlc_compliance),
        ]

    failed: list[str] = []
    output_lines: list[str] = []

    for name, func in checks:
        passed = func()
        status = "✅ PASS" if passed else "❌ FAIL"
        output_lines.append(f"  {status}: {name}")
        if not passed:
            failed.append(name)

    output = "\n".join(output_lines)
    if failed:
        output += f"\n\nFailed checks: {', '.join(failed)}"

    return len(failed) == 0, output


def run_pr_review() -> tuple[bool, str]:
    """Run automated AI PR review."""
    from tools.scripts.ai_pr_reviewer import (
        format_review_report,
        get_git_diff,
        review_diff,
    )

    diff = get_git_diff()
    res = review_diff(diff)
    report = format_review_report(res)
    return res["total_findings"] == 0, report


def run_arch_graph() -> tuple[bool, str]:
    """Run architecture dependency graph generation."""
    from tools.scripts.arch_visualizer import (
        generate_mermaid_diagram,
        scan_python_imports,
    )

    graph = scan_python_imports(Path("tools/scripts"))
    mermaid = generate_mermaid_diagram(graph)
    return (
        True,
        f"Architecture graph generated successfully ({len(graph)} modules mapped).\n\n```mermaid\n{mermaid}\n```",
    )

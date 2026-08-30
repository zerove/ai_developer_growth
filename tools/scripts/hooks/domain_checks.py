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
    baseline_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


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
    baseline_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_baseline_structure(baseline_path: Path) -> tuple[bool, str]:
    """校验基线文件结构合法性 (V2.21 P5-66 拆分: 抽 _load_baseline_json + _validate_baseline_metadata + _validate_baseline_files).

    防误编辑/篡改导致棘轮静默失效.
    合法格式: {"version": int, "files": {相对路径: {"type:message": 正整数}}}
    """
    data, err = _load_baseline_json(baseline_path)
    if err is not None:
        return False, err
    assert data is not None  # narrow type for mypy

    err = _validate_baseline_metadata(data)
    if err is not None:
        return False, err

    err = _validate_baseline_files(data["files"])
    if err is not None:
        return False, err

    files = data["files"]
    total = sum(sum(c.values()) for c in files.values())
    return True, f"基线合法: {len(files)} 个文件, {total} 个存量问题"


def _load_baseline_json(baseline_path: Path) -> tuple[dict[str, Any] | None, str | None]:
    """加载 + 解析 baseline JSON (模块级 helper).

    Args:
        baseline_path: 基线文件路径

    Returns:
        (data, None) 成功 或 (None, error_msg) 失败
    """
    if not baseline_path.exists():
        return None, f"基线文件不存在: {baseline_path}"
    try:
        return json.loads(baseline_path.read_text(encoding="utf-8")), None
    except (OSError, json.JSONDecodeError) as e:
        return None, f"基线文件不是合法 JSON: {e}"


def _validate_baseline_metadata(data: dict[str, Any]) -> str | None:
    """校验 version + files 顶层元数据 (模块级 helper).

    Args:
        data: baseline dict

    Returns:
        None 合法, 错误消息字符串 否则
    """
    if not isinstance(data, dict):
        return "顶层必须是对象"
    version = data.get("version")
    if not isinstance(version, int):
        return "缺少整数 version 字段"
    files = data.get("files")
    if not isinstance(files, dict):
        return "缺少 files 对象"
    return None


def _validate_baseline_files(files: dict[str, Any]) -> str | None:
    """校验 files 内每个条目 (模块级 helper).

    Args:
        files: baseline['files'] dict

    Returns:
        None 合法, 错误消息字符串 否则
    """
    for filepath, counts in files.items():
        if not isinstance(counts, dict) or not counts:
            return f"文件条目必须是非空对象: {filepath}"
        for key, count in counts.items():
            if not isinstance(key, str) or ":" not in key:
                return f"问题键必须是 'type:message' 格式: {key!r} ({filepath})"
            if not isinstance(count, int) or count < 1:
                return f"问题计数必须是正整数: {filepath} -> {key} = {count}"
    return None


def prune_stale_baseline_entries(baseline_path: Path) -> int:
    """清除指向已不存在文件的基线条目（全量刷新后调用）。

    返回删除的文件条目数。基线不存在或为空时返回 0。
    """
    try:
        data = json.loads(baseline_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return 0
    files = data.get("files", {})
    stale = [f for f in files if not Path(f).exists()]
    if not stale:
        return 0
    for f in stale:
        del files[f]
    data["files"] = files
    baseline_path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return len(stale)


# 跳过虚拟环境、依赖目录、构建产物与缓存目录
_SKIP_DIR_PARTS = {
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


def _collect_checkable_files(path: Path) -> list[Path]:
    """收集待检查的代码文件（供 run_quality_gate 与 baseline recompute 共用）。"""
    if path.is_file():
        return [path]
    files_to_check: list[Path] = []
    for ext in CODE_EXTENSIONS:
        files_to_check.extend(path.rglob(f"*{ext}"))
    return [f for f in files_to_check if not _SKIP_DIR_PARTS.intersection(f.parts)]


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


def _determine_checks(
    *,
    full: bool,
    check_annotation: bool,
    check_security: bool,
    check_type: bool,
    check_error: bool,
    check_structure: bool,
    check_patterns: bool,
) -> list[str]:
    """根据参数决定要运行的检查列表。

    ADR-016 拆分: 从 run_quality_gate (C=41) 抽出。
    """
    if full or check_patterns:
        return [
            "annotation",
            "security",
            "type",
            "error",
            "structure",
            "language_rules",
        ]
    checks: list[str] = []
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
        return ["annotation", "security", "type", "error"]
    return checks


def _apply_baseline_ratchet(
    all_results: list[tuple[Path, dict[str, Any]]],
    baseline_path: Path,
) -> tuple[list[tuple[Path, dict[str, Any]]], int, str]:
    """应用基线棘轮: 存量问题豁免，只拦截新增问题。

    Returns:
        - 过滤后的 results
        - 豁免数量
        - 备注信息

    ADR-016 拆分: 从 run_quality_gate 抽出。
    """
    filtered_results: list[tuple[Path, dict[str, Any]]] = list(all_results)
    existing_baseline = _load_issue_baseline(baseline_path)
    baseline_exempt = 0
    baseline_note = ""
    if existing_baseline is None:
        _save_issue_baseline(baseline_path, all_results)
        baseline_note = f"首次运行，已创建质量基线（本次按严格模式判定）: {baseline_path}"
        return filtered_results, baseline_exempt, baseline_note
    if not existing_baseline:
        return filtered_results, baseline_exempt, baseline_note
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
        filtered_results[filtered_results.index((filepath, r))] = (filepath, new_r)
    if baseline_exempt:
        baseline_note = f"基线豁免存量问题 {baseline_exempt} 个"
    return filtered_results, baseline_exempt, baseline_note


def _refresh_baseline_if_clean(
    original_results: list[tuple[Path, dict[str, Any]]],
    baseline_path: Path,
    existing_baseline: dict[str, Any] | None,
    full: bool,
) -> None:
    """无新增问题时合并刷新基线 (棘轮只紧不松)。

    ADR-016 拆分: 从 run_quality_gate 抽出。
    """
    if existing_baseline is None:
        return
    try:
        _merge_issue_baseline(baseline_path, original_results, existing_baseline)
        if full:
            pruned = prune_stale_baseline_entries(baseline_path)
            if pruned:
                logger.info("质量基线清理失效条目 %d 个", pruned)
    except Exception as e:  # noqa: BLE001 - 刷新失败不影响本次结果
        logger.warning("质量基线刷新失败: %s", e)


def _record_run_history(
    all_results: list[tuple[Path, dict[str, Any]]],
    passed_count: int,
    failed_count: int,
    total_issues: int,
) -> None:
    """记录运行历史到 store, 失败不影响检查结果。

    ADR-016 拆分: 从 run_quality_gate 抽出。
    """
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


def _format_output(
    all_results: list[tuple[Path, dict[str, Any]]],
    format: str,
    baseline_exempt: int,
    baseline_note: str,
) -> str:
    """格式化输出 (text 或 json)。

    ADR-016 拆分: 从 run_quality_gate 抽出。
    """
    passed_count = sum(1 for _, r in all_results if r["passed"])
    failed_count = len(all_results) - passed_count
    total_issues = sum(len(r["issues"]) for _, r in all_results)
    if format == "json":
        return json.dumps(
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
    lines: list[str] = []
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
    return "\n".join(lines)


def _resolve_baseline_path() -> Path:
    """解析基线文件路径 (env 覆盖或默认位置)。"""
    env_baseline = os.environ.get("JCODE_QUALITY_BASELINE")
    if env_baseline:
        return Path(env_baseline)
    return get_project_root() / ".jcode" / "baseline.json"


def _run_checks_on_files(
    files: list[Path],
    checks: list[str],
) -> list[tuple[Path, dict[str, Any]]]:
    """对每个文件运行检查, 跳过无法识别语言的文件。

    测试代码 (路径含 'tests') 只做 annotation 检查。

    ADR-016 拆分: 从 run_quality_gate 抽出。
    """
    results: list[tuple[Path, dict[str, Any]]] = []
    for filepath in files:
        lang = detect_language_from_file(filepath)
        if not lang:
            continue
        file_checks = ["annotation"] if "tests" in filepath.parts else checks
        result = check_file(filepath, file_checks)
        results.append((filepath, result))
    return results


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
    """Run AI Quality Gate checks (orchestrator).

    ADR-016 拆分: 从 C=41 / 182 行主函数拆出 7 个 helper。
    主函数仅负责编排, 行数 < 50。
    """
    checks = _determine_checks(
        full=full,
        check_annotation=check_annotation,
        check_security=check_security,
        check_type=check_type,
        check_error=check_error,
        check_structure=check_structure,
        check_patterns=check_patterns,
    )

    filtered_files = _collect_checkable_files(path)
    if not filtered_files:
        return True, "No files to check"

    all_results = _run_checks_on_files(filtered_files, checks)
    if not all_results:
        return True, "No files to check"

    baseline_path = _resolve_baseline_path()
    original_results = list(all_results)
    existing_baseline = _load_issue_baseline(baseline_path)

    all_results, baseline_exempt, baseline_note = _apply_baseline_ratchet(all_results, baseline_path)

    passed_count = sum(1 for _, r in all_results if r["passed"])
    failed_count = len(all_results) - passed_count
    total_issues = sum(len(r["issues"]) for _, r in all_results)

    if failed_count == 0:
        _refresh_baseline_if_clean(original_results, baseline_path, existing_baseline, full)

    output = _format_output(all_results, format, baseline_exempt, baseline_note)
    _record_run_history(all_results, passed_count, failed_count, total_issues)
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

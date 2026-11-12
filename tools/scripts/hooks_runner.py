#!/usr/bin/env python3
"""
统一 Hook 运行器 (CLI 入口) - 多语言版本

模块化拆分:
    - hooks/basic_checks.py    : lint, format, typecheck, test, security
    - hooks/domain_checks.py   : language-rules, quality-gate, governance-audit
    - hooks/incremental_checks.py : diff, pre-commit, git helpers

新增: 语言工具链支持 (via language_registry)
    - 自动检测项目语言
    - 使用语言对应的工具链运行检查
    - 支持多语言项目

用法:
    python hooks_runner.py lint [--lang python|typescript|...] [--path PATH]
    python hooks_runner.py format [--lang python|...] [--path PATH]
    python hooks_runner.py typecheck [--lang python|...] [--path PATH]
    python hooks_runner.py test [--lang python|...] [--path PATH]
    python hooks_runner.py security [--lang python|...] [--path PATH]
    python hooks_runner.py language-rules [--path PATH] [--lang LANG]
    python hooks_runner.py quality-gate [--path PATH] [--full] [--check-security] ...
    python hooks_runner.py governance-audit [--full] [--validate-docs] [--check-ai-sdlc] [--audit-hallucination]
    python hooks_runner.py diff [--base REF]  # Incremental: only check changed files
    python hooks_runner.py pre-commit        # Pre-commit hook: check staged files
    python hooks_runner.py full [--lang python,typescript] [--path PATH]
"""

from __future__ import annotations

import argparse
import importlib
import importlib.util
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


_FORWARDED_GROUPS: dict[str, tuple[str, ...]] = {
    "tools.scripts.hooks.basic_checks": (
        "run_format_check",
        "run_lint",
        "run_security",
        "run_tests",
        "run_typecheck",
    ),
    "tools.scripts.hooks.domain_checks": (
        "run_arch_graph",
        "run_governance_audit",
        "run_language_rules",
        "run_pr_review",
        "run_quality_gate",
    ),
    "tools.scripts.hooks.incremental_checks": (
        "get_changed_files",
        "get_staged_files",
        "run_diff_checks",
        "run_pre_commit_checks",
    ),
    "tools.scripts.hooks.misc_runner": (
        "_close_store_quietly",
        "_dep_graph_analyze",
        "_dep_graph_build",
        "_dep_graph_circular",
        "_dep_graph_conflicts",
        "_dep_graph_impact",
        "_emit_or_write",
        "_exception_check_expirations",
        "_exception_list",
        "_exception_request",
        "_exception_review",
        "_exception_sync_gitops",
        "_handle_dashboard",
        "_handle_db_maintain",
        "_handle_dep_graph",
        "_handle_docs_validate",
        "_handle_exception",
        "_handle_install_hooks",
        "_handle_learn",
        "_make_exception_manager",
    ),
    "tools.scripts.hooks.phase_runner": (
        "_print_results_in_order",
        "_resolve_order",
        "_resolve_phase_func",
        "_run_ast_fix",
        "_run_format_phase",
        "_run_full",
        "_run_governance_audit_full",
        "_run_hallucination_scan",
        "_run_lint_phase",
        "_run_parallel_checks",
        "_run_phase",
        "_run_quality_gate_full",
        "_run_security_phase",
        "_run_semantic_check",
        "_run_sequential_phases",
        "_run_test_phase",
        "_run_typecheck_phase",
    ),
    "tools.scripts.hooks.runner_parsers": (
        "_add_analysis_parsers",
        "_add_core_gate_parsers",
        "_add_dep_graph_parsers",
        "_add_doctor_baseline_parsers",
        "_add_exception_dep_parsers",
        "_add_extended_scan_parsers",
        "_add_security_parsers",
        "_add_signature_sbom_parsers",
        "_add_workflow_parsers",
        "_build_parser",
    ),
    "tools.scripts.hooks.supply_runner": (
        "_build_fix_orchestrator",
        "_check_dependency_freshness",
        "_collect_check_results",
        "_fix_result_dicts",
        "_handle_auto_fix",
        "_handle_sbom",
        "_handle_supply_chain",
        "_handle_supply_chain_compliance",
        "_handle_supply_chain_freshness",
        "_handle_supply_chain_sbom",
        "_handle_supply_chain_scan",
        "_handle_supply_chain_verify",
        "_handle_verify_signature",
        "_load_license_policy",
        "_output_compliance",
        "_output_scan_result",
        "_print_compliance_text",
        "_print_fix_text",
        "_print_freshness_text",
        "_print_scan_text",
        "_print_verify_text",
        "_run_compliance_checks",
        "_scan_has_failing_vulns",
        "_scan_severity_threshold",
        "_scan_vulnerability_dicts",
        "_severity_to_sarif_level",
        "_to_cyclonedx",
        "_to_sarif_supply_chain",
        "_to_spdx_tagvalue",
        "_verify_packages",
    ),
    "tools.scripts.hooks.tool_runner": (
        "_build_tool_command",
        "_count_language_files",
        "_detect_project_languages",
        "_excluded_scan_dirs",
        "_execute_tool",
        "_get_jobs_setting",
        "_parse_languages",
        "_run_basic_check_for_languages",
        "_run_format_multi",
        "_run_lint_multi",
        "_run_security_multi",
        "_run_simple",
        "_run_test_multi",
        "_run_tool_for_language",
        "_run_typecheck_multi",
        "_timeout_for_category",
        "_tool_available",
    ),
}

_FORWARDED: dict[str, tuple[str, str]] = {
    name: (module_name, name) for module_name, names in _FORWARDED_GROUPS.items() for name in names
}
_FORWARDED.update(
    {
        "_orig_run_format_check": ("tools.scripts.hooks.basic_checks", "run_format_check"),
        "_orig_run_lint": ("tools.scripts.hooks.basic_checks", "run_lint"),
        "_orig_run_security": ("tools.scripts.hooks.basic_checks", "run_security"),
        "_orig_run_tests": ("tools.scripts.hooks.basic_checks", "run_tests"),
        "_orig_run_typecheck": ("tools.scripts.hooks.basic_checks", "run_typecheck"),
    }
)


def __getattr__(name: str) -> Any:
    """按需解析历史转发符号（PEP 562）。"""
    try:
        module_name, attribute = _FORWARDED[name]
    except KeyError:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from None
    value = getattr(importlib.import_module(module_name), attribute)
    globals()[name] = value
    return value


def _resolve(name: str) -> Any:
    """经本模块解析符号，保留 monkeypatch 语义。"""
    return getattr(sys.modules[__name__], name)


from tools.scripts.language_registry import (  # noqa: E402
    Language,
)
from tools.scripts.quality_gate import run_quality_gate as run_quality_gate_new  # noqa: E402
from tools.scripts.rules_engine.models import CheckResult  # noqa: E402
from tools.scripts.secret_scanner import SecretScanResult, scan_secrets  # noqa: E402

logger = logging.getLogger(__name__)

# ─── Backward compatibility aliases for tests ───
# Tests patch these function names, so we provide aliases
# that delegate to the original implementations


def run_lint(fix: bool = False) -> tuple[bool, str]:
    """Backward compatibility alias for run_lint."""
    result: tuple[bool, str] = _resolve("_orig_run_lint")(fix)
    return result


def run_format_check(fix: bool = False) -> tuple[bool, str]:
    """Backward compatibility alias for run_format_check."""
    result: tuple[bool, str] = _resolve("_orig_run_format_check")(fix)
    return result


def run_typecheck() -> tuple[bool, str]:
    """Backward compatibility alias for run_typecheck."""
    result: tuple[bool, str] = _resolve("_orig_run_typecheck")()
    return result


def run_tests() -> tuple[bool, str]:
    """Backward compatibility alias for run_tests."""
    result: tuple[bool, str] = _resolve("_orig_run_tests")()
    return result


def run_security() -> tuple[bool, str]:
    """Backward compatibility alias for run_security."""
    result: tuple[bool, str] = _resolve("_orig_run_security")()
    return result

    # 新增: Supply Chain Security


# ─── 检查阶段数据定义 ──────────────────────────────────────
# 每个阶段: (名称, 函数名, 是否可并行, 依赖阶段)
# 函数名在运行时通过 globals() 解析，便于测试 mock 与配置化扩展
_CHECK_PHASES: list[tuple[str, str, bool, list[str]]] = [
    ("Lint", "_run_lint_phase", True, []),
    ("Format", "_run_format_phase", True, []),
    ("Type Check", "_run_typecheck_phase", True, []),
    ("Test Suite", "_run_test_phase", False, ["Type Check"]),
    ("Security Scan", "_run_security_phase", False, ["Test Suite"]),
    ("AI Quality Gate", "_run_quality_gate_full", False, ["Type Check"]),
    ("Governance Audit", "_run_governance_audit_full", False, []),
]

# 阶段名到 (函数名, 并行标记, 依赖) 的索引
_PHASE_INDEX: dict[str, tuple[str, bool, list[str]]] = {
    name: (func_name, parallel, deps) for name, func_name, parallel, deps in _CHECK_PHASES
}


# 全局变量存储 full 模式的参数
_full_args: argparse.Namespace | None = None


# 全局变量，供阶段函数使用
_full_langs: list[Language] = []
_full_path: Path = Path(".")


def _print_check_result(result: CheckResult) -> None:
    """Print a single check result if it has issues."""
    if result.issues:
        for issue in result.issues:
            severity_icon = {"error": "❌", "warning": "⚠️", "info": "ℹ️"}.get(issue.severity, "?")
            print(f"  {severity_icon} {result.file}:{issue.line} [{issue.rule_id}] {issue.message}")


def _language_rules_fix(args: argparse.Namespace) -> int:
    from tools.scripts.rules_engine.auto_fix import FAILED_WRITE_RULE_IDS, apply_fixes_to_directory, format_fix_results

    fix_results = apply_fixes_to_directory(args.path, dry_run=False)
    print(format_fix_results(fix_results))
    # ADR-072: 写盘失败/拒绝写盘必须非零退出；MANUAL FIX REQUIRED 是正常产物。
    return 1 if any(r.rule_id in FAILED_WRITE_RULE_IDS for r in fix_results) else 0


def _language_rules_cache(args: argparse.Namespace) -> int:
    from tools.scripts.app_config import get_path, get_setting
    from tools.scripts.rules_engine.checker import check_directory

    jobs: int = int(str(getattr(args, "jobs", None) or get_setting("jobs", 4)))
    db_path = getattr(args, "db", None) or str(get_path("trend_db", Path("adg_quality.db")))
    stats: dict[str, Any] = {}
    results = check_directory(args.path, jobs=jobs, use_cache=True, db_path=db_path, stats=stats)
    passed = all(r.passed for r in results)
    if getattr(args, "format", "text") == "json":
        meta: dict[str, Any] = {
            "files_checked": int(stats.get("files_checked", len(results))),
            "cache": True,
            "use_cache": bool(stats.get("use_cache", True)),
            "cache_supported": bool(stats.get("cache_supported", True)),
            "cache_engine": stats.get("cache_engine"),
            "cache_reason": stats.get("cache_reason"),
            "cache_initialized": bool(stats.get("cache_initialized", False)),
            "cache_degraded": stats.get("cache_degraded"),
            "cache_hits": stats.get("cache_hits"),
            "cache_misses": stats.get("cache_misses"),
            "cache_hit_rate": stats.get("cache_hit_rate"),
            "parallel": bool(stats.get("parallel", False)),
            "jobs": int(stats.get("jobs", jobs)),
            "db_path": db_path,
        }
        payload = {
            "passed": passed,
            "path": str(args.path),
            "files_checked": len(results),
            "results": [{"file": r.file, "passed": r.passed, "issues": len(r.issues)} for r in results],
            "meta": meta,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        lines = [f"{r.file}: {'PASS' if r.passed else 'FAIL'} ({len(r.issues)} issues)" for r in results]
        print("\n".join(lines) if lines else "No files to check")
    return 0 if passed else 1


def _handle_language_rules(args: argparse.Namespace) -> int:
    """Handle language-rules command."""
    if getattr(args, "fix", False):
        return _language_rules_fix(args)
    if getattr(args, "cache", False):
        return _language_rules_cache(args)
    return _resolve("_run_simple")(
        _resolve("run_language_rules")(args.path, args.lang, getattr(args, "format", "text"))
    )


def _handle_quality_gate(args: argparse.Namespace) -> int:
    """Handle quality-gate command."""
    return _resolve("_run_simple")(
        _resolve("run_quality_gate")(
            args.path,
            full=args.full,
            check_annotation=args.check_annotation,
            check_security=args.check_security,
            check_type=args.check_type,
            check_error=args.check_error,
            check_structure=args.check_structure,
            check_patterns=args.check_patterns,
            format=args.format,
        )
    )


def _handle_governance_audit(args: argparse.Namespace) -> int:
    """Handle governance-audit command."""
    return _resolve("_run_simple")(
        _resolve("run_governance_audit")(
            full=args.full,
            validate_docs=args.validate_docs,
            check_ai_sdlc=args.check_ai_sdlc,
            audit_hallucination=args.audit_hallucination,
            check_index=args.check_index,
        )
    )


def _check_pre_commit_hook() -> tuple[bool, str]:
    """检查 .git/hooks/pre-commit 是否健康（本次会话曾因环境损坏阻断提交）。"""
    hook = Path(".git/hooks/pre-commit")
    if not hook.exists():
        return True, "pre-commit 钩子未安装（跳过）"
    text = hook.read_text(encoding="utf-8", errors="replace")
    # pre-commit 生成脚本头部声明 INSTALL_PYTHON
    install_python: Path | None = None
    for line in text.splitlines():
        if line.startswith("INSTALL_PYTHON="):
            install_python = Path(line.split("=", 1)[1].strip())
            break
    if install_python is None:
        return True, "非 pre-commit 生成的钩子（跳过环境校验）"
    if not install_python.is_file():
        return False, (
            f"pre-commit 钩子指向不存在的 Python: {install_python}；"
            f"修复: mise install python 或 pre-commit uninstall && pre-commit install"
        )
    try:
        probe = subprocess.run(
            [str(install_python), "-m", "pre_commit", "--version"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        return False, f"pre-commit 探测失败: {e}"
    if probe.returncode != 0:
        return False, f"{install_python} 缺少 pre_commit 模块；修复: {install_python} -m pip install pre-commit"
    return True, f"pre-commit 健康 ({install_python})"


def _check_tool_available(cmd: list[str], name: str, required: bool, hint: str = "") -> tuple[bool, str, bool]:
    """探测外部工具可用性。返回 (通过, 描述, 是否必需)。"""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
        )
        ok = result.returncode == 0
    except (subprocess.TimeoutExpired, OSError):
        ok = False
    desc = f"{'✅' if ok else ('❌' if required else '⚠️ ')} {name}"
    if not ok and hint:
        desc += f" ({hint})"
    return ok or not required, desc, required


def _doctor_check_toolchain(checks: list[tuple[bool, str, bool]]) -> None:
    """检查外部工具链可用性并打印结果（仅必需项缺失才使门禁失败）。

    required 必须与实际门禁用法一致：security 检查中 pip-audit 是 `|| true`
    可选降级，若在此标为必需会导致 doctor 在完全健康的机器上返回非零——
    监控工具误报会使人开始忽略它，比不监控更糟。
    """
    tools_to_check: list[tuple[list[str], str, bool, str]] = [
        ([sys.executable, "-m", "ruff", "--version"], "ruff", True, "pip install ruff"),
        ([sys.executable, "-m", "mypy", "--version"], "mypy", True, "pip install mypy"),
        ([sys.executable, "-m", "pytest", "--version"], "pytest", True, "pip install pytest"),
        (["bandit", "--version"], "bandit", True, "pip install bandit"),
        (
            ["pip-audit", "--version"],
            "pip-audit",
            False,
            "pip install pip-audit (可选，未安装时 security 门禁降级跳过)",
        ),
    ]
    for cmd, name, required, hint in tools_to_check:
        ok, desc, req = _check_tool_available(cmd, name, required, hint)
        checks.append((ok, desc, req))
        print(desc)


def _doctor_check_plugins() -> None:
    """检查 pytest 加速插件（可选，缺失自动降级）。"""
    for module, label in [
        ("xdist", "pytest-xdist (并行测试)"),
        ("pytest_rerunfailures", "pytest-rerunfailures (flaky 重试)"),
        ("pytest_cov", "pytest-cov (覆盖率门禁)"),
    ]:
        try:
            # 用 find_spec 判存在性: 比 __import__ 更轻（不执行模块顶层代码）,
            # 也不会被项目自定义安全规则 sec-001 (动态执行入口) 命中。
            if importlib.util.find_spec(module) is None:
                raise ImportError(module)
            print(f"✅ {label}")
        except (ImportError, ValueError):
            print(f"⚠️  {label} 未安装，将自动降级")


def _doctor_check_hooks_json(root: Path, checks: list[tuple[bool, str, bool]]) -> None:
    """检查 hooks.json 可解析性。"""
    hooks_json = root / ".jcode" / "hooks.json"
    try:
        json.loads(hooks_json.read_text(encoding="utf-8"))
        hooks_ok = True
        hooks_desc = "✅ hooks.json 可解析"
    except Exception as e:  # noqa: BLE001 - 自检需要捕获全部异常并报告
        hooks_ok = False
        hooks_desc = f"❌ hooks.json 解析失败: {e}"
    checks.append((hooks_ok, "hooks.json", True))
    print(hooks_desc)


def _handle_doctor(args: argparse.Namespace) -> int:
    """门禁健康自检: 校验钩子环境、工具链、pytest 插件与基线完整性。

    必需项缺失返回 1（CI 应失败），可选项缺失仅警告。
    """
    root = args.path
    checks: list[tuple[bool, str, bool]] = []

    print("=" * 60)
    print("  HOOKS DOCTOR - 门禁环境自检")
    print("=" * 60)

    # 1. git 仓库
    git_ok = (root / ".git").exists()
    checks.append((git_ok, "git 仓库" if git_ok else "❌ 不是 git 仓库", True))
    print(f"{'✅' if git_ok else '❌'} git 仓库: {root}")

    # 2. pre-commit 钩子健康
    pc_ok, pc_desc = _check_pre_commit_hook()
    checks.append((pc_ok, "pre-commit 钩子", False))
    print(f"{'✅' if pc_ok else '❌'} {pc_desc}")

    # 3-4. 工具链与插件
    _doctor_check_toolchain(checks)
    _doctor_check_plugins()

    # 5. 基线文件结构校验
    from tools.scripts.hooks.domain_checks import validate_baseline_structure

    baseline_file = root / ".jcode" / "baseline.json"
    bl_ok, bl_desc = validate_baseline_structure(baseline_file)
    checks.append((bl_ok, "质量基线文件", True))
    print(f"{'✅' if bl_ok else '❌'} 质量基线: {bl_desc}")

    # 6. hooks.json 可解析
    _doctor_check_hooks_json(root, checks)

    failed_required = [d for ok, d, req in checks if not ok and req]
    print("=" * 60)
    if failed_required:
        print(f"❌ DOCTOR: {len(failed_required)} 项必需检查未通过")
        for d in failed_required:
            print(f"   - {d}")
        print("=" * 60)
        return 1
    print("✅ DOCTOR: 全部必需检查通过")
    print("=" * 60)
    return 0


def _handle_ci_heartbeat(args: argparse.Namespace) -> int:
    """探测远端 CI 是否真的执行过 job（ADR-057）。

    与 doctor 的区别：doctor 检查本地工具链，ci-heartbeat 检查门禁本身
    是否还活着。必须运行在 CI 之外——配额耗尽时 CI 内的检测器会一并死亡。
    """
    argv = ["--workflow", args.workflow, "--stale-hours", str(args.stale_hours)]
    if args.repo:
        argv += ["--repo", args.repo]
    if args.json:
        argv.append("--json")
    if args.alert:
        argv.append("--alert")
    from tools.scripts.ci_heartbeat import main as heartbeat_main

    return heartbeat_main(argv)


def _baseline_file_for(path: Path, explicit: Path | None) -> Path:
    """解析基线文件路径（显式参数优先，否则项目根目录默认值）。"""
    if explicit is not None:
        return explicit
    return path.resolve() / ".jcode" / "baseline.json"


def _handle_baseline_validate(args: argparse.Namespace) -> int:
    """基线结构校验（快速，供 CI 与本地使用）。"""
    from tools.scripts.hooks.domain_checks import validate_baseline_structure

    baseline_file = _baseline_file_for(Path("."), args.file)
    ok, desc = validate_baseline_structure(baseline_file)
    print(("✅" if ok else "❌") + " " + desc)
    return 0 if ok else 1


def _count_current_issues(project_root: Path) -> dict[str, dict[str, int]]:
    """用与 run_quality_gate(full=True) 相同的规则重算当前问题计数（不写基线）。"""
    from tools.scripts.ai_quality_gate import check_file
    from tools.scripts.hooks import domain_checks as dc
    from tools.scripts.validate_language_rules import detect_language_from_file

    # 与 run_quality_gate(full=True) 的 checks 列表严格一致，否则重算会误报
    file_checks = ["annotation", "security", "type", "error", "structure", "language_rules"]
    counts: dict[str, dict[str, int]] = {}
    for filepath in dc._collect_checkable_files(project_root):  # noqa: SLF001 - 同包内复用
        if not detect_language_from_file(filepath):
            continue
        # 与 run_quality_gate 一致: 测试文件只做标注检查
        effective = ["annotation"] if "tests" in filepath.parts else file_checks
        result = check_file(filepath, effective)
        issue_counts = dc._count_issues(result["issues"])  # noqa: SLF001 - 同包内复用
        if issue_counts:
            counts[str(filepath)] = issue_counts
    return counts


def _compare_baseline_with_current(
    baseline_counts: dict[str, dict[str, int]],
    current: dict[str, dict[str, int]],
) -> list[str]:
    """逐文件对比基线与重算结果，返回不一致描述列表。"""
    problems: list[str] = []
    all_files = set(baseline_counts) | set(current)
    for filepath in sorted(all_files):
        b_counts = baseline_counts.get(filepath, {})
        c_counts = current.get(filepath, {})
        for key in set(b_counts) | set(c_counts):
            b, c = b_counts.get(key, 0), c_counts.get(key, 0)
            if c > b:
                problems.append(f"{filepath}: {key} 实际 {c} > 基线 {b}（新增存量未入基线）")
            elif b > c:
                problems.append(f"{filepath}: {key} 基线 {b} > 实际 {c}（基线过松，应刷新）")
    return problems


def _handle_baseline_recompute(args: argparse.Namespace) -> int:
    """重算当前问题数并与基线对比（CI 防篡改校验）。

    - 基线计数 < 重算计数: 存量问题增加但基线未更新 → 失败
      （正常开发中这会被棘轮拦截，此处兜底防绕过）
    - 基线计数 > 重算计数: 基线过松 → 失败（防止人为放宽）
    """
    from tools.scripts.hooks.domain_checks import validate_baseline_structure

    baseline_file = _baseline_file_for(Path("."), args.file)

    ok, desc = validate_baseline_structure(baseline_file)
    if not ok:
        print(f"❌ 基线校验失败: {desc}")
        return 1

    data = json.loads(baseline_file.read_text(encoding="utf-8"))
    baseline_counts: dict[str, dict[str, int]] = data["files"]

    # 注意: 必须用相对路径收集（与本地 quality-gate --full 生成基线时的键一致），
    # 绝对路径会导致与基线条目全部错位
    current = _count_current_issues(args.path)

    baseline_total = sum(sum(c.values()) for c in baseline_counts.values())
    current_total = sum(sum(c.values()) for c in current.values())
    print(f"   基线存量: {baseline_total} ({len(baseline_counts)} 文件)")
    print(f"   当前实际: {current_total} ({len(current)} 文件)")

    problems = _compare_baseline_with_current(baseline_counts, current)

    if problems:
        print(f"\n❌ 基线与现状不一致 ({len(problems)} 处):")
        for p in problems[:20]:
            print(f"   - {p}")
        if len(problems) > 20:
            print(f"   ... 共 {len(problems)} 处")
        print("\n修复: 本地运行 quality-gate --full 刷新基线后提交")
        return 1

    print("\n✅ 基线与代码现状一致")
    return 0


def _print_secret_text(result: SecretScanResult) -> None:
    """打印 secret 扫描 text 格式结果.

    V2.17 P2-3 拆分: 从 _handle_secret_scan (C=13) 抽出.
    """
    if result.findings:
        print(f"❌ Found {len(result.findings)} secret(s):")
        for f in result.findings:
            print(f"  [{f.severity.upper()}] {f.tool}:{f.rule_id} in {f.file}:{f.line}")
            if f.secret:
                print(f"    Secret: {f.secret[:50]}...")
    else:
        print("✅ No secrets found")
    print(f"\nScanned in {result.scan_duration_ms}ms using {', '.join(result.tools_used)}")
    if result.errors:
        print(f"Errors: {', '.join(result.errors)}")


def _output_secret_result(result: SecretScanResult, args: argparse.Namespace) -> None:
    """根据 format 输出 secret 扫描结果到 stdout.

    V2.17 P2-3 拆分: 从 _handle_secret_scan (C=13) 抽出.
    """
    if args.format == "text":
        _print_secret_text(result)
    elif args.format == "json" and not args.output:
        print(result.to_json())
    elif args.format == "sarif" and not args.output:
        import json

        print(json.dumps(result.to_sarif(), indent=2))


def _handle_secret_scan(args: argparse.Namespace) -> int:
    """Handle secret-scan command (orchestrator).

    V2.17 P2-3 拆分: 从 C=13 / 60 行拆出 2 个输出 helper.
    """
    tools = None
    if args.tools:
        tools = [t.strip() for t in args.tools.split(",")]

    result = scan_secrets(
        args.path,
        tools=tools,
        scan_workspace=args.workspace,
        scan_git_history=args.history,
        scan_pr_diff=args.pr_diff,
        output_format=args.format,
        output_file=args.output,
    )

    _output_secret_result(result, args)
    if result.findings:
        return 1
    # 工具缺失时扫描返回 0 条findings。若不区分, "没扫到" 会被当成 "干净",
    # 即扫描器静默失效反而让门禁通过 (fail-open)。
    if not result.tools_used:
        print(f"❌ 无任何密钥扫描工具可用, 扫描结果不可信: {', '.join(result.errors) or '未知原因'}")
        return 1
    return 0


def _handle_quality_gate_new(args: argparse.Namespace) -> int:
    """Handle quality-gate-new command."""
    # 首先运行规则引擎检查获取 CheckResult
    from tools.scripts.app_config import get_setting
    from tools.scripts.rules_engine.checker import check_directory

    jobs = getattr(args, "jobs", None) or int(str(get_setting("jobs", 4)))
    results = check_directory(args.path, jobs=jobs, semantic=False)

    # 加载基线
    baseline = None
    if args.baseline:
        from pathlib import Path

        baseline_path = Path(args.baseline)
        if baseline_path.exists():
            import json

            with open(baseline_path) as f:
                baseline = json.load(f)

    # 运行质量门禁
    report = run_quality_gate_new(
        results,
        gate_name=args.gate,
        baseline=baseline,
        output_format=args.format,
        output_file=args.output,
    )
    # 必须传播门禁结论: 此前无条件 return 0, 使该命令永远不会失败。
    return 0 if report.overall_passed else 1


# 基础检查命令 → 可 mock 别名函数名（测试通过 globals() patch 这些名字）
_SIMPLE_COMMANDS = {
    "lint": "run_lint",
    "format": "run_format_check",
    "typecheck": "run_typecheck",
    "test": "run_tests",
    "security": "run_security",
}

# 多语言版本命令（显式指定 --lang 时使用）
_MULTI_COMMANDS = {
    "lint": "_run_lint_multi",
    "format": "_run_format_multi",
    "typecheck": "_run_typecheck_multi",
    "test": "_run_test_multi",
    "security": "_run_security_multi",
}


def _build_handlers() -> dict[str, Callable[[argparse.Namespace], int]]:
    """构建命令处理器注册表（从 _dispatch 拆出以控制函数长度）。"""
    return {
        "doctor": _handle_doctor,
        "ci-heartbeat": _handle_ci_heartbeat,
        "baseline": lambda a: (
            _handle_baseline_validate(a) if a.baseline_action == "validate" else _handle_baseline_recompute(a)
        ),
        "language-rules": _handle_language_rules,
        "quality-gate": _handle_quality_gate,
        "quality-gate-new": _handle_quality_gate_new,
        "governance-audit": _handle_governance_audit,
        "secret-scan": _handle_secret_scan,
        "auto-fix": _resolve("_handle_auto_fix"),
        "supply-chain": _resolve("_handle_supply_chain"),
        "sbom": _resolve("_handle_sbom"),
        "verify-signature": _resolve("_handle_verify_signature"),
        "diff": lambda a: _resolve("_run_simple")(_resolve("run_diff_checks")(a.base)),
        "pre-commit": lambda a: _resolve("_run_simple")(_resolve("run_pre_commit_checks")()),
        "pr-review": lambda a: _resolve("_run_simple")(_resolve("run_pr_review")()),
        "arch-graph": lambda a: _resolve("_run_simple")(_resolve("run_arch_graph")()),
        "semantic-check": lambda a: _resolve("_run_semantic_check")(
            a.path,
            getattr(a, "lang", None),
            getattr(a, "jobs", None) or _resolve("_get_jobs_setting")(),
        ),
        "ast-fix": lambda a: _resolve("_run_ast_fix")(a.path, getattr(a, "dry_run", False)),
        "hallucination-scan": lambda a: _resolve("_run_hallucination_scan")(
            getattr(a, "path", Path(".")),
            getattr(a, "lang", None),
        ),
        "install-hooks": _resolve("_handle_install_hooks"),
        "learn": _resolve("_handle_learn"),
        "dashboard": _resolve("_handle_dashboard"),
        "db-maintain": _resolve("_handle_db_maintain"),
        "docs-validate": _resolve("_handle_docs_validate"),
        "exception": _resolve("_handle_exception"),
        "dep-graph": _resolve("_handle_dep_graph"),
        "full": lambda a: _resolve("_run_full")(a),
    }


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to the appropriate handler."""
    cmd = args.command

    # 增量测试: 只跑受变更影响的测试（PR 级时间预算）
    if cmd == "test" and getattr(args, "incremental", False) and not getattr(args, "lang", None):
        from tools.scripts.hooks.basic_checks import run_tests_incremental

        return _resolve("_run_simple")(lambda: run_tests_incremental(args.base))

    if cmd in _SIMPLE_COMMANDS:
        func = _resolve(_SIMPLE_COMMANDS[cmd])
        if cmd in ("lint", "format") and getattr(args, "fix", False):
            return _resolve("_run_simple")(lambda: func(fix=True))
        return _resolve("_run_simple")(func)

    # 多语言版本命令（显式指定 --lang 时使用）
    multi_commands = _MULTI_COMMANDS

    # 如果显式指定了 --lang，使用多语言版本
    if cmd in multi_commands and getattr(args, "lang", None):
        return _resolve("_run_simple")(_resolve(multi_commands[cmd])(args))

    handler = _build_handlers().get(cmd)
    if handler:
        return handler(args)

    print(f"Unknown command: {cmd}")
    return 1


def main() -> int:
    parser = _resolve("_build_parser")()
    args = parser.parse_args()
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())

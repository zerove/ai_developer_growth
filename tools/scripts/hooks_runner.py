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
import json
import logging
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

# 阶段函数通过名称字符串运行时解析（_CHECK_PHASES / _resolve_phase_func），
# 必须在模块命名空间中存在
from tools.scripts.hooks.basic_checks import (  # noqa: F401
    run_format_check as _orig_run_format_check,
)
from tools.scripts.hooks.basic_checks import (
    run_lint as _orig_run_lint,
)
from tools.scripts.hooks.basic_checks import (
    run_security as _orig_run_security,
)
from tools.scripts.hooks.basic_checks import (
    run_tests as _orig_run_tests,
)
from tools.scripts.hooks.basic_checks import (
    run_typecheck as _orig_run_typecheck,
)
from tools.scripts.hooks.domain_checks import (  # noqa: F401
    run_arch_graph,
    run_governance_audit,
    run_language_rules,
    run_pr_review,
    run_quality_gate,
)
from tools.scripts.hooks.incremental_checks import (  # noqa: F401
    get_changed_files,
    get_staged_files,
    run_diff_checks,
    run_pre_commit_checks,
)
from tools.scripts.hooks.misc_runner import (  # noqa: F401 - 拆分后转发
    _close_store_quietly,
    _dep_graph_analyze,
    _dep_graph_build,
    _dep_graph_circular,
    _dep_graph_conflicts,
    _dep_graph_impact,
    _emit_or_write,
    _exception_check_expirations,
    _exception_list,
    _exception_request,
    _exception_review,
    _exception_sync_gitops,
    _handle_dashboard,
    _handle_db_maintain,
    _handle_dep_graph,
    _handle_docs_validate,
    _handle_exception,
    _handle_install_hooks,
    _handle_learn,
    _make_exception_manager,
)
from tools.scripts.hooks.phase_runner import (  # noqa: F401 - 拆分后转发
    _print_results_in_order,
    _resolve_order,
    _resolve_phase_func,
    _run_ast_fix,
    _run_format_phase,
    _run_full,
    _run_governance_audit_full,
    _run_hallucination_scan,
    _run_lint_phase,
    _run_parallel_checks,
    _run_phase,
    _run_quality_gate_full,
    _run_security_phase,
    _run_semantic_check,
    _run_sequential_phases,
    _run_test_phase,
    _run_typecheck_phase,
)
from tools.scripts.hooks.runner_parsers import (  # noqa: F401 - 拆分后转发
    _add_analysis_parsers,
    _add_core_gate_parsers,
    _add_dep_graph_parsers,
    _add_doctor_baseline_parsers,
    _add_exception_dep_parsers,
    _add_extended_scan_parsers,
    _add_security_parsers,
    _add_signature_sbom_parsers,
    _add_workflow_parsers,
    _build_parser,
)
from tools.scripts.hooks.supply_runner import (  # noqa: F401 - 拆分后转发, 保持命令入口
    _build_fix_orchestrator,
    _check_dependency_freshness,
    _collect_check_results,
    _fix_result_dicts,
    _handle_auto_fix,
    _handle_sbom,
    _handle_supply_chain,
    _handle_supply_chain_compliance,
    _handle_supply_chain_freshness,
    _handle_supply_chain_sbom,
    _handle_supply_chain_scan,
    _handle_supply_chain_verify,
    _handle_verify_signature,
    _load_license_policy,
    _output_compliance,
    _output_scan_result,
    _print_compliance_text,
    _print_fix_text,
    _print_freshness_text,
    _print_scan_text,
    _print_verify_text,
    _run_compliance_checks,
    _scan_has_failing_vulns,
    _scan_severity_threshold,
    _scan_vulnerability_dicts,
    _severity_to_sarif_level,
    _to_cyclonedx,
    _to_sarif_supply_chain,
    _to_spdx_tagvalue,
    _verify_packages,
)
from tools.scripts.hooks.tool_runner import (  # noqa: F401 - 拆分后转发
    _build_tool_command,
    _count_language_files,
    _detect_project_languages,
    _excluded_scan_dirs,
    _execute_tool,
    _get_jobs_setting,
    _parse_languages,
    _run_basic_check_for_languages,
    _run_format_multi,
    _run_lint_multi,
    _run_security_multi,
    _run_simple,
    _run_test_multi,
    _run_tool_for_language,
    _run_typecheck_multi,
    _timeout_for_category,
    _tool_available,
)
from tools.scripts.language_registry import (
    Language,
)
from tools.scripts.quality_gate import run_quality_gate as run_quality_gate_new
from tools.scripts.rules_engine.models import CheckResult
from tools.scripts.secret_scanner import scan_secrets

logger = logging.getLogger(__name__)

# ─── Backward compatibility aliases for tests ───
# Tests patch these function names, so we provide aliases
# that delegate to the original implementations


def run_lint() -> tuple[bool, str]:
    """Backward compatibility alias for run_lint."""
    return _orig_run_lint()


def run_format_check() -> tuple[bool, str]:
    """Backward compatibility alias for run_format_check."""
    return _orig_run_format_check()


def run_typecheck() -> tuple[bool, str]:
    """Backward compatibility alias for run_typecheck."""
    return _orig_run_typecheck()


def run_tests() -> tuple[bool, str]:
    """Backward compatibility alias for run_tests."""
    return _orig_run_tests()


def run_security() -> tuple[bool, str]:
    """Backward compatibility alias for run_security."""
    return _orig_run_security()

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


def _handle_language_rules(args: argparse.Namespace) -> int:
    """Handle language-rules command."""
    from tools.scripts.app_config import get_path, get_setting

    if getattr(args, "fix", False):
        from tools.scripts.rules_engine.auto_fix import (
            apply_fixes_to_directory,
            format_fix_results,
        )

        fix_results = apply_fixes_to_directory(args.path, dry_run=False)
        print(format_fix_results(fix_results))
        return 0
    if getattr(args, "cache", False):
        # 增量缓存模式：复用统一存储中的检查历史（mtime+size 未变则跳过）
        from tools.scripts.rules_engine.checker import check_directory

        jobs: int = int(str(getattr(args, "jobs", None) or get_setting("jobs", 4)))
        # 注意必须走 get_path（展开 ~），get_setting 返回字面量 "~/.cache/..." 会导致
        # sqlite3.connect 无法建库，缓存静默失效（历史 bug：check_cache 恒 0 行）
        db_path = getattr(args, "db", None) or str(get_path("trend_db", Path("adg_quality.db")))
        results = check_directory(args.path, jobs=jobs, use_cache=True, db_path=db_path)
        passed = all(r.passed for r in results)
        lines = [f"{r.file}: {'PASS' if r.passed else 'FAIL'} ({len(r.issues)} issues)" for r in results]
        print("\n".join(lines) if lines else "No files to check")
        return 0 if passed else 1
    return _run_simple(run_language_rules(args.path, args.lang))


def _handle_quality_gate(args: argparse.Namespace) -> int:
    """Handle quality-gate command."""
    return _run_simple(
        run_quality_gate(
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
    return _run_simple(
        run_governance_audit(
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


def _doctor_check_toolchain(checks: list[tuple[bool, str]]) -> None:
    """检查外部工具链可用性并打印结果（必需项缺失则门禁失败）。"""
    tools_to_check: list[tuple[list[str], str, bool, str]] = [
        (["ruff", "--version"], "ruff", True, "pip install ruff"),
        ([sys.executable, "-m", "mypy", "--version"], "mypy", True, "pip install mypy"),
        ([sys.executable, "-m", "pytest", "--version"], "pytest", True, "pip install pytest"),
        (["bandit", "--version"], "bandit", True, "pip install bandit"),
        (["pip-audit", "--version"], "pip-audit", True, "pip install pip-audit"),
    ]
    for cmd, name, required, hint in tools_to_check:
        ok, desc, _ = _check_tool_available(cmd, name, required, hint)
        checks.append((ok, desc))
        print(desc)


def _doctor_check_plugins() -> None:
    """检查 pytest 加速插件（可选，缺失自动降级）。"""
    for module, label in [
        ("xdist", "pytest-xdist (并行测试)"),
        ("pytest_rerunfailures", "pytest-rerunfailures (flaky 重试)"),
        ("pytest_cov", "pytest-cov (覆盖率门禁)"),
    ]:
        try:
            __import__(module)
            print(f"✅ {label}")
        except ImportError:
            print(f"⚠️  {label} 未安装，将自动降级")


def _doctor_check_hooks_json(root: Path, checks: list[tuple[bool, str]]) -> None:
    """检查 hooks.json 可解析性。"""
    hooks_json = root / ".jcode" / "hooks.json"
    try:
        json.loads(hooks_json.read_text(encoding="utf-8"))
        hooks_ok = True
        hooks_desc = "✅ hooks.json 可解析"
    except Exception as e:  # noqa: BLE001 - 自检需要捕获全部异常并报告
        hooks_ok = False
        hooks_desc = f"❌ hooks.json 解析失败: {e}"
    checks.append((hooks_ok, "hooks.json"))
    print(hooks_desc)


def _handle_doctor(args: argparse.Namespace) -> int:
    """门禁健康自检: 校验钩子环境、工具链、pytest 插件与基线完整性。

    必需项缺失返回 1（CI 应失败），可选项缺失仅警告。
    """
    root = args.path
    checks: list[tuple[bool, str]] = []

    print("=" * 60)
    print("  HOOKS DOCTOR - 门禁环境自检")
    print("=" * 60)

    # 1. git 仓库
    git_ok = (root / ".git").exists()
    checks.append((git_ok, "git 仓库" if git_ok else "❌ 不是 git 仓库"))
    print(f"{'✅' if git_ok else '❌'} git 仓库: {root}")

    # 2. pre-commit 钩子健康
    pc_ok, pc_desc = _check_pre_commit_hook()
    checks.append((pc_ok, "pre-commit 钩子"))
    print(f"{'✅' if pc_ok else '❌'} {pc_desc}")

    # 3-4. 工具链与插件
    _doctor_check_toolchain(checks)
    _doctor_check_plugins()

    # 5. 基线文件结构校验
    from tools.scripts.hooks.domain_checks import validate_baseline_structure

    baseline_file = root / ".jcode" / "baseline.json"
    bl_ok, bl_desc = validate_baseline_structure(baseline_file)
    checks.append((bl_ok, "质量基线文件"))
    print(f"{'✅' if bl_ok else '❌'} 质量基线: {bl_desc}")

    # 6. hooks.json 可解析
    _doctor_check_hooks_json(root, checks)

    failed_required = [d for ok, d in checks if not ok]
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


def _handle_secret_scan(args: argparse.Namespace) -> int:
    """Handle secret-scan command."""
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

    # 打印结果
    if args.format == "text":
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
    elif args.format == "json" and not args.output:
        print(result.to_json())
    elif args.format == "sarif" and not args.output:
        import json

        print(json.dumps(result.to_sarif(), indent=2))

    return 0 if len(result.findings) == 0 else 1


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
    run_quality_gate_new(
        results,
        gate_name=args.gate,
        baseline=baseline,
        output_format=args.format,
        output_file=args.output,
    )
    return 0


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
    "lint": _run_lint_multi,
    "format": _run_format_multi,
    "typecheck": _run_typecheck_multi,
    "test": _run_test_multi,
    "security": _run_security_multi,
}


def _build_handlers() -> dict[str, Callable[[argparse.Namespace], int]]:
    """构建命令处理器注册表（从 _dispatch 拆出以控制函数长度）。"""
    return {
        "doctor": _handle_doctor,
        "baseline": lambda a: (
            _handle_baseline_validate(a) if a.baseline_action == "validate" else _handle_baseline_recompute(a)
        ),
        "language-rules": _handle_language_rules,
        "quality-gate": _handle_quality_gate,
        "quality-gate-new": _handle_quality_gate_new,
        "governance-audit": _handle_governance_audit,
        "secret-scan": _handle_secret_scan,
        "auto-fix": _handle_auto_fix,
        "supply-chain": _handle_supply_chain,
        "sbom": _handle_sbom,
        "verify-signature": _handle_verify_signature,
        "diff": lambda a: _run_simple(run_diff_checks(a.base)),
        "pre-commit": lambda a: _run_simple(run_pre_commit_checks()),
        "pr-review": lambda a: _run_simple(run_pr_review()),
        "arch-graph": lambda a: _run_simple(run_arch_graph()),
        "semantic-check": lambda a: _run_semantic_check(
            a.path,
            getattr(a, "lang", None),
            getattr(a, "jobs", None) or _get_jobs_setting(),
        ),
        "ast-fix": lambda a: _run_ast_fix(a.path, getattr(a, "dry_run", False)),
        "hallucination-scan": lambda a: _run_hallucination_scan(
            getattr(a, "path", Path(".")),
            getattr(a, "lang", None),
        ),
        "install-hooks": _handle_install_hooks,
        "learn": _handle_learn,
        "dashboard": _handle_dashboard,
        "db-maintain": _handle_db_maintain,
        "docs-validate": _handle_docs_validate,
        "exception": _handle_exception,
        "dep-graph": _handle_dep_graph,
        "full": lambda a: _run_full(a),
    }


def _dispatch(args: argparse.Namespace) -> int:
    """Dispatch the parsed command to the appropriate handler."""
    cmd = args.command

    # 增量测试: 只跑受变更影响的测试（PR 级时间预算）
    if cmd == "test" and getattr(args, "incremental", False) and not getattr(args, "lang", None):
        from tools.scripts.hooks.basic_checks import run_tests_incremental

        return _run_simple(lambda: run_tests_incremental(args.base))

    if cmd in _SIMPLE_COMMANDS:
        func = globals()[_SIMPLE_COMMANDS[cmd]]
        return _run_simple(func)

    # 多语言版本命令（显式指定 --lang 时使用）
    multi_commands = _MULTI_COMMANDS

    # 如果显式指定了 --lang，使用多语言版本
    if cmd in multi_commands and getattr(args, "lang", None):
        return _run_simple(multi_commands[cmd](args))

    handler = _build_handlers().get(cmd)
    if handler:
        return handler(args)

    print(f"Unknown command: {cmd}")
    return 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    return _dispatch(args)


if __name__ == "__main__":
    sys.exit(main())

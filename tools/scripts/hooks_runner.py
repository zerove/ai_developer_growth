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
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, cast

from tools.scripts.auto_fix import AutoFixOrchestrator, FixResult, FixSafetyLevel, FixStrategy
from tools.scripts.dependency_graph import (
    CircularDependency,
    DependencyConflict,
    DependencyGraph,
    analyze_dependency_graph,
)
from tools.scripts.exception_manager import (
    EnhancedExceptionManager,
    ExceptionStatus,
    create_enhanced_manager,
)

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
from tools.scripts.language_registry import (
    EXTENSION_MAP,
    Language,
    ToolCategory,
    ToolConfig,
    detect_language,
    get_tool,
)
from tools.scripts.quality_gate import run_quality_gate as run_quality_gate_new
from tools.scripts.rules_engine.models import CheckResult
from tools.scripts.secret_scanner import scan_secrets
from tools.scripts.supply_chain import (
    SBOM,
    LicensePolicy,
    ScanResult,
    Severity,
    SupplyChainScanner,
    Vulnerability,
)

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


def _get_jobs_setting() -> int:
    """获取 jobs 配置（从 [tool.adg].jobs 或默认值 4）。"""
    try:
        from tools.scripts.app_config import get_setting

        return int(str(get_setting("jobs", 4)))
    except Exception:
        return 4


def _timeout_for_category(category: object) -> int:
    """按工具类别获取超时秒数，支持 [tool.adg].timeouts 配置覆盖。

    默认: 测试套件 900s（全量运行且与其他阶段并行时耗时显著变长），其余 300s。
    配置格式: [tool.adg.timeouts] test = 1200, lint = 180 ...
    """
    default = 900 if getattr(category, "name", "") == "TEST" else 300
    key = getattr(category, "name", "").lower()
    try:
        from tools.scripts.app_config import get_setting

        timeouts = get_setting("timeouts", None)
        if isinstance(timeouts, dict) and key in timeouts:
            return int(str(timeouts[key]))
    except Exception as e:  # noqa: BLE001 - 配置缺失时使用默认超时
        logger.debug("读取超时配置失败，使用默认 %ss: %s", default, e)
    return default


def _excluded_scan_dirs() -> set[str]:
    """扫描时排除的目录: 虚拟环境、依赖与构建产物。"""
    return {
        ".venv",
        "venv",
        "node_modules",
        ".git",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        "__pycache__",
        "site-packages",
        "dist",
        "build",
        "target",
        "site",
    }


def _count_language_files(project_root: Path) -> dict[Language, int]:
    """扫描所有扩展名, 统计各语言文件数 (排除第三方/构建目录)。"""
    _node_ecosystem_languages = {Language.TYPESCRIPT, Language.JAVASCRIPT}
    has_package_json = (project_root / "package.json").exists()
    excluded = _excluded_scan_dirs()

    ext_counts: dict[Language, int] = {}
    for ext, lang in EXTENSION_MAP.items():
        if lang in _node_ecosystem_languages and not has_package_json:
            continue
        count = sum(1 for p in project_root.rglob(f"*{ext}") if not (set(p.parts) & excluded))
        if count > 0:
            ext_counts[lang] = ext_counts.get(lang, 0) + count
    return ext_counts


def _detect_project_languages(project_root: Path) -> list[Language]:
    """检测项目中使用的所有语言"""
    languages: list[Language] = []

    # Node 生态语言需要 package.json 作为工程化标志；
    # 否则散落的 .ts/.js（如编辑器扩展、构建产物）会因缺少
    # eslint/prettier/tsc 工具链而误报失败
    _node_ecosystem_languages = {Language.TYPESCRIPT, Language.JAVASCRIPT}
    has_package_json = (project_root / "package.json").exists()

    # 1. 通过配置文件检测主要语言
    main_lang = detect_language(project_root)
    if main_lang and not (main_lang in _node_ecosystem_languages and not has_package_json):
        languages.append(main_lang)

    # 2. 扫描扩展名统计语言分布, 按文件数排序后仅纳入占比显著的语言：
    # 示例脚本、编辑器扩展等附带文件不应触发全量工具链门禁
    ext_counts = _count_language_files(project_root)
    total = sum(ext_counts.values())
    for lang, count in sorted(ext_counts.items(), key=lambda kv: kv[1], reverse=True):
        if lang in languages:
            continue
        if count >= 50 or (total > 0 and count / total >= 0.2):
            languages.append(lang)

    return languages


def _build_parser() -> argparse.ArgumentParser:
    """Build the CLI argument parser."""
    parser = argparse.ArgumentParser(
        description="统一 Hook 运行器 - 多语言支持",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
支持的语言: see `hooks_runner.py full --help`

Examples:
  hooks_runner.py full --lang python,typescript
  hooks_runner.py quality-gate --path tools/scripts --full
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # 基础检查命令 - 支持 --lang 和 --path
    for cmd_name, help_text in [
        ("lint", "Run lint check"),
        ("format", "Run format check"),
        ("typecheck", "Run type check"),
        ("test", "Run test suite"),
        ("security", "Run security scan"),
    ]:
        sp = subparsers.add_parser(cmd_name, help=help_text)
        sp.add_argument("--lang", help="Language (auto-detect if not specified)")
        sp.add_argument("--path", type=Path, default=Path("."), help="Path to check (default: current dir)")
        sp.add_argument("--fix", action="store_true", help="Apply auto-fixes (lint/format only)")
        if cmd_name == "test":
            sp.add_argument(
                "--incremental",
                action="store_true",
                help="Only run tests affected by changed files vs --base",
            )
            sp.add_argument("--base", default="HEAD", help="Base ref for incremental test selection")

    # doctor 与 baseline 棘轮管理
    _add_doctor_baseline_parsers(subparsers)
    _add_core_gate_parsers(subparsers)
    _add_analysis_parsers(subparsers)
    _add_extended_scan_parsers(subparsers)
    _add_exception_dep_parsers(subparsers)
    _add_dep_graph_parsers(subparsers)
    _add_signature_sbom_parsers(subparsers)
    _add_security_parsers(subparsers)
    _add_workflow_parsers(subparsers)
    return parser


def _add_doctor_baseline_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """doctor 与 baseline 棘轮管理命令。"""
    doctor_parser = subparsers.add_parser(
        "doctor",
        help="Diagnose hook/gate environment health (pre-commit, tools, baseline)",
    )
    doctor_parser.add_argument("--path", type=Path, default=Path("."), help="Project root")

    # 质量基线管理
    baseline_parser = subparsers.add_parser("baseline", help="Quality ratchet baseline management")
    baseline_sub = baseline_parser.add_subparsers(dest="baseline_action", required=True)
    bl_validate = baseline_sub.add_parser("validate", help="Validate baseline file structure")
    bl_validate.add_argument(
        "--file", type=Path, default=None, help="Baseline path (default: <root>/.jcode/baseline.json)"
    )
    bl_recompute = baseline_sub.add_parser(
        "recompute",
        help="Recompute current issues and compare with baseline (CI anti-tamper check)",
    )
    bl_recompute.add_argument("--path", type=Path, default=Path("."), help="Project root")
    bl_recompute.add_argument(
        "--file", type=Path, default=None, help="Baseline path (default: <root>/.jcode/baseline.json)"
    )


def _add_extended_scan_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """扩展扫描命令: secret-scan/quality-gate-new/auto-fix。"""
    # 新增: Secret Scan
    ss_parser = subparsers.add_parser("secret-scan", help="Scan for secrets in code (gitleaks, trufflehog)")
    ss_parser.add_argument("--path", type=Path, default=Path("."), help="Path to scan")
    ss_parser.add_argument("--workspace", action="store_true", default=True, help="Scan workspace")
    ss_parser.add_argument("--no-workspace", action="store_false", dest="workspace", help="Skip workspace scan")
    ss_parser.add_argument("--history", action="store_true", default=True, help="Scan git history")
    ss_parser.add_argument("--no-history", action="store_false", dest="history", help="Skip git history scan")
    ss_parser.add_argument("--pr-diff", action="store_true", help="Scan PR diff only")
    ss_parser.add_argument("--tools", help="Comma-separated tools: gitleaks,trufflehog,detect-secrets")
    ss_parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    ss_parser.add_argument("--output", type=Path, help="Output file path")

    # 新增: Quality Gate (新引擎)
    qg2_parser = subparsers.add_parser("quality-gate-new", help="Run new Quality Gate engine")
    qg2_parser.add_argument("--path", type=Path, default=Path("."), help="Path to check")
    qg2_parser.add_argument("--gate", default="default", help="Gate name from config")
    qg2_parser.add_argument("--baseline", type=Path, help="Baseline file path")
    qg2_parser.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    qg2_parser.add_argument("--output", type=Path, help="Output file path")

    # 新增: Auto-fix
    af_parser = subparsers.add_parser("auto-fix", help="Run auto-fix on code issues")
    af_parser.add_argument("--path", type=Path, default=Path("."), help="Path to fix")
    af_parser.add_argument(
        "--strategy", choices=["auto", "interactive", "dry_run", "batch_pr"], default="auto", help="Fix strategy"
    )
    af_parser.add_argument(
        "--safety", choices=["safe", "low_risk", "medium_risk", "high_risk"], default="safe", help="Max safety level"
    )
    af_parser.add_argument("--max-per-file", type=int, default=50, help="Max fixes per file")
    af_parser.add_argument("--no-backup", action="store_true", help="Don't create backups")
    af_parser.add_argument("--run-tests", action="store_true", help="Run regression tests after fix")
    af_parser.add_argument("--test-cmd", help="Test command to run")
    af_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    af_parser.add_argument("--output", type=Path, help="Output file path")

    # 新增: Supply Chain Security


def _add_core_gate_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """核心门禁命令: language-rules/quality-gate/governance-audit/docs-validate/diff 等"""
    lr_parser = subparsers.add_parser("language-rules", help="Run language-specific rules validation")
    lr_parser.add_argument("--path", type=Path, default=Path("."), help="Path to validate")
    lr_parser.add_argument("--lang", help="Language (auto-detect if not specified)")
    lr_parser.add_argument("--jobs", "-j", type=int, help="Parallel workers (default: from [tool.adg].jobs)")
    lr_parser.add_argument("--fix", action="store_true", help="Apply auto-fixes to fixable issues")
    lr_parser.add_argument("--cache", action="store_true", help="启用增量缓存（复用检查历史）")
    lr_parser.add_argument("--db", help="统一存储数据库路径（默认 [tool.adg].trend_db)")

    qg_parser = subparsers.add_parser("quality-gate", help="Run AI Quality Gate checks")
    qg_parser.add_argument("--path", type=Path, default=Path("tools/scripts"), help="Path to check")
    qg_parser.add_argument("--full", action="store_true", help="Run all checks")
    qg_parser.add_argument("--check-annotation", action="store_true", help="Check AI annotation")
    qg_parser.add_argument("--check-security", action="store_true", help="Check security patterns")
    qg_parser.add_argument("--check-type", action="store_true", help="Check type safety")
    qg_parser.add_argument("--check-error", action="store_true", help="Check error handling")
    qg_parser.add_argument("--check-structure", action="store_true", help="Check code structure")
    qg_parser.add_argument("--check-patterns", action="store_true", help="Check all anti-patterns")
    qg_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    ga_parser = subparsers.add_parser("governance-audit", help="Run Governance Auditor checks")
    ga_parser.add_argument("--full", action="store_true", help="Run all governance checks")
    ga_parser.add_argument("--validate-docs", action="store_true", help="Validate governance docs")
    ga_parser.add_argument("--check-ai-sdlc", action="store_true", help="Check AI-SDLC compliance")
    ga_parser.add_argument("--audit-hallucination", action="store_true", help="Audit hallucination risks")
    ga_parser.add_argument("--check-index", action="store_true", help="Check index references")

    dv_parser = subparsers.add_parser(
        "docs-validate",
        help="治理文档验证统一入口（validate/check-index/sync-refs/full）",
    )
    dv_parser.add_argument(
        "action2",
        nargs="?",
        default="validate",
        choices=["validate", "check-index", "sync-refs", "full"],
        help="验证动作",
    )


def _add_analysis_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """增量与静态分析命令。"""
    diff_parser = subparsers.add_parser("diff", help="Incremental check: only changed files vs base ref")
    diff_parser.add_argument("--base", default="HEAD", help="Git ref to diff against (default: HEAD)")

    sc_parser = subparsers.add_parser("semantic-check", help="Run AST-based semantic analysis (tree-sitter)")
    sc_parser.add_argument("--path", type=Path, default=Path("."), help="Path to check")
    sc_parser.add_argument("--lang", help="Language filter")
    sc_parser.add_argument("--jobs", "-j", type=int, help="Parallel workers (default: from [tool.adg].jobs)")

    af_parser = subparsers.add_parser("ast-fix", help="Run AST-based auto-fix on files")
    af_parser.add_argument("--path", type=Path, default=Path("."), help="Path to fix")
    af_parser.add_argument("--dry-run", action="store_true", help="Preview fixes without applying")

    hs_parser = subparsers.add_parser("hallucination-scan", help="Scan for AI hallucination patterns in code")
    hs_parser.add_argument("--path", type=Path, default=Path("."), help="Path to scan")
    hs_parser.add_argument("--lang", help="Language filter")


def _add_exception_dep_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """例外管理与依赖图命令。"""
    # 新增: Exception Manager (例外管理)
    em_parser = subparsers.add_parser("exception", help="Manage quality gate exceptions")
    em_subparsers = em_parser.add_subparsers(dest="exception_action", required=True)

    # exception request
    em_req = em_subparsers.add_parser("request", help="Request an exception")
    em_req.add_argument("--rule-id", required=True, help="Rule ID to except")
    em_req.add_argument("--paths", required=True, help="Comma-separated paths/patterns")
    em_req.add_argument("--reason", required=True, help="Reason for exception")
    em_req.add_argument("--severity", required=True, help="Original severity (error/warning/info)")
    em_req.add_argument("--requested-severity", required=True, help="Requested severity after exception")
    em_req.add_argument("--expires", help="Expiration date (ISO format)")
    em_req.add_argument("--created-by", required=True, help="Requester")
    em_req.add_argument("--reviewers", help="Comma-separated reviewers")

    # exception approve
    em_appr = em_subparsers.add_parser("approve", help="Approve an exception request")
    em_appr.add_argument("--request-id", required=True, help="Request ID")
    em_appr.add_argument("--reviewer", required=True, help="Reviewer name")
    em_appr.add_argument("--comment", default="", help="Approval comment")

    # exception reject
    em_rej = em_subparsers.add_parser("reject", help="Reject an exception request")
    em_rej.add_argument("--request-id", required=True, help="Request ID")
    em_rej.add_argument("--reviewer", required=True, help="Reviewer name")
    em_rej.add_argument("--comment", default="", help="Rejection reason")

    # exception revoke
    em_rev = em_subparsers.add_parser("revoke", help="Revoke an approved exception")
    em_rev.add_argument("--request-id", required=True, help="Request ID")

    # exception list
    em_list = em_subparsers.add_parser("list", help="List exception requests")
    em_list.add_argument(
        "--status", choices=["pending", "approved", "rejected", "expired", "revoked"], help="Filter by status"
    )

    # exception check-expirations
    em_subparsers.add_parser("check-expirations", help="Check for expiring exceptions")

    # exception audit
    em_subparsers.add_parser("audit", help="Generate audit report")

    # exception sync-gitops
    em_subparsers.add_parser("sync-gitops", help="Sync exceptions to/from GitOps repo")


def _add_dep_graph_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """依赖图分析命令。"""
    dg_parser = subparsers.add_parser("dep-graph", help="Analyze dependency graph")
    dg_subparsers = dg_parser.add_subparsers(dest="dep_graph_action", required=True)

    # dep-graph analyze
    dg_analyze = dg_subparsers.add_parser("analyze", help="Analyze project dependencies")
    dg_analyze.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    dg_analyze.add_argument("--output", type=Path, help="Output file (JSON/Graphviz/Mermaid)")
    dg_analyze.add_argument(
        "--format", choices=["json", "graphviz", "mermaid", "tree"], default="tree", help="Output format"
    )
    dg_analyze.add_argument("--max-depth", type=int, default=-1, help="Max depth for tree format")

    # dep-graph circular
    dg_circular = dg_subparsers.add_parser("circular", help="Detect circular dependencies")
    dg_circular.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    dg_circular.add_argument("--output", type=Path, help="Output file (JSON)")

    # dep-graph conflicts
    dg_conflicts = dg_subparsers.add_parser("conflicts", help="Detect version conflicts")
    dg_conflicts.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    dg_conflicts.add_argument("--output", type=Path, help="Output file (JSON)")

    # dep-graph impact
    dg_impact = dg_subparsers.add_parser("impact", help="Analyze impact of package change")
    dg_impact.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    dg_impact.add_argument("--package", required=True, help="Package name to analyze")
    dg_impact.add_argument("--version", help="Specific version (optional)")
    dg_impact.add_argument("--output", type=Path, help="Output file (JSON)")


def _add_security_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """安全类命令: semantic-check/ast-fix/hallucination-scan/secret-scan/auto-fix/supply-chain/sbom/verify-signature"""
    sc_parser = subparsers.add_parser("supply-chain", help="Multi-language supply chain security")
    sc_subparsers = sc_parser.add_subparsers(dest="sc_action", required=True)

    # supply-chain scan
    sc_scan = sc_subparsers.add_parser("scan", help="Scan supply chain for vulnerabilities")
    sc_scan.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sc_scan.add_argument("--format", choices=["text", "json", "sarif"], default="text", help="Output format")
    sc_scan.add_argument("--output", type=Path, help="Output file path")
    sc_scan.add_argument(
        "--fail-on", choices=["critical", "high", "medium", "low"], default="high", help="Fail on severity level"
    )

    # supply-chain sbom
    sc_sbom = sc_subparsers.add_parser("sbom", help="Generate SBOM (Software Bill of Materials)")
    sc_sbom.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sc_sbom.add_argument("--output", type=Path, help="Output file path (default: stdout)")
    sc_sbom.add_argument("--format", choices=["json", "spdx", "cyclonedx"], default="json", help="Output format")

    # supply-chain compliance
    sc_compliance = sc_subparsers.add_parser("compliance", help="Check supply chain compliance against policy")
    sc_compliance.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sc_compliance.add_argument("--policy-file", type=Path, help="Path to policy file")
    sc_compliance.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    sc_compliance.add_argument("--output", type=Path, help="Output file path")

    # supply-chain freshness
    sc_freshness = sc_subparsers.add_parser("freshness", help="Check dependency freshness")
    sc_freshness.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sc_freshness.add_argument("--max-age-days", type=int, default=90, help="Maximum age in days")
    sc_freshness.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    sc_freshness.add_argument("--output", type=Path, help="Output file path")

    # supply-chain verify
    sc_verify = sc_subparsers.add_parser("verify", help="Verify supply chain integrity (SLSA provenance)")
    sc_verify.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sc_verify.add_argument("--format", choices=["text", "json"], default="text", help="Output format")
    sc_verify.add_argument("--output", type=Path, help="Output file path")


def _add_signature_sbom_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """SBOM 兼容与签名验证命令。"""
    # Keep backward compatible sbom parser at top level
    sbom_parser = subparsers.add_parser("sbom", help="Generate SBOM (Software Bill of Materials)")
    sbom_parser.add_argument("--path", type=Path, default=Path("."), help="Project root path")
    sbom_parser.add_argument("--output", type=Path, help="Output file path (default: stdout)")
    sbom_parser.add_argument("--format", choices=["json", "spdx"], default="json", help="Output format")

    # 新增: 签名验证
    vs_parser = subparsers.add_parser("verify-signature", help="Verify package/container signatures")
    vs_parser.add_argument("--cosign", help="Container image to verify with cosign")
    vs_parser.add_argument("--cosign-key", help="Cosign public key path")
    vs_parser.add_argument("--slsa", type=Path, help="Path to package for SLSA provenance verification")
    vs_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")


def _add_workflow_parsers(subparsers: argparse._SubParsersAction[argparse.ArgumentParser]) -> None:
    """工作流辅助命令: exception/dep-graph/pre-commit/pr-review/arch-graph/install-hooks/learn/dashboard/full"""
    subparsers.add_parser("pre-commit", help="Pre-commit hook: check staged files only")
    subparsers.add_parser("pr-review", help="Run automated AI PR review")
    subparsers.add_parser("arch-graph", help="Generate architecture dependency graph (Mermaid)")

    install_parser = subparsers.add_parser("install-hooks", help="Install git hooks")
    install_parser.add_argument("--pre-push", action="store_true", help="Install pre-push hook")
    install_parser.add_argument("--pre-commit", action="store_true", help="Install pre-commit hook")

    learn_parser = subparsers.add_parser("learn", help="AI-driven rule generation from codebase analysis")
    learn_parser.add_argument(
        "project_path", type=Path, nargs="?", default=Path("."), help="Project root (default: current dir)"
    )
    learn_parser.add_argument("--output", "-o", type=Path, help="Output rules YAML file")
    learn_parser.add_argument("--format", choices=["text", "json"], default="text", help="Output format")

    dashboard_parser = subparsers.add_parser("dashboard", help="Start quality dashboard web server")
    dashboard_parser.add_argument("--port", type=int, default=8765, help="Port (default: 8765)")
    dashboard_parser.add_argument("--db", help="SQLite database path (default: [tool.adg].trend_db)")

    full_parser = subparsers.add_parser(
        "full",
        help="Run all checks (lint, format, typecheck, test, security, quality-gate, governance-audit)",
    )
    full_parser.add_argument("--lang", help="Comma-separated languages (auto-detect if not specified)")
    full_parser.add_argument("--path", type=Path, default=Path("."), help="Project root path")


def _run_simple(
    func_or_result: Callable[[], tuple[bool, str]] | tuple[bool, str],
) -> int:
    """Run a simple check function and print output."""
    if callable(func_or_result):
        passed, output = func_or_result()
    else:
        passed, output = func_or_result
    print(output)
    return 0 if passed else 1


def _tool_available(language: Language, tool: ToolConfig) -> str | None:
    """检查工具是否可用, 返回错误消息或 None。"""
    try:
        version_result: subprocess.CompletedProcess[str] = subprocess.run(
            [tool.command, tool.version_flag],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if version_result.returncode != 0:
            return f"  ❌ {language.value}: {tool.command} 不可用 ({tool.install_hint})"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return f"  ❌ {language.value}: {tool.command} 未安装 ({tool.install_hint})"
    return None


def _build_tool_command(tool: ToolConfig, fix: bool, check_only: bool) -> list[str]:
    """按 fix/check_only 模式构建工具命令行。"""
    cmd = [tool.command]
    if fix and tool.fix_args:
        cmd.extend(tool.fix_args)
    elif check_only and tool.check_args:
        cmd.extend(tool.check_args)
    else:
        cmd.extend(tool.args)
    return cmd


def _execute_tool(cmd: list[str], language: Language, category: ToolCategory, project_root: Path) -> tuple[bool, str]:
    """执行工具命令并格式化输出。"""
    timeout_seconds = _timeout_for_category(category)
    try:
        result: subprocess.CompletedProcess[str] = subprocess.run(
            cmd,
            cwd=project_root,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired:
        return False, f"  ❌ {language.value}: {category.value} 超时 ({timeout_seconds}s)"
    except Exception as e:
        return False, f"  ❌ {language.value}: {category.value} 错误 - {e}"

    output = result.stdout
    if result.stderr:
        output += "\n" + result.stderr

    passed = result.returncode == 0
    status = "✅" if passed else "❌"
    suffix = "通过" if passed else "失败"
    return passed, f"  {status} {language.value}: {category.value} {suffix}\n{output}"


def _run_tool_for_language(
    language: Language,
    category: ToolCategory,
    project_root: Path,
    fix: bool = False,
    check_only: bool = False,
) -> tuple[bool, str]:
    """使用语言工具链运行特定类别工具"""
    tool = get_tool(language, category)
    if tool is None:
        return False, f"  ⚠️  {language.value}: {category.value} 工具未配置"

    unavailable = _tool_available(language, tool)
    if unavailable:
        return False, unavailable

    cmd = _build_tool_command(tool, fix, check_only)
    print(f"  🔧 {language.value}: 运行 {category.value} ({' '.join(cmd)})")
    return _execute_tool(cmd, language, category, project_root)


def _run_basic_check_for_languages(
    languages: list[Language],
    category: ToolCategory,
    project_root: Path,
    fix: bool = False,
    check_only: bool = False,
) -> tuple[bool, str]:
    """为多个语言运行基础检查"""
    all_passed = True
    outputs = []

    for lang in languages:
        passed, output = _run_tool_for_language(lang, category, project_root, fix, check_only)
        all_passed = all_passed and passed
        outputs.append(output)

    return all_passed, "\n".join(outputs)


def _run_lint_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言 lint 检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.LINT, args.path, fix=args.fix)


def _run_format_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言格式检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.FORMAT, args.path, fix=args.fix)


def _run_typecheck_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言类型检查 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.TYPECHECK, args.path)


def _run_test_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言测试 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.TEST, args.path)


def _run_security_multi(args: argparse.Namespace) -> tuple[bool, str]:
    """多语言安全扫描 - 兼容模式：默认只检查 Python"""
    if args.lang:
        langs = _parse_languages(args.lang)
    else:
        # 兼容模式：默认只检查 Python（向后兼容）
        langs = [Language.PYTHON]
    return _run_basic_check_for_languages(langs, ToolCategory.SECURITY, args.path)


def _parse_languages(lang_str: str) -> list[Language]:
    """解析逗号分隔的语言字符串"""
    languages = []
    for part in lang_str.split(","):
        part = part.strip()
        if part:
            try:
                languages.append(Language(part.lower()))
            except ValueError:
                # 尝试别名
                from tools.scripts.language_registry import LANGUAGE_ALIASES

                if part.lower() in LANGUAGE_ALIASES:
                    languages.append(LANGUAGE_ALIASES[part.lower()])
                else:
                    print(f"  ⚠️  未知语言: {part}，跳过")
    return languages


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


def _run_lint_phase() -> tuple[bool, str]:
    # 使用 globals() 获取可 mock 的模块级函数
    func: Callable[[], tuple[bool, str]] = globals()["run_lint"]
    return func()


def _run_format_phase() -> tuple[bool, str]:
    func: Callable[[], tuple[bool, str]] = globals()["run_format_check"]
    return func()


def _run_typecheck_phase() -> tuple[bool, str]:
    func: Callable[[], tuple[bool, str]] = globals()["run_typecheck"]
    return func()


def _run_test_phase() -> tuple[bool, str]:
    func: Callable[[], tuple[bool, str]] = globals()["run_tests"]
    return func()


def _run_security_phase() -> tuple[bool, str]:
    func: Callable[[], tuple[bool, str]] = globals()["run_security"]
    return func()


def _run_quality_gate_full() -> tuple[bool, str]:
    """全量质量门禁检查（阶段用具名函数便于运行时解析与 mock）。"""
    return run_quality_gate(_full_path, full=True)


def _run_governance_audit_full() -> tuple[bool, str]:
    """全量治理审计（阶段用具名函数）。"""
    return run_governance_audit(full=True)


def _resolve_phase_func(func_name: str) -> Callable[[], tuple[bool, str]]:
    """运行时解析阶段函数（支持测试 mock 与外部配置）。"""
    func = globals().get(func_name, None)
    if not callable(func):
        raise NameError(f"阶段函数未定义: {func_name}")
    return cast(Callable[[], tuple[bool, str]], func)


# 全局变量，供阶段函数使用
_full_langs: list[Language] = []
_full_path: Path = Path(".")


def _run_phase(phase_name: str, results: dict[str, tuple[bool, str]]) -> None:
    """执行单个阶段并记录结果（跳过已执行阶段）。"""
    if phase_name in results:
        return
    func_name, parallel, _ = _PHASE_INDEX[phase_name]
    _ = parallel  # 依赖解析阶段由 _run_full 统一调度并行
    print(f"⏳ [hooks] 阶段开始: {phase_name}", flush=True)
    start = time.monotonic()
    try:
        passed, output = _resolve_phase_func(func_name)()
    except Exception as e:
        passed, output = False, str(e)
    elapsed = time.monotonic() - start
    status = "✅" if passed else "❌"
    print(f"{status} [hooks] 阶段完成: {phase_name} ({elapsed:.1f}s)", flush=True)
    results[phase_name] = (passed, output)


def _resolve_order() -> list[str]:
    """拓扑排序所有阶段，保证依赖先于使用者执行。"""
    order: list[str] = []
    visited: set[str] = set()

    def visit(name: str) -> None:
        if name in visited:
            return
        visited.add(name)
        _, _, deps = _PHASE_INDEX[name]
        for dep in deps:
            if dep in _PHASE_INDEX:
                visit(dep)
        order.append(name)

    for name in _PHASE_INDEX:
        visit(name)
    return order


def _run_parallel_checks() -> dict[str, tuple[bool, str]]:
    """Run parallel phase checks: lint, format, typecheck."""
    parallel_phases = [name for name, _, parallel, _ in _CHECK_PHASES if parallel]
    results: dict[str, tuple[bool, str]] = {}
    with ThreadPoolExecutor(max_workers=len(parallel_phases)) as executor:
        futures = {
            executor.submit(_resolve_phase_func(func_name)): name
            for name, func_name, parallel, _ in _CHECK_PHASES
            if name in parallel_phases and parallel
        }
        for future in as_completed(futures):
            name = futures[future]
            try:
                passed, output = future.result()
            except Exception as e:
                passed, output = False, str(e)
            status = "✅" if passed else "❌"
            print(f"{status} [hooks] 并行阶段完成: {name}", flush=True)
            results[name] = (passed, output)
    return results


def _print_results_in_order(results: dict[str, tuple[bool, str]], order: list[str]) -> bool:
    """Print results in fixed order. Returns all_passed."""
    all_passed = True
    for i, name in enumerate(order, 1):
        print(f"\n📋 {i}/{len(order)}: {name}")
        passed, output = results[name]
        print(output)
        if not passed:
            all_passed = False
    return all_passed


def _run_sequential_phases(results: dict[str, tuple[bool, str]]) -> None:
    """执行串行阶段 (含依赖解析: 依赖失败则跳过)。"""
    sequential_phases = [name for name, _, parallel, _ in _CHECK_PHASES if not parallel]
    for name in sequential_phases:
        _, _, deps = _PHASE_INDEX[name]
        passed_deps = True
        failed_deps: list[str] = []
        for dep in deps:
            if dep not in results:
                _run_phase(dep, results)
            if not results[dep][0]:
                passed_deps = False
                failed_deps.append(dep)
        if passed_deps:
            _run_phase(name, results)
        else:
            results[name] = (False, f"Skipped: dependency '{failed_deps}' failed")


def _run_full(args: argparse.Namespace) -> int:
    """Run the full check suite with parallel + sequential phases."""
    global _full_args, _full_langs, _full_path

    _full_args = args
    _full_path = args.path

    # 检测语言
    if args.lang:
        _full_langs = _parse_languages(args.lang)
    else:
        _full_langs = _detect_project_languages(args.path)

    if not _full_langs:
        print("⚠️  未检测到支持的语言，默认使用 Python")
        _full_langs = [Language.PYTHON]

    print("=" * 60)
    print("  FULL HOOKS RUNNER - 完整检查套件 (多语言)")
    print(f"  检测语言: {', '.join(lang.value for lang in _full_langs)}")
    print(f"  项目路径: {_full_path}")
    print("=" * 60)

    results: dict[str, tuple[bool, str]] = {}
    results.update(_run_parallel_checks())
    _run_sequential_phases(results)

    order = _resolve_order()
    all_passed = _print_results_in_order(results, order)

    print("\n" + "=" * 60)
    print("✅ ALL CHECKS PASSED" if all_passed else "❌ SOME CHECKS FAILED")
    print("=" * 60)

    return 0 if all_passed else 1


def _run_semantic_check(path: Path, lang: str | None, jobs: int) -> int:
    """Run AST-based semantic analysis on a directory or file."""
    from tools.scripts.rules_engine.checker import check_directory, check_file

    print("=" * 60)
    print("  SEMANTIC CHECK (tree-sitter AST)")
    print("=" * 60)

    if path.is_file():
        result = check_file(path, semantic=True)
        _print_check_result(result)
        return 0 if not result.issues else 1

    languages = [lang] if lang else None
    results = check_directory(path, languages=languages, jobs=jobs, semantic=True)

    total_issues = 0
    for result in sorted(results, key=lambda r: r.file):
        _print_check_result(result)
        total_issues += len(result.issues)

    print(f"\n{'=' * 60}")
    print(f"  Scanned {len(results)} files, found {total_issues} semantic issues")
    if total_issues == 0:
        print("  ✅ ALL CLEAN")
    else:
        print("  ⚠️  Issues found")
    print("=" * 60)

    return 0 if total_issues == 0 else 1


def _run_ast_fix(path: Path, dry_run: bool) -> int:
    """Run AST-based auto-fix on files."""
    from tools.scripts.rules_engine.ast_fixer import ASTFixer

    print("=" * 60)
    print("  AST AUTO-FIX" + (" (dry run)" if dry_run else ""))
    print("=" * 60)

    fixer = ASTFixer()

    if path.is_file():
        report = fixer.fix_file(path, dry_run=dry_run)
        if report is None:
            print(f"  ⚠️  Cannot parse {path}, skipping")
            return 0
        print(fixer.format_fix_report(report))
        return 0 if report.total_fixes == 0 else (0 if dry_run else 1)

    # Directory: fix all Python files
    total_fixes = 0
    for filepath in sorted(path.rglob("*.py")):
        if any(d in filepath.parts for d in {"__pycache__", ".git", "node_modules", ".venv"}):
            continue
        report = fixer.fix_file(filepath, dry_run=dry_run)
        if report is None:
            continue
        if report.total_fixes > 0:
            print(fixer.format_fix_report(report))
            total_fixes += report.total_fixes

    print(f"\n{'=' * 60}")
    print(f"  Total fixes: {total_fixes}" + (" (dry run)" if dry_run else ""))
    if total_fixes == 0:
        print("  ✅ No fixes needed")
    elif dry_run:
        print("  ℹ️  Run without --dry-run to apply")
    else:
        print("  ✅ Fixes applied")
    print("=" * 60)

    return 0


def _run_hallucination_scan(path: Path, lang: str | None) -> int:
    """Run AI hallucination pattern detection."""
    from tools.scripts.rules_engine.hallucination_detector import (
        detect_hallucinations,
        detect_hallucinations_in_file,
        format_hallucination_report,
    )

    print("=" * 60)
    print("  AI HALLUCINATION PATTERN SCAN")
    print("=" * 60)

    if path.is_file():
        report = detect_hallucinations_in_file(path)
    else:
        report = detect_hallucinations(path)

    print(format_hallucination_report(report))

    return 0 if report.high_count == 0 else 1


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


def _collect_check_results(target_path: Path, jobs: int) -> list[CheckResult]:
    """对单文件或目录执行规则检查, 收集结果。"""
    from tools.scripts.language_registry import EXTENSION_MAP, Language
    from tools.scripts.rules_engine.checker import check_directory, check_file

    if target_path.is_file():
        ext = target_path.suffix
        lang = EXTENSION_MAP.get(ext, Language.PYTHON)
        return [check_file(target_path, None, lang, semantic=False, run_linters=True)]
    return check_directory(target_path, jobs=jobs, semantic=False)


def _build_fix_orchestrator(args: argparse.Namespace) -> AutoFixOrchestrator:
    """按命令行参数配置修复编排器。"""
    from tools.scripts.auto_fix import create_default_orchestrator

    orchestrator = create_default_orchestrator()
    orchestrator.strategy = FixStrategy(args.strategy)
    orchestrator.safety_level = FixSafetyLevel(args.safety)
    orchestrator.max_fixes_per_file = args.max_per_file
    orchestrator.backup = not args.no_backup
    orchestrator.run_tests_after = args.run_tests
    orchestrator.test_command = args.test_cmd
    return orchestrator


def _print_fix_text(fix_results: list[FixResult]) -> None:
    """文本格式输出修复结果。"""
    total_applied = sum(len(r.applied) for r in fix_results)
    total_skipped = sum(len(r.skipped) for r in fix_results)
    total_errors = sum(len(r.errors) for r in fix_results)

    print("\n🔧 Auto-fix 完成")
    print(f"  应用: {total_applied}")
    print(f"  跳过: {total_skipped}")
    print(f"  错误: {total_errors}")

    for result in fix_results:
        if result.applied:
            print(f"\n  📄 {result.file}:")
            for action in result.applied:
                print(f"    ✅ {action.rule_id} @ line {action.line}")
            if result.diff:
                print(f"    Diff:\n{result.diff[:200]}...")

        if result.skipped:
            for action in result.skipped:
                print(f"    ⏭️  {action.rule_id} @ line {action.line} (skipped)")

        if result.errors:
            for err in result.errors:
                print(f"    ❌ {err}")


def _fix_result_dicts(fix_results: list[FixResult]) -> list[dict[str, object]]:
    """将修复结果序列化为 JSON 兼容字典。"""
    return [
        {
            "file": r.file,
            "applied": [{"rule_id": a.rule_id, "line": a.line} for a in r.applied],
            "skipped": [{"rule_id": a.rule_id, "line": a.line} for a in r.skipped],
            "errors": r.errors,
            "diff": r.diff,
        }
        for r in fix_results
    ]


def _handle_auto_fix(args: argparse.Namespace) -> int:
    """Handle auto-fix command."""
    import json
    from pathlib import Path

    from tools.scripts.app_config import get_setting

    jobs = getattr(args, "jobs", None) or int(str(get_setting("jobs", 4)))

    results = _collect_check_results(args.path, jobs)

    orchestrator = _build_fix_orchestrator(args)
    fix_results = orchestrator.execute_plan(
        orchestrator.create_plan(results),
        Path.cwd(),
    )

    total_errors = sum(len(r.errors) for r in fix_results)

    if args.format == "text":
        _print_fix_text(fix_results)
    elif args.format == "json":
        print(json.dumps(_fix_result_dicts(fix_results), indent=2, ensure_ascii=False))

    return 0 if total_errors == 0 else 1


def _handle_supply_chain(args: argparse.Namespace) -> int:
    """Handle supply-chain command with subcommands."""
    action = args.sc_action

    if action == "scan":
        return _handle_supply_chain_scan(args)
    elif action == "sbom":
        return _handle_supply_chain_sbom(args)
    elif action == "compliance":
        return _handle_supply_chain_compliance(args)
    elif action == "freshness":
        return _handle_supply_chain_freshness(args)
    elif action == "verify":
        return _handle_supply_chain_verify(args)
    else:
        print(f"Unknown supply-chain action: {action}")
        return 1


def _handle_supply_chain_scan(args: argparse.Namespace) -> int:
    """Handle supply-chain scan subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    scanner = SupplyChainScanner()
    result = scanner.scan_project(project_root)

    _, fail_level = _scan_severity_threshold(args)
    should_fail = _scan_has_failing_vulns(result.vulnerabilities, fail_level)

    _output_scan_result(args, project_root, result)

    return 1 if should_fail else 0


def _scan_severity_threshold(args: argparse.Namespace) -> tuple[Severity, int]:
    """解析 --fail-on 为严重级别及其序数值。"""
    severity_order = {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
        Severity.NONE: 0,
    }
    fail_on = Severity(args.fail_on)
    return fail_on, severity_order.get(fail_on, 0)


def _scan_has_failing_vulns(vulnerabilities: list[Vulnerability], threshold: int) -> bool:
    """判断是否存在达到阈值的漏洞。"""
    severity_order = {
        Severity.CRITICAL: 4,
        Severity.HIGH: 3,
        Severity.MEDIUM: 2,
        Severity.LOW: 1,
        Severity.NONE: 0,
    }
    levels = (severity_order.get(v.severity, 0) for v in vulnerabilities)
    return any(lv >= threshold and lv > 0 for lv in levels)


def _scan_vulnerability_dicts(result: ScanResult) -> list[dict[str, object]]:
    """将漏洞列表序列化为 JSON 兼容字典。"""
    return [
        {
            "id": v.id,
            "source": v.source,
            "severity": v.severity.value,
            "package": v.affected_package,
            "version": v.affected_version,
            "fixed_version": v.fixed_version,
            "summary": v.summary,
        }
        for v in result.vulnerabilities
    ]


def _print_scan_text(project_root: Path, result: ScanResult) -> None:
    """文本格式输出扫描结果。"""
    print(f"\n🔒 Supply Chain Scan: {project_root}")
    print(f"  依赖总数: {result.summary['total_dependencies']}")
    print(f"  直接依赖: {result.summary['direct_dependencies']}")
    print(f"  漏洞总数: {result.summary['vulnerabilities']}")
    print(f"    Critical: {result.summary['critical']}")
    print(f"    High:     {result.summary['high']}")
    print(f"    Medium:   {result.summary['medium']}")
    print(f"    Low:      {result.summary['low']}")
    print(f"  许可证问题: {result.summary['license_issues']}")

    if result.vulnerabilities:
        print("\n📋 漏洞详情:")
        for vuln in result.vulnerabilities:
            print(f"  [{vuln.severity.value.upper()}] {vuln.id}: {vuln.affected_package}@{vuln.affected_version}")
            print(f"    {vuln.summary[:100]}...")
            if vuln.fixed_version:
                print(f"    修复版本: {vuln.fixed_version}")

    if result.license_issues:
        print("\n⚖️  许可证问题:")
        for issue in result.license_issues:
            print(f"  {issue}")


def _output_scan_result(args: argparse.Namespace, project_root: Path, result: ScanResult) -> None:
    """按 --format 输出扫描结果 (text/json/sarif), 支持 --output 落盘。"""
    import json

    vuln_dicts = _scan_vulnerability_dicts(result)

    if args.format == "text":
        _print_scan_text(project_root, result)
    elif args.output:
        output_data = {
            "project": str(project_root),
            "scanned_at": result.scanned_at,
            "summary": result.summary,
            "vulnerabilities": vuln_dicts,
            "license_issues": result.license_issues,
        }
        args.output.write_text(json.dumps(output_data, indent=2, ensure_ascii=False))
        print(f"Results written to {args.output}")
    elif args.format == "json":
        payload = {
            "project": str(project_root),
            "scanned_at": result.scanned_at,
            "summary": result.summary,
            "vulnerabilities": vuln_dicts,
            "license_issues": result.license_issues,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    elif args.format == "sarif":
        sarif = _to_sarif_supply_chain(result)
        print(json.dumps(sarif, indent=2))


def _handle_supply_chain_sbom(args: argparse.Namespace) -> int:
    """Handle supply-chain sbom subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    scanner = SupplyChainScanner()
    sbom = scanner.generate_sbom(project_root, args.output)

    if args.format == "json":
        if args.output:
            print(f"SBOM written to {args.output}")
        else:
            print(sbom.to_json())
    elif args.format == "spdx":
        spdx = _to_spdx_tagvalue(sbom)
        if args.output:
            args.output.write_text(spdx)
            print(f"SBOM written to {args.output}")
        else:
            print(spdx)
    elif args.format == "cyclonedx":
        # CycloneDX format (simplified JSON)
        import json

        cyclonedx = _to_cyclonedx(sbom)
        if args.output:
            args.output.write_text(json.dumps(cyclonedx, indent=2))
            print(f"SBOM written to {args.output}")
        else:
            print(json.dumps(cyclonedx, indent=2))

    return 0


def _load_license_policy(policy_file: Path | None) -> dict[str, LicensePolicy] | None:
    """从 YAML 策略文件加载许可证白/黑名单。"""
    if not (policy_file and policy_file.exists()):
        return None

    import yaml

    with open(policy_file) as f:
        policy = yaml.safe_load(f)
    license_policy: dict[str, LicensePolicy] = {}
    for lic in policy.get("allowed_licenses", []):
        license_policy[lic] = LicensePolicy.ALLOW
    for lic in policy.get("disallowed_licenses", []):
        license_policy[lic] = LicensePolicy.DENY
    return license_policy


def _run_compliance_checks(project_root: Path, result: ScanResult) -> dict[str, Any]:
    """执行合规检查: 许可证问题与漏洞阈值。"""
    compliance: dict[str, Any] = {
        "project": str(project_root),
        "scanned_at": result.scanned_at,
        "passed": True,
        "violations": [],
        "warnings": [],
        "summary": result.summary,
    }

    for issue in result.license_issues:
        compliance["violations"].append({"type": "license", "message": issue, "severity": "high"})
        compliance["passed"] = False

    for vuln in result.vulnerabilities:
        message = f"{vuln.id}: {vuln.affected_package}@{vuln.affected_version} - {vuln.summary}"
        if vuln.severity in (Severity.CRITICAL, Severity.HIGH):
            compliance["violations"].append(
                {"type": "vulnerability", "message": message, "severity": vuln.severity.value}
            )
            compliance["passed"] = False
        elif vuln.severity == Severity.MEDIUM:
            compliance["warnings"].append({"type": "vulnerability", "message": message, "severity": "medium"})

    return compliance


def _print_compliance_text(project_root: Path, compliance: dict[str, Any]) -> None:
    """文本格式输出合规结果。"""
    print(f"\n📋 Supply Chain Compliance: {project_root}")
    print(f"  Status: {'✅ PASSED' if compliance['passed'] else '❌ FAILED'}")
    print(f"  Violations: {len(compliance['violations'])}")
    print(f"  Warnings: {len(compliance['warnings'])}")

    if compliance["violations"]:
        print("\n❌ Violations:")
        for v in compliance["violations"]:
            print(f"  [{str(v['severity']).upper()}] {v['message']}")

    if compliance["warnings"]:
        print("\n⚠️ Warnings:")
        for w in compliance["warnings"]:
            print(f"  [{str(w['severity']).upper()}] {w['message']}")


def _output_compliance(args: argparse.Namespace, project_root: Path, compliance: dict[str, Any]) -> None:
    """按 --format 输出合规报告。"""
    import json

    if args.format == "text":
        _print_compliance_text(project_root, compliance)
    elif args.format == "json":
        print(json.dumps(compliance, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(compliance, indent=2, ensure_ascii=False))
        print(f"Compliance report written to {args.output}")


def _handle_supply_chain_compliance(args: argparse.Namespace) -> int:
    """Handle supply-chain compliance subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    _load_license_policy(args.policy_file)
    scanner = SupplyChainScanner()
    result = scanner.scan_project(project_root)

    compliance = _run_compliance_checks(project_root, result)
    _output_compliance(args, project_root, compliance)

    return 0 if compliance["passed"] else 1


def _check_dependency_freshness(project_root: Path, max_age: int) -> dict[str, Any]:
    """检查依赖新鲜度 (当前实现将全部依赖归为 unknown)。"""
    import datetime

    scanner = SupplyChainScanner()
    sbom = scanner.sbom_generator.generate_from_project(project_root)
    all_deps = scanner._flatten_deps(sbom.packages)

    result: dict[str, Any] = {
        "project": str(project_root),
        "checked_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "max_age_days": max_age,
        "total_dependencies": len(all_deps),
        "fresh": [],
        "stale": [],
        "unknown": [],
    }

    for dep in all_deps:
        # 真实实现应查询注册表获取最近更新日期; 当前归为 unknown
        result["unknown"].append({"name": dep.name, "version": dep.version, "ecosystem": dep.ecosystem})

    return result


def _print_freshness_text(project_root: Path, report: dict[str, Any]) -> None:
    """文本格式输出新鲜度报告。"""
    print(f"\n📅 Dependency Freshness: {project_root}")
    print(f"  Max age: {report['max_age_days']} days")
    print(f"  Total dependencies: {report['total_dependencies']}")
    print(f"  Fresh: {len(report['fresh'])}")
    print(f"  Stale: {len(report['stale'])}")
    print(f"  Unknown: {len(report['unknown'])}")

    if report["stale"]:
        print("\n📦 Stale dependencies:")
        for d in report["stale"]:
            print(
                f"  {d['name']}@{d['version']} ({d['ecosystem']}) - last updated {d.get('days_since_update', 'N/A')} days ago"
            )


def _handle_supply_chain_freshness(args: argparse.Namespace) -> int:
    """Handle supply-chain freshness subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    import json

    report = _check_dependency_freshness(project_root, args.max_age_days)

    if args.format == "text":
        _print_freshness_text(project_root, report)
    elif args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Freshness report written to {args.output}")

    return 0


def _verify_packages(project_root: Path) -> dict[str, Any]:
    """逐依赖执行签名验证并汇总结果。"""
    import datetime

    scanner = SupplyChainScanner()
    sbom = scanner.sbom_generator.generate_from_project(project_root)
    all_deps = scanner._flatten_deps(sbom.packages)

    result: dict[str, Any] = {
        "project": str(project_root),
        "verified_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "total_packages": len(all_deps),
        "verified": [],
        "unverified": [],
        "failed": [],
    }

    for dep in all_deps:
        if dep.ecosystem != "pypi":
            result["unverified"].append(
                {"name": dep.name, "version": dep.version, "reason": f"No verifier for {dep.ecosystem}"}
            )
            continue
        vres = scanner.signature_verifier.verify_pypi_package(dep.name, dep.version)
        if vres.get("verified"):
            result["verified"].append({"name": dep.name, "version": dep.version, "details": vres})
        else:
            result["unverified"].append(
                {"name": dep.name, "version": dep.version, "reason": vres.get("error", "No verification data")}
            )

    return result


def _print_verify_text(project_root: Path, report: dict[str, Any]) -> None:
    """文本格式输出验证报告。"""
    print(f"\n🔐 Supply Chain Verification: {project_root}")
    print(f"  Total packages: {report['total_packages']}")
    print(f"  Verified: {len(report['verified'])}")
    print(f"  Unverified: {len(report['unverified'])}")
    print(f"  Failed: {len(report['failed'])}")

    if report["unverified"]:
        print("\n⚠️ Unverified packages:")
        for u in report["unverified"][:10]:
            print(f"  {u['name']}@{u['version']}: {u['reason']}")
        if len(report["unverified"]) > 10:
            print(f"  ... and {len(report['unverified']) - 10} more")


def _handle_supply_chain_verify(args: argparse.Namespace) -> int:
    """Handle supply-chain verify subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    import json

    report = _verify_packages(project_root)

    if args.format == "text":
        _print_verify_text(project_root, report)
    elif args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Verification report written to {args.output}")

    # 存在未验证包时返回非零 (严格模式)
    return 0 if not report["unverified"] else 1


def _handle_sbom(args: argparse.Namespace) -> int:
    """Handle sbom command."""

    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    scanner = SupplyChainScanner()
    sbom = scanner.generate_sbom(project_root, args.output)

    if args.format == "json":
        if args.output:
            print(f"SBOM written to {args.output}")
        else:
            print(sbom.to_json())
    elif args.format == "spdx":
        # SPDX tag-value format (简化版)
        spdx = _to_spdx_tagvalue(sbom)
        if args.output:
            args.output.write_text(spdx)
            print(f"SBOM written to {args.output}")
        else:
            print(spdx)

    return 0


def _handle_verify_signature(args: argparse.Namespace) -> int:
    """Handle verify-signature command."""
    from tools.scripts.supply_chain import SignatureVerifier

    verifier = SignatureVerifier()

    if args.cosign:
        result = verifier.verify_cosign_signature(args.cosign, args.cosign_key)
        if args.format == "text":
            status = "✅ Verified" if result["verified"] else "❌ Failed"
            print(f"Cosign verification: {status}")
            print(f"Image: {args.cosign}")
            if result.get("output"):
                print(f"Output: {result['output']}")
            if result.get("error"):
                print(f"Error: {result['error']}")
        elif args.format == "json":
            import json

            print(json.dumps(result, indent=2))
        return 0 if result["verified"] else 1

    if args.slsa:
        result = verifier.verify_slsa_provenance(args.slsa)
        if args.format == "text":
            status = "✅ Verified" if result["verified"] else "❌ Failed"
            print(f"SLSA provenance verification: {status}")
            print(f"Package: {args.slsa}")
            print(f"Message: {result.get('message', '')}")
        elif args.format == "json":
            import json

            print(json.dumps(result, indent=2))
        return 0 if result["verified"] else 1

    print("Specify --cosign or --slsa")
    return 1


def _make_exception_manager() -> EnhancedExceptionManager:
    """创建例外管理器实例。"""
    return create_enhanced_manager(
        config_path=Path(".jcode/governance.yaml"),
        repo_path=Path("."),
    )


def _exception_request(manager: EnhancedExceptionManager, args: argparse.Namespace) -> int:
    """处理 exception request 子命令。"""
    paths = [p.strip() for p in args.paths.split(",")]
    reviewers = [r.strip() for r in args.reviewers.split(",")] if args.reviewers else None

    req = manager.request_exception(
        rule_id=args.rule_id,
        paths=paths,
        reason=args.reason,
        severity=args.severity,
        requested_severity=args.requested_severity,
        expires=args.expires,
        created_by=args.created_by,
        reviewers=reviewers,
    )

    print(f"✅ Exception request created: {req.id}")
    print(f"   Rule: {req.rule_id}")
    print(f"   Paths: {', '.join(req.paths)}")
    print(f"   Reason: {req.reason}")
    print(f"   Severity: {req.severity} -> {req.requested_severity}")
    print(f"   Expires: {req.expires or 'Never'}")
    print(f"   Status: {req.status.value}")
    return 0


def _exception_review(manager: EnhancedExceptionManager, args: argparse.Namespace, action: str) -> int:
    """处理 approve/reject/revoke 三个审批动作。"""
    if action == "approve":
        ok, fail_msg = (
            manager.approve_exception(args.request_id, args.reviewer, args.comment),
            "not approved (may not be pending)",
        )
        ok_msg = "approved"
    elif action == "reject":
        ok, fail_msg = (
            manager.reject_exception(args.request_id, args.reviewer, args.comment),
            "not rejected (may not be pending)",
        )
        ok_msg = "rejected"
    else:
        ok, fail_msg = manager.revoke_exception(args.request_id), "not found"
        ok_msg = "revoked"

    if ok:
        print(f"✅ Exception {args.request_id} {ok_msg}")
        return 0
    print(f"❌ Exception {args.request_id} {fail_msg}")
    return 1


def _exception_list(manager: EnhancedExceptionManager, args: argparse.Namespace) -> int:
    """处理 exception list 子命令。"""
    status_filter = ExceptionStatus(args.status) if args.status else None
    requests = manager.approval.list_requests(status_filter)

    if not requests:
        print("No exception requests found")
        return 0

    for req in requests:
        status_icon = {
            ExceptionStatus.PENDING: "⏳",
            ExceptionStatus.APPROVED: "✅",
            ExceptionStatus.REJECTED: "❌",
            ExceptionStatus.EXPIRED: "⏰",
            ExceptionStatus.REVOKED: "🚫",
        }.get(req.status, "?")
        print(f"{status_icon} {req.id} [{req.status.value}] {req.rule_id} - {req.created_by} ({req.created_at[:10]})")
        if req.expires:
            print(f"    Expires: {req.expires}")
    return 0


def _exception_check_expirations(manager: EnhancedExceptionManager) -> int:
    """处理 check-expirations 子命令。"""
    alerts = manager.check_expirations()
    if not alerts:
        print("✅ No exceptions expiring soon")
        return 0

    print(f"⚠️  Found {len(alerts)} expiring exception(s):")
    for alert in alerts:
        print(f"  [{alert.days_until_expiry}d] {alert.request_id} - {alert.rule_id} (expires {alert.expires_at})")
    return 0


def _exception_sync_gitops(manager: EnhancedExceptionManager) -> int:
    """处理 sync-gitops 子命令。"""
    if not manager.gitops:
        print("❌ GitOps not configured (repo_path required)")
        return 1

    manager.gitops.pull_latest()
    success = manager.gitops.sync_to_git(manager.get_all_requests())
    if success:
        print("✅ Exceptions synced to GitOps repo")
        return 0
    print("❌ Failed to sync exceptions")
    return 1


def _handle_exception(args: argparse.Namespace) -> int:
    """Handle exception command."""
    manager = _make_exception_manager()
    action = args.exception_action

    if action == "request":
        return _exception_request(manager, args)
    if action in ("approve", "reject", "revoke"):
        return _exception_review(manager, args, action)
    if action == "list":
        return _exception_list(manager, args)
    if action == "check-expirations":
        return _exception_check_expirations(manager)
    if action == "audit":
        import json

        report = manager.generate_audit_report()
        print(json.dumps(report, indent=2, ensure_ascii=False))
        return 0
    if action == "sync-gitops":
        return _exception_sync_gitops(manager)

    print(f"Unknown exception action: {action}")
    return 1


def _emit_or_write(output: str, output_path: Path | None, label: str) -> None:
    """输出到文件或 stdout 的公共助手。"""
    if output_path:
        output_path.write_text(output)
        print(f"{label} written to {output_path}")
    else:
        print(output)


def _dep_graph_build(project_root: Path) -> DependencyGraph:
    """生成 SBOM 并构建依赖图。"""
    scanner = SupplyChainScanner()
    sbom = scanner.generate_sbom(project_root)
    return analyze_dependency_graph(project_root, sbom)


def _dep_graph_analyze(graph: DependencyGraph, args: argparse.Namespace) -> int:
    """处理 dep-graph analyze 子命令。"""
    import json

    if args.format == "json":
        output = graph.to_json()
    elif args.format == "graphviz":
        output = graph.export_graphviz(args.output)
    elif args.format == "mermaid":
        output = graph.export_mermaid(args.output)
    else:  # tree
        dep_tree = graph.get_dependency_tree(max_depth=args.max_depth)
        output = json.dumps(dep_tree, indent=2, ensure_ascii=False)

    _emit_or_write(output, args.output, "Dependency graph")
    return 0


def _dep_graph_circular(graph: DependencyGraph, args: argparse.Namespace) -> int:
    """处理 dep-graph circular 子命令。"""
    import json

    cycles: list[CircularDependency] = graph.detect_circular_dependencies()
    output = json.dumps(
        [{"cycle": c.cycle, "ecosystems": c.ecosystems, "severity": c.severity} for c in cycles],
        indent=2,
        ensure_ascii=False,
    )
    _emit_or_write(output, args.output, "Circular dependencies")

    if cycles:
        print(f"\n⚠️  Found {len(cycles)} circular dependency(ies)")
        for c in cycles:
            print(f"  {' -> '.join(c.cycle)}")
        return 1
    print("✅ No circular dependencies found")
    return 0


def _dep_graph_conflicts(graph: DependencyGraph, args: argparse.Namespace) -> int:
    """处理 dep-graph conflicts 子命令。"""
    import json

    conflicts: list[DependencyConflict] = graph.detect_conflicts()
    output = json.dumps(
        [{"package": conf.package_name, "versions": conf.versions, "severity": conf.severity} for conf in conflicts],
        indent=2,
        ensure_ascii=False,
    )
    _emit_or_write(output, args.output, "Conflicts")

    if conflicts:
        print(f"\n⚠️  Found {len(conflicts)} version conflict(s)")
        for conf in conflicts:
            print(f"  {conf.package_name}: {list(conf.versions.keys())}")
        return 1
    print("✅ No version conflicts found")
    return 0


def _dep_graph_impact(graph: DependencyGraph, args: argparse.Namespace) -> int:
    """处理 dep-graph impact 子命令。"""
    import json

    impacts = graph.analyze_impact(args.package, args.version)
    output = json.dumps(
        [
            {
                "package": i.package,
                "version": i.version,
                "direct_dependents": i.direct_dependents,
                "transitive_dependents": i.transitive_dependents,
                "total_affected": i.total_affected,
                "critical_path": i.critical_path,
            }
            for i in impacts
        ],
        indent=2,
        ensure_ascii=False,
    )
    _emit_or_write(output, args.output, "Impact analysis")

    if not impacts:
        print(f"Package {args.package} not found in dependencies")
        return 1

    for i in impacts:
        print(f"\nPackage: {i.package}@{i.version}")
        print(f"  Direct dependents: {len(i.direct_dependents)}")
        print(f"  Transitive dependents: {len(i.transitive_dependents)}")
        print(f"  Total affected: {i.total_affected}")
        if i.critical_path:
            print(f"  Critical path: {' -> '.join(i.critical_path)}")

    return 0


def _handle_dep_graph(args: argparse.Namespace) -> int:
    """Handle dep-graph command."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    graph = _dep_graph_build(project_root)
    action = args.dep_graph_action

    handlers = {
        "analyze": _dep_graph_analyze,
        "circular": _dep_graph_circular,
        "conflicts": _dep_graph_conflicts,
        "impact": _dep_graph_impact,
    }
    handler = handlers.get(action)
    if handler is None:
        print(f"Unknown dep-graph action: {action}")
        return 1
    return handler(graph, args)


def _to_sarif_supply_chain(result: ScanResult) -> dict[str, Any]:
    """Convert supply chain result to SARIF format"""
    rules = {}
    results = []

    for vuln in result.vulnerabilities:
        rule_id = vuln.id
        if rule_id not in rules:
            rules[rule_id] = {
                "id": rule_id,
                "name": vuln.id,
                "shortDescription": {"text": vuln.summary[:100]},
                "fullDescription": {"text": vuln.summary},
                "defaultConfiguration": {"level": _severity_to_sarif_level(vuln.severity)},
                "properties": {"tags": ["security", "supply-chain", vuln.source]},
            }
        results.append(
            {
                "ruleId": rule_id,
                "level": _severity_to_sarif_level(vuln.severity),
                "message": {"text": f"{vuln.affected_package}@{vuln.affected_version}: {vuln.summary}"},
                "locations": [
                    {
                        "physicalLocation": {
                            "artifactLocation": {"uri": result.project_path},
                            "region": {"startLine": 1},
                        }
                    }
                ],
            }
        )

    return {
        "$schema": "https://schemastore.org/schemas/json/sarif-2.1.0.json",
        "version": "2.1.0",
        "runs": [
            {
                "tool": {
                    "driver": {
                        "name": "JCode Supply Chain Scanner",
                        "version": "1.0.0",
                        "rules": list(rules.values()),
                    }
                },
                "results": results,
            }
        ],
    }


def _severity_to_sarif_level(severity: Severity) -> str:
    mapping = {
        Severity.CRITICAL: "error",
        Severity.HIGH: "error",
        Severity.MEDIUM: "warning",
        Severity.LOW: "note",
        Severity.NONE: "note",
    }
    return mapping.get(severity, "note")


def _to_spdx_tagvalue(sbom: SBOM) -> str:
    """Convert SBOM to SPDX tag-value format"""
    lines = [
        "SPDXVersion: SPDX-2.3",
        "DataLicense: CC0-1.0",
        "SPDXID: SPDXRef-DOCUMENT",
        f"DocumentName: {sbom.name}",
        f"DocumentNamespace: https://jcode.dev/sbom/{sbom.name}-{sbom.version}",
        f"Created: {sbom.created_at}",
        "Creator: Tool: JCode Supply Chain Scanner",
        "",
    ]

    for i, pkg in enumerate(sbom.packages):
        lines.extend(
            [
                f"PackageName: {pkg.name}",
                f"SPDXID: SPDXRef-Package-{i}",
                f"PackageVersion: {pkg.version}",
                "PackageSupplier: NOASSERTION",
                "PackageDownloadLocation: NOASSERTION",
                "FilesAnalyzed: false",
                f"LicenseConcluded: {pkg.license or 'NOASSERTION'}",
                f"LicenseDeclared: {pkg.license or 'NOASSERTION'}",
                "CopyrightText: NOASSERTION",
                "",
            ]
        )

    return "\n".join(lines)


def _to_cyclonedx(sbom: SBOM) -> dict[str, Any]:
    """Convert SBOM to CycloneDX format (simplified)"""
    components = []
    for pkg in sbom.packages:
        components.append(
            {
                "type": "library",
                "name": pkg.name,
                "version": pkg.version,
                "purl": f"pkg:{pkg.ecosystem}/{pkg.name}@{pkg.version}",
                "licenses": [{"license": {"name": pkg.license or "NOASSERTION"}}] if pkg.license else [],
            }
        )

    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{sbom.name}-{sbom.version}",
        "metadata": {
            "timestamp": sbom.created_at,
            "tools": [{"name": "JCode Supply Chain Scanner", "version": "1.0"}],
            "component": {"name": sbom.name, "version": sbom.version},
        },
        "components": components,
    }


def _handle_install_hooks(args: argparse.Namespace) -> int:
    """Handle install-hooks command."""
    if args.pre_push:
        from tools.scripts.hooks.pre_push import install_pre_push_hook

        success = install_pre_push_hook()
        return 0 if success else 1
    if args.pre_commit:
        print("Pre-commit hook installation not yet implemented")
        return 1
    print("Specify --pre-push or --pre-commit")
    return 1


def _handle_learn(args: argparse.Namespace) -> int:
    """Handle learn command."""
    from tools.scripts.rules_engine.ai_rules_generator import (
        analyze_project,
        format_analysis,
    )

    result = analyze_project(args.project_path)
    print(format_analysis(result, format=args.format))
    if args.output:
        import yaml

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            yaml.dump(result["rules"], f, default_flow_style=False, allow_unicode=True)
        print(f"\nRules written to {args.output}")
    return 0


def _handle_dashboard(args: argparse.Namespace) -> int:
    """Handle dashboard command."""
    import uvicorn

    from tools.scripts.app_config import get_path
    from tools.scripts.rules_engine.dashboard import create_app

    db_path = getattr(args, "db", None) or str(get_path("trend_db", Path("adg_quality.db")))
    app = create_app(db_path)
    print(f"Starting ADG Quality Dashboard at http://0.0.0.0:{args.port}")  # nosec - dev only
    uvicorn.run(app, host="0.0.0.0", port=args.port)  # nosec - dev only
    return 0


def _handle_docs_validate(args: argparse.Namespace) -> int:
    """治理文档验证统一入口：validate/check-index/sync-refs/full。"""
    action = getattr(args, "action2", "validate")
    result = subprocess.run(
        [
            sys.executable,
            str(Path(__file__).resolve().parent.parent.parent / ".jcode" / "scripts" / "governance-docs-validator.py"),
            action,
        ],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    return result.returncode


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

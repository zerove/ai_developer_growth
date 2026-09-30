"""Hooks runner: argparse 解析器构建域（P2-1 第三刀）。

_build_parser 与全部 _add_* 子命令注册函数。由 hooks_runner.py import 转发。
"""

from __future__ import annotations

import argparse
from pathlib import Path


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

    # CI 存活心跳（ADR-057）：检测门禁自身是否还活着，必须在 CI 之外运行
    heartbeat_parser = subparsers.add_parser(
        "ci-heartbeat",
        help="Check whether remote CI actually ran jobs (must run outside CI, see ADR-057)",
    )
    heartbeat_parser.add_argument("--repo", default="", help="owner/name (default: from env or git remote)")
    heartbeat_parser.add_argument("--workflow", default="ci.yml", help="Workflow file to probe")
    heartbeat_parser.add_argument("--stale-hours", type=int, default=24, help="Stale threshold in hours")
    heartbeat_parser.add_argument("--json", action="store_true", help="JSON output")

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

    db_maintain_parser = subparsers.add_parser("db-maintain", help="统一存储维护：裁剪运行历史（保留窗口）并回收空间")
    db_maintain_parser.add_argument("--retention-days", type=int, default=90, help="运行历史保留天数 (default: 90)")
    db_maintain_parser.add_argument("--db", help="SQLite database path (default: [tool.adg].trend_db)")

    full_parser = subparsers.add_parser(
        "full",
        help="Run all checks (lint, format, typecheck, test, security, quality-gate, governance-audit)",
    )
    full_parser.add_argument("--lang", help="Comma-separated languages (auto-detect if not specified)")
    full_parser.add_argument("--path", type=Path, default=Path("."), help="Project root path")

"""Hooks runner: exception / dep-graph / install-hooks / learn / db / dashboard 命令域。

从 hooks_runner.py 拆出（P2-1 第二刀），由原模块 import 转发保持入口兼容。
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from pathlib import Path

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
from tools.scripts.supply_chain import SupplyChainScanner

logger = logging.getLogger(__name__)


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


def _handle_db_maintain(args: argparse.Namespace) -> int:
    """统一存储维护：裁剪运行历史（E 项保留策略）并回收空间。"""
    from tools.scripts.app_config import get_path
    from tools.scripts.rules_engine.store import CheckStore

    db_path = getattr(args, "db", None) or str(get_path("trend_db", Path("adg_quality.db")))
    retention = int(getattr(args, "retention_days", 90))
    try:
        store = CheckStore(db_path)
    except Exception as exc:  # noqa: BLE001 - 存储打不开属用户可见故障，必须报错并返回非零
        print(f"❌ 无法打开统一存储 {db_path}: {exc}")
        return 1

    try:
        deleted = store.prune_history(retention_days=retention)
        stats = store.cache_hit_rate()
        print(f"✅ 运行历史裁剪完成: 删除 {deleted} 条运行记录 (保留窗口 {retention} 天)")
        print(f"   当前缓存文件数: {stats['cached_files']}")
        return 0
    finally:
        _close_store_quietly(store)


def _close_store_quietly(store: object) -> None:
    """静默关闭 CheckStore 连接（维护命令收尾用）。"""
    close = getattr(store, "close", None)
    if callable(close):
        try:
            close()
        except Exception:  # noqa: BLE001 - 关闭连接失败属收尾清理，不得掩盖主流程返回值
            pass


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

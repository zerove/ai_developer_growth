"""Hooks runner: supply-chain / SBOM / auto-fix 命令域实现。

从 hooks_runner.py 拆出（P2-1 结构优化），由原模块 import 复用，
命令行为与拆分前完全一致。"""

from __future__ import annotations

import argparse
import json
import logging
from pathlib import Path
from typing import Any

from tools.scripts.auto_fix import AutoFixOrchestrator, FixResult, FixSafetyLevel, FixStrategy
from tools.scripts.rules_engine.models import CheckResult
from tools.scripts.supply_chain import (
    SBOM,
    Dependency,
    LicensePolicy,
    ScanResult,
    Severity,
    SignatureVerifier,
    SupplyChainScanner,
    Vulnerability,
)
from tools.scripts.supply_chain import (
    PyPIMetadataClient as PyPIMetadataClient,
)

logger = logging.getLogger(__name__)


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
    """文本格式输出修复结果 (V2.21 P5-65 拆分: 抽 _compute_fix_totals + _print_fix_details)."""
    total_applied, total_skipped, total_errors = _compute_fix_totals(fix_results)

    print("\n🔧 Auto-fix 完成")
    print(f"  应用: {total_applied}")
    print(f"  跳过: {total_skipped}")
    print(f"  错误: {total_errors}")

    for result in fix_results:
        _print_fix_details(result)


def _compute_fix_totals(fix_results: list[FixResult]) -> tuple[int, int, int]:
    """计算修复总数 (applied/skipped/errors 三元组, 模块级 helper).

    Args:
        fix_results: FixResult 列表

    Returns:
        (total_applied, total_skipped, total_errors) 三元组
    """
    total_applied = sum(len(r.applied) for r in fix_results)
    total_skipped = sum(len(r.skipped) for r in fix_results)
    total_errors = sum(len(r.errors) for r in fix_results)
    return total_applied, total_skipped, total_errors


def _print_fix_details(result: FixResult) -> None:
    """打印单文件修复详情 (模块级 helper).

    Args:
        result: 单个 FixResult
    """
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

    policy_file = getattr(args, "policy_file", None)
    # 传入策略文件时, 许可证策略必须真正生效: 补齐许可证后, 命中禁用
    # 许可证即视为违规 (与漏洞阈值同级阻断)。
    policy = _load_license_policy(policy_file) if policy_file else None
    scanner = SupplyChainScanner(license_policy=policy)
    result = scanner.scan_project(project_root)

    _, fail_level = _scan_severity_threshold(args)
    should_fail = _scan_has_failing_vulns(result.vulnerabilities, fail_level)

    if policy_file:
        _resolve_licenses(scanner, result, PyPIMetadataClient())
        should_fail = should_fail or bool(result.license_issues)

    diff = _compute_review_ledger_diff(args, result.summary)
    review_new = _review_new_failures(diff) if getattr(args, "fail_on_review_new", False) else 0
    if review_new:
        should_fail = True
        print(f"❌ License review ratchet: {review_new} new review item(s) vs baseline")
    _output_scan_result(args, project_root, result)
    if diff is not None and args.format == "text":
        _print_review_ledger_diff(diff)
    _write_review_ledger(args, project_root, result.scanned_at, result.summary, diff)

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
    print(f"  待复核许可证: {result.summary.get('license_review', 0)}")
    unreachable = result.summary.get("license_review_unreachable", 0)
    unknown = result.summary.get("license_review_unknown", 0)
    if unreachable or unknown:
        print(f"    其中 PyPI 元数据不可达: {unreachable}")
        print(f"    许可证未声明/未知: {unknown}")

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

    if result.license_review:
        print("\n🔍 待复核许可证:")
        for issue in result.license_review:
            print(f"  {issue}")


def _output_scan_result(args: argparse.Namespace, project_root: Path, result: ScanResult) -> None:
    """按 --format 输出扫描结果 (text/json/sarif), 支持 --output 落盘。"""

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
            "license_review": result.license_review,
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
            "license_review": result.license_review,
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


def _resolve_licenses(scanner: SupplyChainScanner, result: ScanResult, client: PyPIMetadataClient) -> None:
    """补齐依赖许可证并重算许可证策略。

    清单文件 (pyproject/requirements) 不声明依赖自身的许可证, 扫描结果里的
    license 恒为 None → 全部落进"待复核"分支, 合规检查失去判别力。这里从
    PyPI 元数据补齐许可证, 再按策略重算 (禁用许可证 → 阻断项)。
    """
    for dep in result.dependencies:
        if dep.license or dep.ecosystem != "pypi":
            continue
        dep.license = client.license_of(dep.name)
    result.license_issues, result.license_review = scanner.license_checker.evaluate_dependencies(result.dependencies)
    _attribute_license_review(result, client)


def _attribute_license_review(result: ScanResult, client: PyPIMetadataClient) -> None:
    """按成因归因许可证待复核项, 写入摘要显式统计与复核台账 (盘点可观测性)。

    license_review 混合三种成因: copyleft (已知许可证需人工评估)、PyPI 元数据
    不可达 (网络抖动, 重试可能消失)、许可证确实未声明/未知 (PyPI 可达但拿不到,
    或包不存在)。摘要只显式区分后两者 (许可证仍为 None 的部分), 归因依据与
    _verify_one_dependency 相同的判别式: metadata 为 None 且非 404 → 不可达。

    同时生成 `license_review_items` 台账条目 (机器可读): 每条包含依赖标识、
    许可证原值、策略与成因, 便于周期盘点与复核跟进 (JSON/--output 随 summary
    透出, 不改变既有 license_review 字符串列表的兼容语义)。

    Args:
        result: 扫描结果 (原地更新 summary)
        client: PyPI 元数据客户端 (进程内缓存, 元数据查询已预热)
    """
    unreachable = unknown = 0
    items: list[dict[str, object]] = []
    for dep in result.dependencies:
        if dep.license_policy != LicensePolicy.REVIEW:
            continue
        if not dep.license and dep.ecosystem == "pypi":
            if client.metadata(dep.name) is None and not client.package_missing(dep.name):
                cause = "unreachable"
                unreachable += 1
            else:
                cause = "unknown_license"
                unknown += 1
        elif not dep.license:
            cause = "unknown_license"
        else:
            cause = "policy_review"
        items.append(
            {
                "name": dep.name,
                "version": dep.version,
                "ecosystem": dep.ecosystem,
                "license": dep.license,
                "policy": dep.license_policy.value,
                "cause": cause,
                "message": f"REVIEW needed: {dep.name}@{dep.version} ({dep.license})",
            }
        )
    result.summary["license_review_unreachable"] = unreachable
    result.summary["license_review_unknown"] = unknown
    result.summary["license_review_items"] = items


def _run_compliance_checks(project_root: Path, result: ScanResult) -> dict[str, Any]:
    """执行合规检查: 许可证问题与漏洞阈值。

    阻断项 (passed=False): 明确禁止的许可证 + critical/high 漏洞。
    告警项: 待人工复核的许可证 (未知 / copyleft) + medium 漏洞 ——
    未知许可证不等于违规, 阻断会让任何未声明许可证的项目恒红。
    """
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

    for issue in result.license_review:
        compliance["warnings"].append({"type": "license", "message": issue, "severity": "medium"})

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

    summary = compliance.get("summary", {})
    review = summary.get("license_review", 0)
    if review:
        print(f"  待复核许可证 (license_review): {review}")
        unreachable = summary.get("license_review_unreachable", 0)
        unknown = summary.get("license_review_unknown", 0)
        if unreachable or unknown:
            print(f"    其中 PyPI 元数据不可达: {unreachable}")
            print(f"    许可证未声明/未知: {unknown}")

    if compliance["violations"]:
        print("\n❌ Violations:")
        for v in compliance["violations"]:
            print(f"  [{str(v['severity']).upper()}] {v['message']}")

    if compliance["warnings"]:
        print("\n⚠️ Warnings:")
        for w in compliance["warnings"]:
            print(f"  [{str(w['severity']).upper()}] {w['message']}")


def _ledger_item_key(item: dict[str, object]) -> tuple[str, str, str]:
    """复核台账项稳定键 (ecosystem, name, version)。"""
    return (
        str(item.get("ecosystem", "")),
        str(item.get("name", "")),
        str(item.get("version", "")),
    )


def _load_review_ledger_baseline(path: Path) -> list[dict[str, object]]:
    """加载基线台账 JSON 并返回 items 列表。"""
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict) and isinstance(data.get("items"), list):
        return [it for it in data["items"] if isinstance(it, dict)]
    if isinstance(data, list):
        return [it for it in data if isinstance(it, dict)]
    raise ValueError("invalid ledger format: expected object with items list")


def _diff_review_ledger(
    current_items: list[dict[str, object]], baseline_items: list[dict[str, object]], baseline_path: Path
) -> dict[str, object]:
    """对比当前台账与基线, 返回新增/移除/变更/未变统计。"""
    cur = {_ledger_item_key(it): it for it in current_items}
    base = {_ledger_item_key(it): it for it in baseline_items}
    added_keys = sorted(set(cur) - set(base))
    removed_keys = sorted(set(base) - set(cur))
    common_keys = sorted(set(cur) & set(base))

    def _sig(it: dict[str, object]) -> tuple[str, str, str, str]:
        return (
            str(it.get("cause", "")),
            str(it.get("license", "")),
            str(it.get("policy", "")),
            str(it.get("message", "")),
        )

    changed = []
    unchanged = 0
    for key in common_keys:
        if _sig(cur[key]) != _sig(base[key]):
            changed.append({"key": key, "from": base[key], "to": cur[key]})
        else:
            unchanged += 1

    return {
        "baseline_path": str(baseline_path),
        "added": [cur[k] for k in added_keys],
        "removed": [base[k] for k in removed_keys],
        "changed": changed,
        "unchanged": unchanged,
        "summary": {
            "added": len(added_keys),
            "removed": len(removed_keys),
            "changed": len(changed),
            "unchanged": unchanged,
        },
    }


def _print_review_ledger_diff(diff: dict[str, object]) -> None:
    """文本输出复核台账差异摘要。"""
    raw_summary = diff.get("summary")
    s: dict[str, object] = raw_summary if isinstance(raw_summary, dict) else {}
    print(
        "  License review ledger diff: "
        f"+{s.get('added', 0)} -{s.get('removed', 0)} ~{s.get('changed', 0)} ={s.get('unchanged', 0)}"
    )
    baseline_path = diff.get("baseline_path")
    if baseline_path:
        print(f"    baseline: {baseline_path}")


def _compute_review_ledger_diff(args: argparse.Namespace, summary: dict[str, object]) -> dict[str, object] | None:
    """按需计算复核台账差异并写回 summary。"""
    baseline_path = getattr(args, "review_ledger_baseline", None)
    if not baseline_path:
        return None
    items = summary.get("license_review_items", [])
    if not isinstance(items, list):
        items = []
    baseline_items = _load_review_ledger_baseline(baseline_path)
    diff = _diff_review_ledger([it for it in items if isinstance(it, dict)], baseline_items, baseline_path)
    summary["license_review_diff"] = diff
    return diff


def _review_new_failures(diff: dict[str, object] | None) -> int:
    """返回基线对比中新增的待复核项数量 (用于 ratchet)。"""
    if not diff:
        return 0
    summary = diff.get("summary")
    if not isinstance(summary, dict):
        return 0
    try:
        return int(summary.get("added", 0) or 0)
    except (TypeError, ValueError):
        return 0


def _build_review_ledger(
    project_root: Path, scanned_at: str, summary: dict[str, object], diff: dict[str, object] | None = None
) -> dict[str, object]:
    """构建 license review 复核台账 (机器可读, 便于周期盘点与对比)。"""
    items = summary.get("license_review_items", [])
    if not isinstance(items, list):
        items = []
    ledger: dict[str, object] = {
        "project": str(project_root),
        "scanned_at": scanned_at,
        "summary": {
            "license_review": summary.get("license_review", 0),
            "license_review_unreachable": summary.get("license_review_unreachable", 0),
            "license_review_unknown": summary.get("license_review_unknown", 0),
            "total_items": len(items),
        },
        "items": items,
    }
    if diff is not None:
        ledger["diff"] = diff
    return ledger


def _write_review_ledger(
    args: argparse.Namespace,
    project_root: Path,
    scanned_at: str,
    summary: dict[str, object],
    diff: dict[str, object] | None = None,
) -> None:
    """按需写出 license review 复核台账 JSON。"""
    ledger_path = getattr(args, "review_ledger", None)
    if not ledger_path:
        return
    ledger = _build_review_ledger(project_root, scanned_at, summary, diff)
    ledger_path.write_text(json.dumps(ledger, indent=2, ensure_ascii=False))
    print(f"License review ledger written to {ledger_path}")


def _output_compliance(
    args: argparse.Namespace,
    project_root: Path,
    compliance: dict[str, Any],
    diff: dict[str, object] | None = None,
) -> None:
    """按 --format 输出合规报告。"""

    if args.format == "text":
        _print_compliance_text(project_root, compliance)
        if diff is not None:
            _print_review_ledger_diff(diff)
    elif args.format == "json":
        print(json.dumps(compliance, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(compliance, indent=2, ensure_ascii=False))
        print(f"Compliance report written to {args.output}")

    _write_review_ledger(args, project_root, str(compliance.get("scanned_at", "")), compliance.get("summary", {}), diff)


def _handle_supply_chain_compliance(args: argparse.Namespace) -> int:
    """Handle supply-chain compliance subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    # 策略文件必须真正生效: 允许/禁止清单要参与许可证判定, 否则白名单形同虚设。
    policy = _load_license_policy(args.policy_file)
    scanner = SupplyChainScanner(license_policy=policy)
    result = scanner.scan_project(project_root)

    _resolve_licenses(scanner, result, PyPIMetadataClient())
    compliance = _run_compliance_checks(project_root, result)
    diff = _compute_review_ledger_diff(args, result.summary)
    if diff is not None:
        compliance["license_review_diff"] = diff
    review_new = _review_new_failures(diff) if getattr(args, "fail_on_review_new", False) else 0
    if review_new:
        compliance["passed"] = False
        compliance["violations"].append(
            {
                "type": "license_review",
                "message": f"New license review items vs baseline: {review_new}",
                "severity": "high",
            }
        )
    _output_compliance(args, project_root, compliance, diff)

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

    report = _check_dependency_freshness(project_root, args.max_age_days)

    if args.format == "text":
        _print_freshness_text(project_root, report)
    elif args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Freshness report written to {args.output}")

    return 0


def _verify_packages(project_root: Path, client: PyPIMetadataClient | None = None) -> dict[str, Any]:
    """逐依赖执行签名验证并汇总结果。"""
    import datetime

    scanner = SupplyChainScanner()
    sbom = scanner.sbom_generator.generate_from_project(project_root)
    all_deps = scanner._flatten_deps(sbom.packages)
    client = client or PyPIMetadataClient()

    result: dict[str, Any] = {
        "project": str(project_root),
        "verified_at": datetime.datetime.now(tz=datetime.timezone.utc).isoformat(),
        "total_packages": len(all_deps),
        "verified": [],
        "unverified": [],
        # 元数据不可达 (网络/超时) 的依赖: 无法判定, 与"包不存在"分开统计
        "unverifiable": [],
        "failed": [],
    }

    for dep in all_deps:
        if dep.ecosystem != "pypi":
            result["unverified"].append(
                {"name": dep.name, "version": dep.version, "reason": f"No verifier for {dep.ecosystem}"}
            )
            continue
        _verify_one_dependency(dep, scanner.signature_verifier, client, result)

    return result


def _verify_one_dependency(
    dep: Dependency,
    verifier: SignatureVerifier,
    client: PyPIMetadataClient,
    result: dict[str, Any],
) -> None:
    """校验单个 PyPI 依赖是否存在满足其声明约束的发布版本 (就地写入 result)。

    先按精确版本校验; 清单里的 ">=0.23" 只是下界 (PyPI 上真实版本是 0.23.0),
    精确版本查不到时再按约束符解析实际发布版本。

    Args:
        dep: 依赖项 (含 name / version / specifier)
        verifier: 签名验证器 (精确版本存在性)
        client: PyPI 元数据客户端
        result: 汇总结果 (原地更新)
    """
    exact = verifier.verify_pypi_package(dep.name, dep.version)
    if exact.get("verified"):
        result["verified"].append({"name": dep.name, "version": dep.version, "details": exact})
        return

    resolved = client.resolve_version(dep.name, dep.version, dep.specifier)
    if resolved is not None:
        result["verified"].append(
            {
                "name": dep.name,
                "version": dep.version,
                "details": {
                    "verified": True,
                    "message": f"PyPI 包 {dep.name} 存在, 声明约束匹配发布版本 {resolved}",
                    "name": dep.name,
                    "declared_version": dep.version,
                    "resolved_version": resolved,
                    "release_files": len(client.release_versions(dep.name)),
                },
            }
        )
        return

    if client.metadata(dep.name) is None and not client.package_missing(dep.name):
        result["unverifiable"].append({"name": dep.name, "version": dep.version, "reason": "PyPI metadata unreachable"})
        return

    reason = exact.get("error") or "No verification data"
    if client.package_missing(dep.name):
        reason = "Package not found on PyPI"
    result["unverified"].append({"name": dep.name, "version": dep.version, "reason": reason})


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

    if report.get("unverifiable"):
        print("\n🌐 Unverifiable packages (PyPI 元数据不可达):")
        for u in report["unverifiable"][:10]:
            print(f"  {u['name']}@{u['version']}: {u['reason']}")
        if len(report["unverifiable"]) > 10:
            print(f"  ... and {len(report['unverifiable']) - 10} more")


def _handle_supply_chain_verify(args: argparse.Namespace) -> int:
    """Handle supply-chain verify subcommand."""
    project_root = args.path
    if not project_root.exists():
        print(f"Path not found: {project_root}")
        return 1

    report = _verify_packages(project_root)

    if args.format == "text":
        _print_verify_text(project_root, report)
    elif args.format == "json":
        print(json.dumps(report, indent=2, ensure_ascii=False))

    if args.output:
        args.output.write_text(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"Verification report written to {args.output}")

    # 存在未验证包时返回非零 (严格模式)。
    # 元数据不可达 (网络抖动) 不直接阻断, 但若一个包都没能校验成功, 说明
    # 校验本身失效 (而不是依赖有问题), 同样阻断 —— 避免"查不到即放行"。
    if report["unverified"]:
        return 1
    if report["unverifiable"] and not report["verified"]:
        return 1
    return 0


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
    """Handle verify-signature command (V2.21 P5-64 拆分: 抽 _print_verify_result)."""
    from tools.scripts.supply_chain import SignatureVerifier

    verifier = SignatureVerifier()

    if args.cosign:
        result = verifier.verify_cosign_signature(args.cosign, args.cosign_key)
        _print_verify_result("Cosign verification", args, result, image_or_package=args.cosign)
        return 0 if result["verified"] else 1

    if args.slsa:
        result = verifier.verify_slsa_provenance(args.slsa)
        _print_verify_result("SLSA provenance verification", args, result, image_or_package=args.slsa)
        return 0 if result["verified"] else 1

    print("Specify --cosign or --slsa")
    return 1


def _print_verify_result(
    label: str,
    args: argparse.Namespace,
    result: dict[str, Any],
    image_or_package: str,
) -> None:
    """打印签名验证结果 (text/json 两种格式, 模块级 helper).

    Args:
        label: 标签 ("Cosign verification" 或 "SLSA provenance verification")
        args: argparse Namespace (含 format)
        result: 验证结果字典 (含 verified/output/error/message)
        image_or_package: 镜像名 (cosign) 或包名 (slsa)
    """
    if args.format == "text":
        status = "✅ Verified" if result["verified"] else "❌ Failed"
        print(f"{label}: {status}")
        print(f"Package: {image_or_package}")
        if result.get("output"):
            print(f"Output: {result['output']}")
        if result.get("error"):
            print(f"Error: {result['error']}")
        if "message" in result:
            print(f"Message: {result['message']}")
    elif args.format == "json":
        import json

        print(json.dumps(result, indent=2))


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

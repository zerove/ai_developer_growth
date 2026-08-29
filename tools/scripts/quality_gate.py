"""
质量门禁策略引擎

核心功能:
- 基于配置的门禁规则评估
- 基线对比 (新增/消失/恶化)
- 例外管理 (申请/审批/过期)
- 多门禁模式 (PR/Release/Deploy)
- SARIF/JSON 输出
"""

from __future__ import annotations

import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from tools.scripts.config import (
    BaselineConfig,
    ExceptionRule,
    GovernanceConfig,
    QualityGateConfig,
    SeverityLevel,
    get_config,
)
from tools.scripts.rules_engine.models import CheckResult, Issue, Severity

logger = logging.getLogger(__name__)


@dataclass
class GateResult:
    """单个门禁检查结果"""

    gate_name: str
    passed: bool
    rule_id: str
    message: str
    details: dict[str, Any] = field(default_factory=dict)
    severity: SeverityLevel = SeverityLevel.ERROR


@dataclass
class QualityGateReport:
    """质量门禁报告"""

    gate_name: str
    overall_passed: bool
    results: list[GateResult] = field(default_factory=list)
    baseline_comparison: dict[str, Any] | None = None
    exceptions_applied: list[ExceptionRule] = field(default_factory=list)
    scan_duration_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "gate_name": self.gate_name,
            "overall_passed": self.overall_passed,
            "timestamp": self.timestamp,
            "scan_duration_ms": self.scan_duration_ms,
            "results": [
                {
                    "gate_name": r.gate_name,
                    "passed": r.passed,
                    "rule_id": r.rule_id,
                    "message": r.message,
                    "severity": r.severity.value,
                    "details": r.details,
                }
                for r in self.results
            ],
            "baseline_comparison": self.baseline_comparison,
            "exceptions_applied": [
                {
                    "id": e.id,
                    "rule": e.rule,
                    "paths": e.paths,
                    "reason": e.reason,
                }
                for e in self.exceptions_applied
            ],
        }

    def to_sarif(self) -> dict[str, Any]:
        return {
            "version": "2.1.0",
            "$schema": "https://json.schemastore.org/sarif-2.1.0.json",
            "runs": [
                {
                    "tool": {
                        "driver": {
                            "name": "jcode-quality-gate",
                            "version": "1.0.0",
                        }
                    },
                    "results": [
                        {
                            "ruleId": r.rule_id,
                            "level": "error" if r.severity == SeverityLevel.ERROR else "warning",
                            "message": {"text": r.message},
                            "properties": r.details,
                        }
                        for r in self.results
                        if not r.passed
                    ],
                }
            ],
        }


class BaselineManager:
    """基线管理器"""

    def __init__(self, config: BaselineConfig | None = None):
        self.config = config or get_config().baseline
        self.baseline_path = Path(self.config.path)

    def load_baseline(self) -> dict[str, Any]:
        """加载基线文件"""
        if not self.baseline_path.exists():
            return {}
        try:
            with open(self.baseline_path) as f:
                data: dict[str, Any] = json.load(f)
                return data
        except Exception as e:
            logger.warning(f"Failed to load baseline: {e}")
            return {}

    def save_baseline(self, data: dict[str, Any]) -> None:
        """保存基线文件"""
        self.baseline_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.baseline_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def update_baseline(self, results: list[CheckResult]) -> dict[str, Any]:
        """从检查结果更新基线"""
        baseline: dict[str, Any] = {
            "version": 1,
            "updated_at": datetime.utcnow().isoformat(),
            "files": {},
        }

        for result in results:
            if result.file not in baseline["files"]:
                baseline["files"][result.file] = {}

            for issue in result.issues:
                rule_key = f"{issue.rule_id}:{issue.line}:{issue.column}"
                baseline["files"][result.file][rule_key] = {
                    "rule_id": issue.rule_id,
                    "line": issue.line,
                    "column": issue.column,
                    "severity": issue.severity,
                    "message": issue.message,
                }

        self.save_baseline(baseline)
        return baseline

    def _init_comparison(self) -> dict[str, Any]:
        """初始化 comparison dict 与 summary.

        V2.18 P3-4 拆分: 从 compare_with_baseline (C=14) 抽出.
        """
        return {
            "new": [],
            "fixed": [],
            "worsened": [],
            "improved": [],
            "unchanged": [],
            "summary": {
                "total_current": 0,
                "total_baseline": 0,
                "new_count": 0,
                "fixed_count": 0,
                "worsened_count": 0,
                "improved_count": 0,
            },
        }

    def _build_current_index(
        self,
        current_results: list[CheckResult],
        comparison: dict[str, Any],
    ) -> dict[str, dict[str, dict[str, Any]]]:
        """构建当前结果的文件 → rule_key → issue 索引.

        V2.18 P3-4 拆分: 从 compare_with_baseline (C=14) 抽出.
        返回索引, 同步累加 total_current 计数.
        """
        current_files: dict[str, dict[str, dict[str, Any]]] = {}
        for result in current_results:
            if result.file not in current_files:
                current_files[result.file] = {}
            for issue in result.issues:
                rule_key = f"{issue.rule_id}:{issue.line}:{issue.column}"
                current_files[result.file][rule_key] = {
                    "rule_id": issue.rule_id,
                    "line": issue.line,
                    "column": issue.column,
                    "severity": issue.severity,  # Already a string
                    "message": issue.message,
                }
                comparison["summary"]["total_current"] += 1
        return current_files

    def _classify_severity_change(
        self,
        comparison: dict[str, Any],
        file_path: str,
        current_issue: dict[str, Any],
        baseline_issue: dict[str, Any],
    ) -> None:
        """分类严重性变化: worsened / improved / unchanged.

        V2.18 P3-4 拆分: 从 compare_with_baseline (C=14) 抽出.
        写入 comparison 列表并累加对应 count.
        """
        severity_order = {"info": 0, "warning": 1, "error": 2}
        current_sev = current_issue["severity"]
        baseline_sev = baseline_issue["severity"]
        current_rank = severity_order.get(current_sev, 0)
        baseline_rank = severity_order.get(baseline_sev, 0)

        entry = {
            "file": file_path,
            "rule_id": current_issue["rule_id"],
            "line": current_issue["line"],
        }

        if current_rank > baseline_rank:
            entry_with_sev = {
                **entry,
                "old_severity": baseline_sev,
                "new_severity": current_sev,
            }
            comparison["worsened"].append(entry_with_sev)
            comparison["summary"]["worsened_count"] += 1
        elif current_rank < baseline_rank:
            entry_with_sev = {
                **entry,
                "old_severity": baseline_sev,
                "new_severity": current_sev,
            }
            comparison["improved"].append(entry_with_sev)
            comparison["summary"]["improved_count"] += 1
        else:
            comparison["unchanged"].append({**entry, "severity": current_sev})

    def _find_fixed_issues(
        self,
        baseline_files: dict[str, dict[str, dict[str, Any]]],
        current_files: dict[str, dict[str, dict[str, Any]]],
        comparison: dict[str, Any],
    ) -> None:
        """查找已修复的违规: 在基线中但不在当前结果.

        V2.18 P3-4 拆分: 从 compare_with_baseline (C=14) 抽出.
        """
        for file_path, file_issues in baseline_files.items():
            current_file_issues = current_files.get(file_path, {})
            for rule_key, baseline_issue in file_issues.items():
                if rule_key not in current_file_issues:
                    comparison["fixed"].append(
                        {
                            "file": file_path,
                            "rule_id": baseline_issue["rule_id"],
                            "line": baseline_issue["line"],
                            "severity": baseline_issue["severity"],
                        }
                    )
                    comparison["summary"]["fixed_count"] += 1

    def compare_with_baseline(
        self,
        current_results: list[CheckResult],
        baseline: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """对比当前结果与基线 (orchestrator).

        返回:
        - new: 新增的违规
        - fixed: 已修复的违规
        - worsened: 严重性升级的违规
        - improved: 严重性降级的违规
        - unchanged: 未变化的违规

        V2.18 P3-4 拆分: 从 C=14 / 130+ 行主函数拆出 4 个 helper.
        主函数仅负责: 加载基线 → 初始化 → 构建索引 → 逐 file 对比 → 找 fixed.
        """
        baseline = baseline or self.load_baseline()
        baseline_files: dict[str, dict[str, dict[str, Any]]] = baseline.get("files", {})

        comparison = self._init_comparison()
        current_files = self._build_current_index(current_results, comparison)

        comparison["summary"]["total_baseline"] = sum(len(issues) for issues in baseline_files.values())

        for file_path, file_issues in current_files.items():
            baseline_file_issues = baseline_files.get(file_path, {})
            for rule_key, current_issue in file_issues.items():
                if rule_key in baseline_file_issues:
                    self._classify_severity_change(
                        comparison,
                        file_path,
                        current_issue,
                        baseline_file_issues[rule_key],
                    )
                else:
                    comparison["new"].append(
                        {
                            "file": file_path,
                            "rule_id": current_issue["rule_id"],
                            "line": current_issue["line"],
                            "severity": current_issue["severity"],
                            "message": current_issue["message"],
                        }
                    )
                    comparison["summary"]["new_count"] += 1

        self._find_fixed_issues(baseline_files, current_files, comparison)

        return comparison


class ExceptionManager:
    """例外管理器"""

    def __init__(self, config: GovernanceConfig | None = None):
        self.config = config or get_config()
        self.exceptions: list[ExceptionRule] = list(self.config.exceptions)

    def add_exception(
        self,
        rule_id: str,
        paths: list[str],
        reason: str,
        expires: str | None = None,
        severity: SeverityLevel = SeverityLevel.WARNING,
        created_by: str = "",
    ) -> ExceptionRule:
        """添加例外规则"""
        import uuid

        exc = ExceptionRule(
            id=str(uuid.uuid4())[:8],
            rule=rule_id,
            paths=paths,
            reason=reason,
            expires=expires,
            severity=severity,
            created_by=created_by,
            created_at=datetime.utcnow().isoformat(),
        )
        self.exceptions.append(exc)
        return exc

    def remove_exception(self, exception_id: str) -> bool:
        """移除例外规则"""
        for i, exc in enumerate(self.exceptions):
            if exc.id == exception_id:
                self.exceptions.pop(i)
                return True
        return False

    def get_active_exceptions(self, rule_id: str | None = None) -> list[ExceptionRule]:
        """获取当前有效的例外"""
        now = datetime.utcnow()
        active = []
        for exc in self.exceptions:
            if rule_id and exc.rule != rule_id:
                continue
            if exc.expires:
                try:
                    exp_date = datetime.fromisoformat(exc.expires)
                    if exp_date < now:
                        continue  # 已过期
                except ValueError:
                    pass
            active.append(exc)
        return active

    def is_excepted(self, file_path: str, rule_id: str, line: int | None = None) -> ExceptionRule | None:
        """检查文件/规则是否有例外"""
        for exc in self.get_active_exceptions(rule_id):
            # 简单的 glob 匹配
            import fnmatch

            for pattern in exc.paths:
                if fnmatch.fnmatch(file_path, pattern):
                    return exc
        return None

    def apply_exceptions(self, results: list[CheckResult]) -> list[CheckResult]:
        """应用例外规则到检查结果"""
        filtered_results = []
        for result in results:
            filtered_issues = []
            for issue in result.issues:
                exc = self.is_excepted(result.file, issue.rule_id, issue.line)
                if exc:
                    # 降级严重性
                    if exc.severity == SeverityLevel.INFO:
                        continue  # 完全忽略
                    # 创建降级后的 issue
                    filtered_issues.append(
                        Issue(
                            rule_id=issue.rule_id,
                            severity=exc.severity.value,
                            category=issue.category,
                            file=issue.file,
                            line=issue.line,
                            column=issue.column,
                            message=f"[EXCEPTED] {issue.message}",
                        )
                    )
                else:
                    filtered_issues.append(issue)

            filtered_results.append(
                CheckResult(
                    file=result.file,
                    issues=filtered_issues,
                    language=result.language,
                    skipped=result.skipped,
                )
            )

        return filtered_results


class QualityGateEngine:
    """质量门禁引擎"""

    def __init__(self, config: GovernanceConfig | None = None):
        self.config = config or get_config()
        self.baseline_manager = BaselineManager(self.config.baseline)
        self.exception_manager = ExceptionManager(self.config)

    def _gate_zero_new_errors(
        self,
        gate_name: str,
        gate_config: QualityGateConfig,
        baseline_comparison: dict[str, Any] | None,
    ) -> GateResult | None:
        """Gate 1: 零新增错误. 关闭时返回 None."""
        if not gate_config.require_zero_new_errors:
            return None
        new_errors = (
            [i for i in baseline_comparison.get("new", []) if i.get("severity") == "error"]
            if baseline_comparison
            else []
        )
        return GateResult(
            gate_name=gate_name,
            passed=len(new_errors) == 0,
            rule_id="gate.zero-new-errors",
            message=f"新增错误: {len(new_errors)} 个" if new_errors else "无新增错误",
            details={"new_errors": new_errors},
            severity=SeverityLevel.ERROR,
        )

    def _gate_zero_new_warnings(
        self,
        gate_name: str,
        gate_config: QualityGateConfig,
        baseline_comparison: dict[str, Any] | None,
    ) -> GateResult | None:
        """Gate 2: 零新增警告. 关闭时返回 None."""
        if not gate_config.require_zero_new_warnings:
            return None
        new_warnings = (
            [i for i in baseline_comparison.get("new", []) if i.get("severity") == "warning"]
            if baseline_comparison
            else []
        )
        return GateResult(
            gate_name=gate_name,
            passed=len(new_warnings) == 0,
            rule_id="gate.zero-new-warnings",
            message=f"新增警告: {len(new_warnings)} 个" if new_warnings else "无新增警告",
            details={"new_warnings": new_warnings},
            severity=SeverityLevel.WARNING,
        )

    def _gate_max_new_errors(
        self,
        gate_name: str,
        gate_config: QualityGateConfig,
        baseline_comparison: dict[str, Any] | None,
    ) -> GateResult | None:
        """Gate 3: 最大新增错误数. 关闭时返回 None."""
        if gate_config.max_new_errors <= 0:
            return None
        new_errors = (
            [i for i in baseline_comparison.get("new", []) if i.get("severity") == "error"]
            if baseline_comparison
            else []
        )
        return GateResult(
            gate_name=gate_name,
            passed=len(new_errors) <= gate_config.max_new_errors,
            rule_id="gate.max-new-errors",
            message=f"新增错误数 {len(new_errors)} <= {gate_config.max_new_errors}",
            details={"count": len(new_errors), "limit": gate_config.max_new_errors},
            severity=SeverityLevel.ERROR,
        )

    def _gate_max_new_warnings(
        self,
        gate_name: str,
        gate_config: QualityGateConfig,
        baseline_comparison: dict[str, Any] | None,
    ) -> GateResult | None:
        """Gate 4: 最大新增警告数. 关闭时返回 None."""
        if gate_config.max_new_warnings <= 0:
            return None
        new_warnings = (
            [i for i in baseline_comparison.get("new", []) if i.get("severity") == "warning"]
            if baseline_comparison
            else []
        )
        return GateResult(
            gate_name=gate_name,
            passed=len(new_warnings) <= gate_config.max_new_warnings,
            rule_id="gate.max-new-warnings",
            message=f"新增警告数 {len(new_warnings)} <= {gate_config.max_new_warnings}",
            details={"count": len(new_warnings), "limit": gate_config.max_new_warnings},
            severity=SeverityLevel.WARNING,
        )

    def _gate_min_coverage(
        self,
        gate_name: str,
        gate_config: QualityGateConfig,
    ) -> GateResult | None:
        """Gate 5: 最小覆盖率. 当前未实现, 始终返回 placeholder."""
        if gate_config.min_coverage_overall <= 0:
            return None
        # 覆盖率工具集成待实现, 暂时跳过
        return GateResult(
            gate_name=gate_name,
            passed=True,
            rule_id="gate.coverage-overall",
            message="覆盖率检查待实现",
            details={},
            severity=SeverityLevel.WARNING,
        )

    def _gate_no_worsened(
        self,
        gate_name: str,
        baseline_comparison: dict[str, Any] | None,
    ) -> GateResult | None:
        """Gate 6: 基线恶化检查. 关闭时返回 None."""
        if not self.config.baseline.fail_on_worsened or not baseline_comparison:
            return None
        worsened = baseline_comparison.get("worsened", [])
        return GateResult(
            gate_name=gate_name,
            passed=len(worsened) == 0,
            rule_id="gate.no-worsened",
            message=f"严重性恶化: {len(worsened)} 个" if worsened else "无恶化",
            details={"worsened": worsened},
            severity=SeverityLevel.ERROR,
        )

    def _gate_current_issues(
        self,
        gate_name: str,
        filtered_results: list[CheckResult],
    ) -> GateResult:
        """Gate 7: 当前总违规数检查 (始终运行)."""
        total_issues = sum(len(r.issues) for r in filtered_results)
        error_count = sum(1 for r in filtered_results for i in r.issues if i.severity == Severity.ERROR)
        warning_count = sum(1 for r in filtered_results for i in r.issues if i.severity == Severity.WARNING)
        return GateResult(
            gate_name=gate_name,
            passed=error_count == 0,
            rule_id="gate.current-errors",
            message=f"当前错误: {error_count} 个, 警告: {warning_count} 个",
            details={"errors": error_count, "warnings": warning_count, "total": total_issues},
            severity=SeverityLevel.ERROR,
        )

    def evaluate(
        self,
        results: list[CheckResult],
        gate_name: str = "default",
        baseline: dict[str, Any] | None = None,
    ) -> QualityGateReport:
        """评估质量门禁 (orchestrator).

        V2.17 P2-2 拆分: 从 C=32 / 152 行主函数拆出 7 个 _gate_* helper.
        主函数仅负责 orchestration: 应用例外 → 基线对比 → 7 规则评估 → 汇总.
        """
        start = time.time()

        gate_config = self.config.quality_gates.get(gate_name, QualityGateConfig(name=gate_name))

        # 应用例外
        filtered_results = self.exception_manager.apply_exceptions(results)
        active_exceptions = self.exception_manager.get_active_exceptions()

        # 基线对比
        baseline_comparison = None
        if self.config.baseline.enabled:
            baseline_comparison = self.baseline_manager.compare_with_baseline(filtered_results, baseline)

        # 评估 7 项规则
        gate_results: list[GateResult] = []
        gate_evaluators: list[Callable[[], GateResult | None]] = [
            lambda: self._gate_zero_new_errors(gate_name, gate_config, baseline_comparison),
            lambda: self._gate_zero_new_warnings(gate_name, gate_config, baseline_comparison),
            lambda: self._gate_max_new_errors(gate_name, gate_config, baseline_comparison),
            lambda: self._gate_max_new_warnings(gate_name, gate_config, baseline_comparison),
            lambda: self._gate_min_coverage(gate_name, gate_config),
            lambda: self._gate_no_worsened(gate_name, baseline_comparison),
            lambda: self._gate_current_issues(gate_name, filtered_results),
        ]
        for gate_fn in gate_evaluators:
            result = gate_fn()
            if result is not None:
                gate_results.append(result)

        # 汇总
        all_passed = all(r.passed for r in gate_results)

        report = QualityGateReport(
            gate_name=gate_name,
            overall_passed=all_passed,
            results=gate_results,
            baseline_comparison=baseline_comparison,
            exceptions_applied=active_exceptions,
            scan_duration_ms=int((time.time() - start) * 1000),
        )

        return report

    def update_baseline_on_success(self, results: list[CheckResult]) -> None:
        """成功时更新基线"""
        if self.config.baseline.auto_update and self.config.baseline.update_on_success:
            self.baseline_manager.update_baseline(results)


def run_quality_gate(
    check_results: list[CheckResult],
    gate_name: str = "default",
    baseline: dict[str, Any] | None = None,
    output_format: str = "text",
    output_file: Path | None = None,
) -> QualityGateReport:
    """便捷函数: 运行质量门禁"""
    engine = QualityGateEngine()
    report = engine.evaluate(check_results, gate_name, baseline)

    # 输出
    if output_format == "json" and output_file:
        output_file.write_text(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
    elif output_format == "sarif" and output_file:
        output_file.write_text(json.dumps(report.to_sarif(), indent=2))

    return report

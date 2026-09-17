"""Code quality trend tracking module.

Tracks code quality metrics over time, detects regressions,
and generates trend reports for dashboards.

Usage:
    from tools.scripts.rules_engine.quality_trends import QualityTracker

    tracker = QualityTracker()
    snapshot = tracker.take_snapshot(Path("."))
    report = tracker.generate_trend_report()
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import CheckResult
from .store import CheckStore


@dataclass
class QualitySnapshot:
    """A point-in-time quality measurement."""

    timestamp: float
    total_files: int
    total_issues: int
    errors: int
    warnings: int
    info: int
    categories: dict[str, int] = field(default_factory=dict)
    rule_counts: dict[str, int] = field(default_factory=dict)
    languages: dict[str, int] = field(default_factory=dict)
    semantic_issues: int = 0
    hallucination_findings: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "total_files": self.total_files,
            "total_issues": self.total_issues,
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "categories": self.categories,
            "rule_counts": self.rule_counts,
            "languages": self.languages,
            "semantic_issues": self.semantic_issues,
            "hallucination_findings": self.hallucination_findings,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> QualitySnapshot:
        return cls(
            timestamp=data["timestamp"],
            total_files=data["total_files"],
            total_issues=data["total_issues"],
            errors=data.get("errors", 0),
            warnings=data.get("warnings", 0),
            info=data.get("info", 0),
            categories=data.get("categories", {}),
            rule_counts=data.get("rule_counts", {}),
            languages=data.get("languages", {}),
            semantic_issues=data.get("semantic_issues", 0),
            hallucination_findings=data.get("hallucination_findings", 0),
        )


@dataclass
class TrendDelta:
    """Change between two snapshots."""

    metric: str
    previous: int | float
    current: int | float
    change: int | float
    change_pct: float
    direction: str  # "improved", "regressed", "unchanged"


@dataclass
class TrendReport:
    """Report of quality trends over time."""

    snapshot_count: int
    latest: QualitySnapshot | None
    deltas: list[TrendDelta] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def has_regressions(self) -> bool:
        """Check if any metrics regressed."""
        return any(d.direction == "regressed" for d in self.deltas)


def _aggregate_results(results: list[CheckResult]) -> dict[str, Any]:
    """Aggregate check results into metrics."""
    categories: dict[str, int] = {}
    rule_counts: dict[str, int] = {}
    languages: dict[str, int] = {}
    errors = warnings = info_count = 0
    semantic_issues = 0

    for result in results:
        lang = result.language or "unknown"
        languages[lang] = languages.get(lang, 0) + 1

        for issue in result.issues:
            categories[issue.category] = categories.get(issue.category, 0) + 1
            rule_counts[issue.rule_id] = rule_counts.get(issue.rule_id, 0) + 1

            if issue.severity == "error":
                errors += 1
            elif issue.severity == "warning":
                warnings += 1
            else:
                info_count += 1

            if issue.rule_id.startswith("semantic-"):
                semantic_issues += 1

    return {
        "categories": categories,
        "rule_counts": rule_counts,
        "languages": languages,
        "errors": errors,
        "warnings": warnings,
        "info_count": info_count,
        "semantic_issues": semantic_issues,
    }


def _detect_hallucinations(dirpath: Path) -> int:
    """Detect hallucinations and return count."""
    try:
        from tools.scripts.rules_engine.hallucination_detector import (
            detect_hallucinations,
        )

        h_report = detect_hallucinations(dirpath)
        return h_report.total_findings
    except ImportError:
        return 0


def _calculate_delta(prev_val: int, curr_val: int, lower_is_better: bool | None) -> tuple[int, float, str]:
    """Calculate delta between two values."""
    change = curr_val - prev_val
    pct = (change / prev_val * 100) if prev_val > 0 else (100 if change > 0 else 0)

    if lower_is_better is None:
        direction = "unchanged"
    elif change < 0:
        direction = "improved"
    elif change > 0:
        direction = "regressed"
    else:
        direction = "unchanged"

    return change, pct, direction


def _get_comparison_metrics() -> list[tuple[str, str, bool | None]]:
    """Get list of metrics to compare."""
    return [
        ("total_issues", "Total Issues", False),
        ("errors", "Errors", False),
        ("warnings", "Warnings", False),
        ("semantic_issues", "Semantic Issues", False),
        ("hallucination_findings", "Hallucination Findings", False),
        ("total_files", "Files Scanned", None),
    ]


def _build_deltas(prev: QualitySnapshot, curr: QualitySnapshot) -> list[TrendDelta]:
    """Build TrendDelta list from two snapshots."""
    deltas: list[TrendDelta] = []
    for attr, label, lower_is_better in _get_comparison_metrics():
        prev_val = getattr(prev, attr, 0)
        curr_val = getattr(curr, attr, 0)
        change, pct, direction = _calculate_delta(prev_val, curr_val, lower_is_better)

        deltas.append(
            TrendDelta(
                metric=label,
                previous=prev_val,
                current=curr_val,
                change=change,
                change_pct=pct,
                direction=direction,
            )
        )
    return deltas


def _metric_regression_message(delta: TrendDelta) -> str | None:
    """回归指标对应的建议文案 (Phase 36c cc 拆分: 从 _generate_recommendations 抽出)."""
    if delta.metric == "Errors" and delta.change > 0:
        return f"Errors increased by {delta.change}. Investigate new error patterns."
    if delta.metric == "Semantic Issues" and delta.change > 0:
        return f"Semantic issues increased by {delta.change}. Check for new code without proper structure."
    if delta.metric == "Hallucination Findings" and delta.change > 0:
        return f"Hallucination patterns increased by {delta.change}. Review recent AI-generated code."
    return None


def _generate_recommendations(deltas: list[TrendDelta]) -> list[str]:
    """Generate recommendations from deltas."""
    recommendations: list[str] = []
    for delta in deltas:
        if delta.direction == "regressed":
            message = _metric_regression_message(delta)
            if message:
                recommendations.append(message)

    if not recommendations:
        recommendations.append("Quality metrics are stable or improving. Keep it up!")

    return recommendations


class QualityTracker:
    """Track code quality metrics over time.

    Stores snapshots in a JSON file for persistence across runs.
    """

    def __init__(self, data_dir: Path | None = None) -> None:
        self.data_dir = data_dir or Path.home() / ".cache" / "adg" / "quality"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # 统一 SQLite 存储（任务7：替代 JSON 快照文件）
        self._db_path = self.data_dir / "quality.db"
        self._store: CheckStore | None = CheckStore(self._db_path)
        self._snapshots: list[QualitySnapshot] = []
        self._load()

    def __enter__(self) -> QualityTracker:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    @property
    def store(self) -> CheckStore:
        """惰性访问底层存储；close 后再访问会重建连接。

        背景: 此前 _store 无 close 途径，连接滞留进程级池导致全量测试时
        大量 ResourceWarning: unclosed database。
        """
        if self._store is None:
            self._store = CheckStore(self._db_path)
        return self._store

    def close(self) -> None:
        """关闭并从进程级连接池移除本库连接。幂等，可重复调用。"""
        if self._store is not None:
            self._store.close()
            self._store = None
        from tools.scripts.rules_engine import store as _store_mod

        _store_mod.close_connection(str(self._db_path))

    def _load(self) -> None:
        """从 SQLite 加载快照。"""
        try:
            self._snapshots = [QualitySnapshot.from_dict(s) for s in self.store.get_snapshots()]
        except Exception:
            self._snapshots = []

    def _save(self) -> None:
        """持久化快照列表到 SQLite（幂等：先清空再写入）。"""
        self.store.clear_snapshots()
        for s in self._snapshots:
            self.store.add_snapshot(s.to_dict())

    @property
    def snapshots(self) -> list[QualitySnapshot]:
        """All stored snapshots."""
        return list(self._snapshots)

    def take_snapshot(
        self,
        dirpath: Path,
        semantic: bool = False,
        hallucination: bool = False,
    ) -> QualitySnapshot:
        """Take a quality snapshot of a directory.

        Args:
            dirpath: Directory to measure.
            semantic: Include AST semantic analysis.
            hallucination: Include hallucination detection.

        Returns:
            The captured snapshot.
        """
        from tools.scripts.rules_engine.checker import check_directory

        results = check_directory(dirpath, semantic=semantic)
        metrics = _aggregate_results(results)

        hallucination_findings = 0
        if hallucination:
            hallucination_findings = _detect_hallucinations(dirpath)

        snapshot = QualitySnapshot(
            timestamp=time.time(),
            total_files=len(results),
            total_issues=metrics["errors"] + metrics["warnings"] + metrics["info_count"],
            errors=metrics["errors"],
            warnings=metrics["warnings"],
            info=metrics["info_count"],
            categories=metrics["categories"],
            rule_counts=metrics["rule_counts"],
            languages=metrics["languages"],
            semantic_issues=metrics["semantic_issues"],
            hallucination_findings=hallucination_findings,
        )

        self._snapshots.append(snapshot)
        self._save()
        return snapshot

    def generate_trend_report(self, lookback: int = 10) -> TrendReport:
        """Generate a trend report from stored snapshots.

        Args:
            lookback: Number of recent snapshots to compare.

        Returns:
            TrendReport with deltas and recommendations.
        """
        snapshots = self._snapshots[-lookback:]
        report = TrendReport(
            snapshot_count=len(self._snapshots),
            latest=snapshots[-1] if snapshots else None,
        )

        if len(snapshots) < 2:
            report.recommendations.append("Need at least 2 snapshots for trend analysis.")
            return report

        prev = snapshots[-2]
        curr = snapshots[-1]

        report.deltas = _build_deltas(prev, curr)
        report.recommendations = _generate_recommendations(report.deltas)

        return report

    def format_trend_report(self, report: TrendReport | None = None) -> str:
        """Format a trend report as human-readable text."""
        if report is None:
            report = self.generate_trend_report()

        lines = [
            "Code Quality Trend Report",
            "=" * 60,
            f"Total snapshots: {report.snapshot_count}",
        ]

        if report.latest:
            lines.append(f"Latest scan: {time.strftime('%Y-%m-%d %H:%M', time.localtime(report.latest.timestamp))}")
            lines.append(f"Files: {report.latest.total_files}, Issues: {report.latest.total_issues}")

        if report.deltas:
            lines.append("\nTrend Changes:")
            lines.append("-" * 40)
            for delta in report.deltas:
                icon = {"improved": "✅", "regressed": "⚠️", "unchanged": "➡️"}[delta.direction]
                lines.append(
                    f"  {icon} {delta.metric}: {delta.previous} → {delta.current} "
                    f"({delta.change:+d}, {delta.change_pct:+.1f}%)"
                )

        if report.recommendations:
            lines.append("\nRecommendations:")
            lines.append("-" * 40)
            for rec in report.recommendations:
                lines.append(f"  • {rec}")

        return "\n".join(lines)

    def clear(self) -> None:
        """Clear all stored snapshots."""
        self._snapshots.clear()
        self._save()

    # ── Dashboard enhancements ──────────────────────────────────────────

    def generate_sparkline(self, attr: str = "total_issues", width: int = 20) -> str:
        """Generate an ASCII sparkline for a metric over all snapshots."""
        values = [getattr(s, attr, 0) for s in self._snapshots]
        if not values:
            return "(no data)"

        mn, mx = min(values), max(values)
        if mx == mn:
            return "▁" * min(len(values), width)

        # Scale to 8 braille levels
        chars = ["▁", "▂", "▃", "▄", "▅", "▆", "▇", "█"]
        step = (mx - mn) / max(len(chars) - 1, 1)

        # Downsample if needed
        if len(values) > width:
            indices = [int(i * len(values) / width) for i in range(width)]
            values = [values[i] for i in indices]

        return "".join(chars[min(int((v - mn) / step), len(chars) - 1)] for v in values)

    def generate_summary(self, report: TrendReport | None = None) -> str:
        """Generate a one-line summary suitable for a dashboard header."""
        if report is None:
            report = self.generate_trend_report()

        if report.latest is None:
            return "📊 Quality: no data yet"

        spark = self.generate_sparkline("total_issues")
        last = report.latest
        regressions = sum(1 for d in report.deltas if d.direction == "regressed")
        icon = "✅" if regressions == 0 else "⚠️" if regressions <= 2 else "🔴"

        return (
            f"{icon} Quality: {last.total_issues} issues / {last.total_files} files [{spark}] {regressions} regressed"
        )

    def generate_multi_trend_report(self, lookback: int = 10) -> str:
        """Generate a multi-point trend report comparing all recent snapshots."""
        snapshots = self._snapshots[-lookback:]
        if len(snapshots) < 2:
            return "Need at least 2 snapshots for multi-trend analysis."

        lines = [
            f"📈 Quality Trend (last {len(snapshots)}/{len(self._snapshots)} snapshots)",
            "",
            "  Issues   Errors   Warnings   Files   Date",
            "  " + "-" * 50,
        ]

        for s in snapshots:
            date = time.strftime("%m-%d %H:%M", time.localtime(s.timestamp))
            lines.append(f"  {s.total_issues:>6d}  {s.errors:>6d}  {s.warnings:>8d}  {s.total_files:>5d}   {date}")

        lines.append("")
        lines.append(f"  Sparkline (issues): {self.generate_sparkline('total_issues')}")
        lines.append(f"  Sparkline (errors):  {self.generate_sparkline('errors')}")
        return "\n".join(lines)

"""quality_trends 第二轮: QualityTracker 全生命周期 + dashboard 增强。60%→85%+

SQLite 持久化/take_snapshot/趋势报告/sparkline/multi-trend/clear。
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tools.scripts.rules_engine.quality_trends import (
    QualitySnapshot,
    QualityTracker,
    TrendDelta,
    TrendReport,
)


def snap(
    total_issues: int = 5,
    errors: int = 2,
    warnings: int = 3,
    total_files: int = 10,
    timestamp: float = 1000.0,
) -> QualitySnapshot:
    return QualitySnapshot(
        timestamp=timestamp,
        total_files=total_files,
        total_issues=total_issues,
        errors=errors,
        warnings=warnings,
        info=0,
    )


class TestTrackerLifecycle:
    def test_snapshot_persisted_across_instances(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t1:
            t1._snapshots.append(snap(timestamp=123.0))
            t1._save()
        with QualityTracker(data_dir=tmp_path) as t2:
            assert len(t2.snapshots) == 1
            assert t2.snapshots[0].timestamp == 123.0

    def test_clear_removes_all(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots.append(snap())
            t._save()
            t.clear()
            assert t.snapshots == []

    def test_store_lazy_reconnect_after_close(self, tmp_path: Path) -> None:
        t = QualityTracker(data_dir=tmp_path)
        t.close()
        # close 后再访问 store 自动重建
        assert t.store is not None
        t.close()  # 幂等

    def test_take_snapshot_with_fake_checker(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        from tools.scripts.rules_engine.models import CheckResult, Issue

        result = CheckResult(
            file="a.py",
            issues=[
                Issue(rule_id="r1", severity="error", category="c", file="a.py", line=1, message="m"),
                Issue(rule_id="r2", severity="warning", category="c", file="a.py", line=2, message="m"),
            ],
        )
        import tools.scripts.rules_engine.checker as checker_mod

        monkeypatch.setattr(checker_mod, "check_directory", lambda d, semantic=False: [result])
        with QualityTracker(data_dir=tmp_path) as t:
            s = t.take_snapshot(tmp_path)
            assert s.total_files == 1 and s.errors == 1 and s.warnings == 1
            assert len(t.snapshots) == 1


class TestTrendReport:
    def test_needs_two_snapshots(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap()]
            report = t.generate_trend_report()
            assert "Need at least 2" in report.recommendations[0]

    def test_deltas_and_recommendations(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=4, errors=1), snap(total_issues=8, errors=3, timestamp=2000.0)]
            report = t.generate_trend_report()
            assert report.deltas
            assert any(d.direction == "regressed" for d in report.deltas)

    def test_format_report_full(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=4), snap(total_issues=6, timestamp=2000.0)]
            text = t.format_trend_report()
            assert "Code Quality Trend Report" in text and "Trend Changes" in text
            delta = TrendDelta(
                metric="total_issues", previous=4, current=6, change=2, change_pct=50.0, direction="regressed"
            )
            text2 = t.format_trend_report(
                TrendReport(snapshot_count=2, latest=snap(), deltas=[delta], recommendations=["fix it"])
            )
            assert "⚠️" in text2 and "fix it" in text2

    def test_format_empty_report(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = []
            text = t.format_trend_report()
            assert "Total snapshots: 0" in text


class TestDashboardEnhancements:
    def test_sparkline_no_data(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            assert t.generate_sparkline() == "(no data)"

    def test_sparkline_flat_values(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=5) for _ in range(3)]
            line = t.generate_sparkline()
            assert set(line) == {"▁"}

    def test_sparkline_varied_and_downsampled(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=i) for i in range(50)]
            line = t.generate_sparkline(width=10)
            assert len(line) <= 10 and any(c != "▁" for c in line)

    def test_summary_icons_by_regressions(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=1), snap(total_issues=9)]
            summary = t.generate_summary()
            assert "Quality:" in summary and "issues /" in summary

    def test_summary_no_data(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            assert t.generate_summary() == "📊 Quality: no data yet"

    def test_multi_trend_needs_two(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap()]
            assert "Need at least 2" in t.generate_multi_trend_report()

    def test_multi_trend_table(self, tmp_path: Path) -> None:
        with QualityTracker(data_dir=tmp_path) as t:
            t._snapshots = [snap(total_issues=3, errors=1), snap(total_issues=7, errors=2, timestamp=2000.0)]
            text = t.generate_multi_trend_report()
            assert "Sparkline (issues)" in text and "Sparkline (errors)" in text

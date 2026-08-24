"""quality_trends 纯函数回归测试（覆盖率门禁提升配套）。

覆盖此前 0% 的趋势分析模块核心路径：
结果聚合、增量计算、快照对比、建议生成。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from tools.scripts.rules_engine.quality_trends import (
    _aggregate_results,
    _build_deltas,
    _calculate_delta,
    _generate_recommendations,
)


@dataclass
class _Issue:
    category: str = "style"
    rule_id: str = "py-test-rule"
    severity: str = "warning"


@dataclass
class _Result:
    language: str | None = "python"
    issues: list = field(default_factory=list)


class TestAggregateResults:
    def test_counts_by_severity(self) -> None:
        results = [
            _Result(issues=[_Issue(severity="error"), _Issue(severity="warning")]),
            _Result(language=None, issues=[_Issue(severity="info")]),
        ]
        agg = _aggregate_results(results)
        assert agg["errors"] == 1
        assert agg["warnings"] == 1
        assert agg["info_count"] == 1
        assert agg["languages"] == {"python": 1, "unknown": 1}

    def test_semantic_and_categories(self) -> None:
        results = [
            _Result(
                issues=[
                    _Issue(rule_id="semantic-missing-docstring", category="missing-docstring"),
                    _Issue(),
                ]
            )
        ]
        agg = _aggregate_results(results)
        assert agg["semantic_issues"] == 1
        assert agg["categories"]["missing-docstring"] == 1
        assert agg["rule_counts"]["py-test-rule"] == 1


class TestCalculateDelta:
    def test_lower_is_better_improved(self) -> None:
        change, pct, direction = _calculate_delta(10, 8, True)
        assert change == -2
        assert pct == -20.0
        assert direction == "improved"

    def test_regressed(self) -> None:
        _, _, direction = _calculate_delta(10, 12, False)
        assert direction == "regressed"

    def test_zero_baseline(self) -> None:
        change, pct, direction = _calculate_delta(0, 5, None)
        assert change == 5
        assert pct == 100
        assert direction == "unchanged"


class TestBuildDeltas:
    def test_all_metrics_present(self) -> None:
        @dataclass
        class _Snap:
            total_issues: int = 10
            errors: int = 2
            warnings: int = 5
            semantic_issues: int = 1
            hallucination_findings: int = 0
            total_files: int = 100

        deltas = _build_deltas(_Snap(), _Snap(total_issues=12))
        assert len(deltas) == 6
        by_metric = {d.metric: d for d in deltas}
        assert by_metric["Total Issues"].change == 2
        assert by_metric["Total Issues"].direction == "regressed"
        assert by_metric["Files Scanned"].direction == "unchanged"


class TestGenerateRecommendations:
    def test_error_regression_message(self) -> None:
        from tools.scripts.rules_engine.quality_trends import TrendDelta

        deltas = [
            TrendDelta(
                metric="Errors",
                previous=1,
                current=4,
                change=3,
                change_pct=200.0,
                direction="regressed",
            )
        ]
        recs = _generate_recommendations(deltas)
        assert any("Errors increased" in r for r in recs)

    def test_stable_default_message(self) -> None:
        recs = _generate_recommendations([])
        assert recs == ["Quality metrics are stable or improving. Keep it up!"]

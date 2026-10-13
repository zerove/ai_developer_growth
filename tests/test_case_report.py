"""_case_report 渲染函数单元测试。

三个 formatter 都是纯函数(输入 report 字典 -> 输出字符串列表/字符串),
此前无直接覆盖(实测 60.2%)。重点覆盖: 7 列定宽渲染、空集合不崩、
以及列表只取前 10 项的截断行为。
"""

from __future__ import annotations

import json
import sys
from typing import Any
from unittest.mock import MagicMock

import tools.scripts._case_report as mod
from tools.scripts._case_report import (
    _format_case_list,
    _format_detail_row,
    _format_score_table,
    format_report,
)


def _scores(**kw) -> dict[str, float]:
    base = {
        "overall": 80.0,
        "authenticity": 90.0,
        "efficiency_credibility": 70.0,
        "insight_quality": 85.0,
        "completeness": 60.0,
        "cross_references": 50.0,
    }
    base.update(kw)
    return base


def _detail(**kw) -> dict[str, Any]:
    base = {
        "case": "docs/case-studies/demo.md",
        "overall": 88.5,
        "authenticity": 92.0,
        "efficiency": 81.0,
        "insight": 95.5,
        "completeness": 77.0,
        "cross_refs": 66.0,
    }
    base.update(kw)
    return base


class TestScoreTable:
    def test_renders_all_six_metrics(self) -> None:
        lines = _format_score_table(_scores())
        assert len(lines) == 6

    def test_includes_values(self) -> None:
        text = "\n".join(_format_score_table(_scores(overall=42.0)))
        assert "42.0/100" in text
        assert "Overall Average" in text

    def test_missing_key_raises(self) -> None:
        """缺键应直接抛错 —— 说明 report 结构不符, 静默补 0 反而会掩盖问题。"""
        partial = {"overall": 1.0}
        try:
            _format_score_table(partial)  # type: ignore[arg-type]
        except KeyError:
            return
        raise AssertionError("缺失 score 键时未抛 KeyError")


class TestCaseList:
    def test_header_always_present_even_when_empty(self) -> None:
        assert _format_case_list("🏆 Top 5 Cases:", []) == ["🏆 Top 5 Cases:"]

    def test_rows_follow_header(self) -> None:
        lines = _format_case_list("H:", [{"score": 91.5, "name": "a.md"}, {"score": 70.0, "name": "b.md"}])
        assert lines[0] == "H:"
        assert "91.5" in lines[1] and "a.md" in lines[1]
        assert "70.0" in lines[2] and "b.md" in lines[2]


class TestDetailRow:
    def test_contains_all_fields(self) -> None:
        row = _format_detail_row(_detail())
        for token in ("demo.md", "88.5", "92.0", "81.0", "95.5", "77.0", "66.0"):
            assert token in row

    def test_is_single_line(self) -> None:
        assert "\n" not in _format_detail_row(_detail())

    def test_case_name_left_aligned_padded(self) -> None:
        """case 列为左对齐定宽 40, 短名须补空格。"""
        row = _format_detail_row(_detail(case="x.md"))
        assert row.startswith("x.md" + " ")


def _make_report(**kw) -> dict[str, Any]:
    base: dict[str, Any] = {
        "summary": {
            "total_cases": 3,
            "average_scores": _scores(),
            "categories": {"excellent": 1, "good": 1, "needs_improvement": 1},
        },
        "top_cases": [{"score": 95.0, "name": "top.md"}],
        "bottom_cases": [{"score": 40.0, "name": "bottom.md"}],
        "common_issues": {"缺少效率数据": 5},
        "common_strengths": {"对比充分": 3},
        "detailed": [_detail(), _detail(case="second.md")],
    }
    base.update(kw)
    return base


class TestFormatReport:
    def test_renders_sections(self) -> None:
        out = format_report(_make_report())
        for token in ("Case Study Quality Analysis Report", "📈 Summary", "📊 Categories", "Detailed Scores"):
            assert token in out

    def test_counts_reported(self) -> None:
        assert "(3 cases)" in format_report(_make_report())

    def test_empty_collections_do_not_crash(self) -> None:
        out = format_report(
            _make_report(top_cases=[], bottom_cases=[], common_issues={}, common_strengths={}, detailed=[])
        )
        assert "Top 5 Cases:" in out

    def test_common_issues_truncated_to_ten(self) -> None:
        issues = {f"issue-{i}": i for i in range(25)}
        out = format_report(_make_report(common_issues=issues))
        assert "issue-9" in out
        assert "issue-10" not in out

    def test_common_strengths_truncated_to_ten(self) -> None:
        strengths = {f"s-{i}": i for i in range(20)}
        out = format_report(_make_report(common_strengths=strengths))
        assert "s-9" in out
        assert "s-10" not in out


class TestMainCli:
    """main() 的 argparse 分支: 无参数应打印帮助并返回 1, 而非静默产出空报告。"""

    def _analyzer(self, monkeypatch, report: dict[str, Any] | None = None) -> MagicMock:
        inst = MagicMock()
        inst.analyze_case.return_value = {"case": "x.md"}
        inst.analyze_all.return_value = [{"case": "x.md"}]
        inst.generate_report.return_value = report or _make_report()
        cls = MagicMock(return_value=inst)
        monkeypatch.setattr(mod, "CaseStudyQualityAnalyzer", cls)
        return inst

    def test_no_args_prints_help_and_returns_nonzero(self, monkeypatch, capsys) -> None:
        self._analyzer(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["_case_report"])
        assert mod.main() == 1
        assert "usage" in capsys.readouterr().out.lower()

    def test_single_path_analyzes_one(self, monkeypatch, capsys, tmp_path) -> None:
        inst = self._analyzer(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["_case_report", "--path", str(tmp_path / "a.md")])
        assert mod.main() == 0
        inst.analyze_case.assert_called_once()
        inst.analyze_all.assert_not_called()
        capsys.readouterr()

    def test_all_flag_uses_analyze_all(self, monkeypatch, capsys) -> None:
        inst = self._analyzer(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["_case_report", "--all"])
        assert mod.main() == 0
        inst.analyze_all.assert_called_once()
        capsys.readouterr()

    def test_json_flag_emits_json(self, monkeypatch, capsys) -> None:
        self._analyzer(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["_case_report", "--all", "--json"])
        assert mod.main() == 0
        assert json.loads(capsys.readouterr().out) is not None

    def test_output_flag_writes_file(self, monkeypatch, capsys, tmp_path) -> None:
        self._analyzer(monkeypatch)
        out_file = tmp_path / "r.json"
        monkeypatch.setattr(sys, "argv", ["_case_report", "--all", "--json", "--output", str(out_file)])
        assert mod.main() == 0
        assert json.loads(out_file.read_text(encoding="utf-8")) is not None
        capsys.readouterr()

    def test_path_wins_over_all(self, monkeypatch, capsys, tmp_path) -> None:
        """同时给 --path 与 --all 时以 --path 为准 —— 对应源码中的 if/elif 顺序。"""
        inst = self._analyzer(monkeypatch)
        monkeypatch.setattr(sys, "argv", ["_case_report", "--path", str(tmp_path / "a.md"), "--all"])
        assert mod.main() == 0
        inst.analyze_case.assert_called_once()
        inst.analyze_all.assert_not_called()
        capsys.readouterr()

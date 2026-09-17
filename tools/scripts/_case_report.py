"""Report formatting and CLI entry for case study quality analysis."""

import json
from pathlib import Path
from typing import Any

from ._case_quality import CaseStudyQualityAnalyzer


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Analyze case study quality")
    parser.add_argument("--path", type=str, help="Path to single case study")
    parser.add_argument("--all", action="store_true", help="Analyze all cases")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--output", type=str, help="Output file path")
    args = parser.parse_args()

    analyzer = CaseStudyQualityAnalyzer()

    if args.path:
        case_path = Path(args.path)
        metrics = analyzer.analyze_case(case_path)
        metrics_list = [metrics]
    elif args.all:
        metrics_list = analyzer.analyze_all()
    else:
        parser.print_help()
        return 1

    report = analyzer.generate_report(metrics_list)

    if args.json:
        output = json.dumps(report, ensure_ascii=False, indent=2)
    else:
        output = format_report(report)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report saved to {args.output}")
    else:
        print(output)

    return 0


def format_report(report: dict[str, Any]) -> str:
    """Format report as human-readable text.

    V2.20 P4-41 拆分: 抽 _format_score_table 收口 6 项均值渲染,
    _format_case_list 收口 top/bottom cases 列表.
    主函数仅 6 段 + 标题收尾.
    """
    lines: list[str] = []
    lines.append("=" * 70)
    lines.append("  📊 Case Study Quality Analysis Report")
    lines.append("=" * 70)
    summary = report["summary"]
    lines.append(f"\n📈 Summary ({summary['total_cases']} cases)")
    lines.extend(_format_score_table(summary["average_scores"]))
    lines.append("\n📊 Categories:")
    lines.append(f"  Excellent (≥80):        {summary['categories']['excellent']}")
    lines.append(f"  Good (60-79):           {summary['categories']['good']}")
    lines.append(f"  Needs Improvement (<60): {summary['categories']['needs_improvement']}")
    lines.extend(_format_case_list("🏆 Top 5 Cases:", report["top_cases"]))
    lines.extend(_format_case_list("📉 Bottom 5 Cases:", report["bottom_cases"]))

    lines.append("\n⚠️  Common Issues:")
    for issue, count in list(report["common_issues"].items())[:10]:
        lines.append(f"  [{count}] {issue}")

    lines.append("\n✅ Common Strengths:")
    for strength, count in list(report["common_strengths"].items())[:10]:
        lines.append(f"  [{count}] {strength}")

    lines.append(f"\n{'=' * 70}")
    lines.append("  Detailed Scores")
    lines.append(f"{'=' * 70}")
    lines.append(f"{'Case':<40} {'Overall':>7} {'Auth':>6} {'Eff':>6} {'Insight':>7} {'Complete':>8} {'X-Ref':>6}")
    lines.append("-" * 85)
    for detail in report["detailed"]:
        lines.append(_format_detail_row(detail))

    return "\n".join(lines)


def _format_score_table(scores: dict[str, float]) -> list[str]:
    """渲染 6 项均值分数表 (模块级 helper).

    Args:
        scores: average_scores 字典

    Returns:
        格式化的字符串列表
    """
    return [
        f"  Overall Average:        {scores['overall']}/100",
        f"  Authenticity:           {scores['authenticity']}/100",
        f"  Efficiency Credibility: {scores['efficiency_credibility']}/100",
        f"  Insight Quality:        {scores['insight_quality']}/100",
        f"  Completeness:           {scores['completeness']}/100",
        f"  Cross-References:       {scores['cross_references']}/100",
    ]


def _format_case_list(header: str, cases: list[dict[str, Any]]) -> list[str]:
    """渲染 top/bottom cases 列表 (模块级 helper).

    Args:
        header: 段标题
        cases: case 字典列表 (含 score/name 字段)

    Returns:
        格式化的字符串列表 (含 header + 各 case 行)
    """
    lines: list[str] = [header]
    for case in cases:
        lines.append(f"  {case['score']:>5.1f}  {case['name']}")
    return lines


def _format_detail_row(detail: dict[str, Any]) -> str:
    """渲染单条 detail 行 (模块级 helper, 7 列固定列宽).

    Args:
        detail: detail 字典 (含 case/overall/authenticity/efficiency/insight/completeness/cross_refs)

    Returns:
        格式化单行字符串
    """
    return (
        f"{detail['case']:<40} "
        f"{detail['overall']:>7.1f} "
        f"{detail['authenticity']:>6.1f} "
        f"{detail['efficiency']:>6.1f} "
        f"{detail['insight']:>7.1f} "
        f"{detail['completeness']:>8.1f} "
        f"{detail['cross_refs']:>6.1f}"
    )

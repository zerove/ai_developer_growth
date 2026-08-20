#!/usr/bin/env python3
"""
Case Study Quality Analyzer

Performs deep quality analysis beyond structural validation:
- Content authenticity scoring
- Efficiency data credibility
- Insight specificity and actionability
- Cross-referencing with INDEX.md and MOC.md
- AI collaboration pattern detection
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class QualityMetrics:
    """Quality metrics for a case study."""

    case_name: str
    authenticity_score: float = 0.0  # 0-100
    efficiency_credibility: float = 0.0  # 0-100
    insight_quality: float = 0.0  # 0-100
    completeness: float = 0.0  # 0-100
    cross_references: float = 0.0  # 0-100
    overall_score: float = 0.0  # 0-100
    issues: list[str] = field(default_factory=list)
    strengths: list[str] = field(default_factory=list)


class CaseStudyQualityAnalyzer:
    """Analyzes case study quality beyond structure."""

    # Patterns indicating real/authentic content
    AUTHENTICITY_PATTERNS = {
        "github_links": r"github\.com/[\w-]+/[\w-]+(/pull/\d+|/commit/[\w]+|/issues/\d+)?",
        "commit_hashes": r"\b[0-9a-f]{7,40}\b",
        "pr_numbers": r"#\d{1,5}",
        "file_paths": r"(src|tools|tests|docs|examples)/[\w/.-]+\.(py|ts|js|md|yml|yaml)",
        "cli_commands": r"(adg|ruff|mypy|pytest|git|docker|kubectl)\s+\w+",
        "error_messages": r"(Error|Exception|FAILED|traceback|line \d+)",
        "version_numbers": r"v?\d+\.\d+\.\d+",
        "timestamps": r"\d{4}-\d{2}-\d{2}",
    }

    # Vague/weak language patterns
    VAGUE_PATTERNS = [
        r"\b(很快|很高|很大|很多|很强|很方便|很高效|显著提升|大幅提升)\b",
        r"\b(significantly|dramatically|massively|huge|tons of)\b",
        r"10x|100x|1000x",  # Unrealistic claims
    ]

    # Strong/credible language patterns
    STRONG_PATTERNS = [
        r"\d+\.?\d*\s*[x%]",  # Specific multipliers/percentages
        r"\d+\.?\d*\s*(hours?|minutes?|days?|weeks?)",  # Specific time
        r"(reduced|increased|improved|decreased)\s+\d+",  # Specific changes
        r"(PR|commit|issue)\s*#?\d+",  # Specific references
    ]

    def __init__(self, case_studies_dir: Path = Path("case-studies")):
        self.case_studies_dir = case_studies_dir
        self.index_content = self._load_index()
        self.moc_content = self._load_moc()

    def _load_index(self) -> str:
        """Load INDEX.md for cross-reference checking."""
        index_path = Path("INDEX.md")
        if index_path.exists():
            return index_path.read_text(encoding="utf-8")
        return ""

    def _load_moc(self) -> str:
        """Load MOC.md for cross-reference checking."""
        moc_path = Path("docs/MOC.md")
        if moc_path.exists():
            return moc_path.read_text(encoding="utf-8")
        return ""

    def analyze_all(self) -> list[QualityMetrics]:
        """Analyze all case studies."""
        results = []
        for case_path in sorted(self.case_studies_dir.iterdir()):
            if case_path.is_dir() or case_path.suffix == ".md":
                if (
                    case_path.name.startswith(".")
                    or case_path.name == "TEMPLATE-community.md"
                ):
                    continue
                metrics = self.analyze_case(case_path)
                results.append(metrics)
        return results

    def analyze_case(self, case_path: Path) -> QualityMetrics:
        """Analyze a single case study."""
        # Support both flat .md and directory with README.md
        readme_path = case_path
        if case_path.is_dir():
            readme_path = case_path / "README.md"

        if not readme_path.exists():
            return QualityMetrics(
                case_name=case_path.name,
                issues=["Missing README.md or case study file"],
            )

        content = readme_path.read_text(encoding="utf-8")
        case_name = case_path.name.replace(".md", "")

        metrics = QualityMetrics(case_name=case_name)

        # Analyze each dimension
        metrics.authenticity_score = self._analyze_authenticity(content)
        metrics.efficiency_credibility = self._analyze_efficiency(content)
        metrics.insight_quality = self._analyze_insights(content)
        metrics.completeness = self._analyze_completeness(content)
        metrics.cross_references = self._analyze_cross_references(content, case_name)

        # Calculate overall score (weighted)
        weights = {
            "authenticity": 0.25,
            "efficiency": 0.25,
            "insight": 0.20,
            "completeness": 0.15,
            "cross_refs": 0.15,
        }
        metrics.overall_score = (
            metrics.authenticity_score * weights["authenticity"]
            + metrics.efficiency_credibility * weights["efficiency"]
            + metrics.insight_quality * weights["insight"]
            + metrics.completeness * weights["completeness"]
            + metrics.cross_references * weights["cross_refs"]
        )

        # Generate issues and strengths
        self._generate_feedback(metrics, content)

        return metrics

    def _analyze_authenticity(self, content: str) -> float:
        """Score authenticity based on concrete evidence."""
        score = 0.0
        max_score = 100.0

        # Check for authenticity patterns
        found_patterns = 0
        for pattern_name, pattern in self.AUTHENTICITY_PATTERNS.items():
            matches = len(re.findall(pattern, content))
            if matches > 0:
                found_patterns += 1
                # Bonus for multiple matches
                score += min(matches * 5, 20)

        # Base score from pattern diversity
        score += (found_patterns / len(self.AUTHENTICITY_PATTERNS)) * 40

        # Check for vague language (penalty)
        vague_count = 0
        for pattern in self.VAGUE_PATTERNS:
            vague_count += len(re.findall(pattern, content, re.IGNORECASE))
        score -= vague_count * 5

        # Check for strong language (bonus)
        strong_count = 0
        for pattern in self.STRONG_PATTERNS:
            strong_count += len(re.findall(pattern, content, re.IGNORECASE))
        score += min(strong_count * 3, 30)

        return max(0, min(max_score, score))

    def _analyze_efficiency(self, content: str) -> float:
        """Score efficiency data credibility."""
        score = 0.0
        max_score = 100.0

        # Find efficiency tables
        table_patterns = [
            r"\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|",
            r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|.*提升.*\|",
            r"\|.*指标.*\|.*使用 AI 前.*\|.*使用 AI 后.*\|.*提升.*\|",
            r"\|.*Metric.*\|.*Before.*\|.*After.*\|.*Boost.*\|",
        ]

        has_table = any(re.search(p, content) for p in table_patterns)
        if not has_table:
            return 0.0

        score += 30  # Has table

        # Extract and validate table rows
        data_rows = self._extract_table_rows(content)
        if data_rows:
            score += 20
            valid_rows = 0
            for row in data_rows:
                if self._validate_row_format(row):
                    valid_rows += 1
            if valid_rows > 0:
                score += min(valid_rows * 10, 30)

                # Check for realistic values
                realistic = self._check_realistic_values(data_rows)
                if realistic:
                    score += 20

        return min(max_score, score)

    def _extract_table_rows(self, content: str) -> list[str]:
        """Extract table data rows."""
        lines = content.split("\n")
        in_table = False
        data_rows = []

        for line in lines:
            if "|" in line and (
                "阶段" in line
                or "总计" in line
                or "指标" in line
                or "Metric" in line
                or "---" in line
            ):
                in_table = True
            if in_table and line.strip().startswith("|"):
                if "---" not in line:  # Skip separator rows
                    data_rows.append(line)
            elif in_table and not line.strip().startswith("|"):
                break

        return data_rows

    def _validate_row_format(self, row: str) -> bool:
        """Validate table row has expected columns."""
        cols = [c.strip() for c in row.split("|")[1:-1]]
        return len(cols) >= 4

    def _check_realistic_values(self, data_rows: list[str]) -> bool:
        """Check if efficiency values are realistic."""
        for row in data_rows:
            cols = [c.strip() for c in row.split("|")[1:-1]]
            if len(cols) >= 4:
                stage, traditional, ai, boost = cols[:4]
                if "总计" in stage:
                    try:
                        # Parse hours
                        t_match = re.search(r"([\d.]+)\s*小时", traditional)
                        a_match = re.search(r"([\d.]+)\s*小时", ai)
                        b_match = re.search(r"([\d.]+)x", boost)

                        if t_match and a_match and b_match:
                            t_hours = float(t_match.group(1))
                            a_hours = float(a_match.group(1))
                            boost_val = float(b_match.group(1))

                            expected = t_hours / a_hours
                            # Allow 50% tolerance for rounding
                            if abs(expected - boost_val) < max(0.5, expected * 0.5):
                                return True
                    except (ValueError, ZeroDivisionError):
                        pass
        return False

    def _analyze_insights(self, content: str) -> float:
        """Score insight quality and specificity."""
        score = 0.0
        max_score = 100.0

        # Extract insights section
        insights_text = self._extract_insights_section(content)
        if not insights_text:
            return 0.0

        score += 20  # Has insights section

        # Count numbered insights
        insights = self._extract_numbered_insights(insights_text)
        if insights:
            score += min(len(insights) * 10, 40)

            # Check insight specificity
            specific_count = 0
            for insight in insights:
                if self._is_specific_insight(insight):
                    specific_count += 1
            score += min(specific_count * 5, 25)

            # Check for code/pattern references
            code_refs = sum(
                1
                for i in insights
                if re.search(r"(函数|类|模块|API|pattern|模式|pattern)", i)
            )
            score += min(code_refs * 5, 15)

        return min(max_score, score)

    def _extract_insights_section(self, content: str) -> str:
        """Extract insights section from content."""
        insight_headers = [
            "## 关键洞察",
            "## 💡 关键洞察",
            "## 洞察",
            "## 关键技术决策",
            "## 关键洞察与反思",
            "## 关键洞察与总结",
        ]

        for header in insight_headers:
            parts = content.split(header)
            if len(parts) >= 2:
                # Get content until next major section
                next_section = re.split(r"\n## ", parts[1])[0]
                return next_section
        return ""

    def _extract_numbered_insights(self, insights_text: str) -> list[str]:
        """Extract numbered insights."""
        # Format 1: "1. **洞察 1** : ..."
        numbered = re.findall(
            r"^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$", insights_text, re.MULTILINE
        )
        if numbered:
            return [item[-1] for item in numbered]

        # Format 2: "1. ..."
        numbered = re.findall(r"^\d+\.\s+(.+)$", insights_text, re.MULTILINE)
        if numbered:
            return numbered

        # Format 3: bullet points
        numbered = re.findall(r"^[-*]\s+(.+)$", insights_text, re.MULTILINE)
        if numbered:
            return numbered

        # Format 4: sub-headers
        numbered = re.findall(r"^###\s+\d+\.\s+(.+)$", insights_text, re.MULTILINE)
        return numbered

    def _is_specific_insight(self, insight: str) -> bool:
        """Check if insight is specific (has numbers, code refs, etc.)."""
        # Has specific numbers
        if re.search(r"\d+\.?\d*\s*(x|%|hours?|minutes?|times?)", insight):
            return True
        # References specific code patterns
        if re.search(r"(函数|类|模块|API|pattern|模式|工具|技术|方法)", insight):
            return True
        # Mentions specific tools/tech
        if re.search(
            r"(Claude|GPT|Cursor|Copilot|ruff|mypy|pytest|ADG|AST|MCP)", insight
        ):
            return True
        return False

    def _analyze_completeness(self, content: str) -> float:
        """Score completeness of required sections."""
        required = [
            "背景",
            "AI 协作",
            "效率",
            "洞察",
            "适用场景",
            "交付物",
            "提交前检查",
        ]
        found = 0
        for req in required:
            if req in content:
                found += 1

        base_score = (found / len(required)) * 70

        # Bonus for detailed sections
        detailed_sections = [
            ("效率对比", 10),
            ("交付物清单", 10),
            ("适用场景", 10),
        ]
        for section, bonus in detailed_sections:
            if section in content:
                base_score += bonus

        return min(100, base_score)

    def _analyze_cross_references(self, content: str, case_name: str) -> float:
        """Score cross-references to INDEX.md and MOC.md."""
        score = 0.0
        max_score = 100.0

        # Check wikilinks to docs/
        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
        valid_wikilinks = 0
        for link in wikilinks:
            target = link.split("|")[0].strip() if "|" in link else link.strip()
            if target.startswith(("docs/", "case-studies/", "examples/")):
                target_path = Path(target)
                if target_path.exists() or target_path.with_suffix(".md").exists():
                    valid_wikilinks += 1

        if wikilinks:
            score += min(len(wikilinks) * 5, 30)
            score += min(valid_wikilinks * 10, 40)

        # Check if case is listed in INDEX.md
        if case_name in self.index_content:
            score += 20

        # Check if case is listed in MOC.md
        if case_name in self.moc_content:
            score += 10

        return min(max_score, score)

    def _generate_feedback(self, metrics: QualityMetrics, content: str) -> None:
        """Generate issues and strengths based on analysis."""
        if metrics.authenticity_score < 50:
            metrics.issues.append(
                "Low authenticity - missing concrete evidence (links, commits, file paths)"
            )
        elif metrics.authenticity_score > 80:
            metrics.strengths.append("High authenticity with concrete references")

        if metrics.efficiency_credibility < 50:
            metrics.issues.append(
                "Efficiency data lacks credibility - missing or unrealistic tables"
            )
        elif metrics.efficiency_credibility > 80:
            metrics.strengths.append(
                "Credible efficiency data with validated calculations"
            )

        if metrics.insight_quality < 50:
            metrics.issues.append(
                "Insights are vague or insufficient - need specific, actionable findings"
            )
        elif metrics.insight_quality > 80:
            metrics.strengths.append(
                "High-quality specific insights with code/tool references"
            )

        if metrics.completeness < 70:
            metrics.issues.append("Missing required sections")

        if metrics.cross_references < 30:
            metrics.issues.append(
                "Poor cross-referencing - not linked in INDEX.md/MOC.md"
            )
        elif metrics.cross_references > 70:
            metrics.strengths.append("Well integrated with knowledge base")

    def generate_report(self, metrics_list: list[QualityMetrics]) -> dict[str, Any]:
        """Generate comprehensive quality report."""
        if not metrics_list:
            return {"error": "No case studies analyzed"}

        # Sort by overall score
        sorted_metrics = sorted(
            metrics_list, key=lambda m: m.overall_score, reverse=True
        )

        avg_overall = sum(m.overall_score for m in metrics_list) / len(metrics_list)
        avg_authenticity = sum(m.authenticity_score for m in metrics_list) / len(
            metrics_list
        )
        avg_efficiency = sum(m.efficiency_credibility for m in metrics_list) / len(
            metrics_list
        )
        avg_insight = sum(m.insight_quality for m in metrics_list) / len(metrics_list)
        avg_completeness = sum(m.completeness for m in metrics_list) / len(metrics_list)
        avg_cross = sum(m.cross_references for m in metrics_list) / len(metrics_list)

        # Categorize
        excellent = [m for m in metrics_list if m.overall_score >= 80]
        good = [m for m in metrics_list if 60 <= m.overall_score < 80]
        needs_improvement = [m for m in metrics_list if m.overall_score < 60]

        return {
            "summary": {
                "total_cases": len(metrics_list),
                "average_scores": {
                    "overall": round(avg_overall, 1),
                    "authenticity": round(avg_authenticity, 1),
                    "efficiency_credibility": round(avg_efficiency, 1),
                    "insight_quality": round(avg_insight, 1),
                    "completeness": round(avg_completeness, 1),
                    "cross_references": round(avg_cross, 1),
                },
                "categories": {
                    "excellent": len(excellent),
                    "good": len(good),
                    "needs_improvement": len(needs_improvement),
                },
            },
            "top_cases": [
                {"name": m.case_name, "score": round(m.overall_score, 1)}
                for m in sorted_metrics[:5]
            ],
            "bottom_cases": [
                {"name": m.case_name, "score": round(m.overall_score, 1)}
                for m in sorted_metrics[-5:]
            ],
            "common_issues": self._aggregate_issues(metrics_list),
            "common_strengths": self._aggregate_strengths(metrics_list),
            "detailed": [
                {
                    "case": m.case_name,
                    "overall": round(m.overall_score, 1),
                    "authenticity": round(m.authenticity_score, 1),
                    "efficiency": round(m.efficiency_credibility, 1),
                    "insight": round(m.insight_quality, 1),
                    "completeness": round(m.completeness, 1),
                    "cross_refs": round(m.cross_references, 1),
                    "issues": m.issues,
                    "strengths": m.strengths,
                }
                for m in sorted_metrics
            ],
        }

    def _aggregate_issues(self, metrics_list: list[QualityMetrics]) -> dict[str, int]:
        """Aggregate common issues."""
        issues_count: dict[str, int] = {}
        for m in metrics_list:
            for issue in m.issues:
                issues_count[issue] = issues_count.get(issue, 0) + 1
        return dict(sorted(issues_count.items(), key=lambda x: x[1], reverse=True))

    def _aggregate_strengths(
        self, metrics_list: list[QualityMetrics]
    ) -> dict[str, int]:
        """Aggregate common strengths."""
        strengths_count: dict[str, int] = {}
        for m in metrics_list:
            for strength in m.strengths:
                strengths_count[strength] = strengths_count.get(strength, 0) + 1
        return dict(sorted(strengths_count.items(), key=lambda x: x[1], reverse=True))


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
    """Format report as human-readable text."""
    lines = []
    lines.append("=" * 70)
    lines.append("  📊 Case Study Quality Analysis Report")
    lines.append("=" * 70)

    summary = report["summary"]
    lines.append(f"\n📈 Summary ({summary['total_cases']} cases)")
    lines.append(
        f"  Overall Average:        {summary['average_scores']['overall']}/100"
    )
    lines.append(
        f"  Authenticity:           {summary['average_scores']['authenticity']}/100"
    )
    lines.append(
        f"  Efficiency Credibility: {summary['average_scores']['efficiency_credibility']}/100"
    )
    lines.append(
        f"  Insight Quality:        {summary['average_scores']['insight_quality']}/100"
    )
    lines.append(
        f"  Completeness:           {summary['average_scores']['completeness']}/100"
    )
    lines.append(
        f"  Cross-References:       {summary['average_scores']['cross_references']}/100"
    )

    lines.append("\n📊 Categories:")
    lines.append(f"  Excellent (≥80):        {summary['categories']['excellent']}")
    lines.append(f"  Good (60-79):           {summary['categories']['good']}")
    lines.append(
        f"  Needs Improvement (<60): {summary['categories']['needs_improvement']}"
    )

    lines.append("\n🏆 Top 5 Cases:")
    for case in report["top_cases"]:
        lines.append(f"  {case['score']:>5.1f}  {case['name']}")

    lines.append("\n📉 Bottom 5 Cases:")
    for case in report["bottom_cases"]:
        lines.append(f"  {case['score']:>5.1f}  {case['name']}")

    lines.append("\n⚠️  Common Issues:")
    for issue, count in list(report["common_issues"].items())[:10]:
        lines.append(f"  [{count}] {issue}")

    lines.append("\n✅ Common Strengths:")
    for strength, count in list(report["common_strengths"].items())[:10]:
        lines.append(f"  [{count}] {strength}")

    lines.append(f"\n{'=' * 70}")
    lines.append("  Detailed Scores")
    lines.append(f"{'=' * 70}")
    lines.append(
        f"{'Case':<40} {'Overall':>7} {'Auth':>6} {'Eff':>6} {'Insight':>7} {'Complete':>8} {'X-Ref':>6}"
    )
    lines.append("-" * 85)
    for detail in report["detailed"]:
        lines.append(
            f"{detail['case']:<40} "
            f"{detail['overall']:>7.1f} "
            f"{detail['authenticity']:>6.1f} "
            f"{detail['efficiency']:>6.1f} "
            f"{detail['insight']:>7.1f} "
            f"{detail['completeness']:>8.1f} "
            f"{detail['cross_refs']:>6.1f}"
        )

    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    sys.exit(main())

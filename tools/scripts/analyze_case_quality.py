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
        """Analyze all case studies.

        V2.20 P4-24 拆分: 抽 _should_skip_case 收口 3 守卫 (dir/md/隐藏/模板),
        主函数仅遍历 + 委托.
        """
        results: list[QualityMetrics] = []
        for case_path in sorted(self.case_studies_dir.iterdir()):
            if self._should_skip_case(case_path):
                continue
            metrics = self.analyze_case(case_path)
            results.append(metrics)
        return results

    def _should_skip_case(self, case_path: Path) -> bool:
        """判断 case 路径是否应跳过 (非 case_study 或 隐藏文件/模板).

        Args:
            case_path: 案例路径

        Returns:
            True if 应跳过
        """
        if not (case_path.is_dir() or case_path.suffix == ".md"):
            return True
        if case_path.name.startswith("."):
            return True
        return case_path.name == "TEMPLATE-community.md"

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
        """Score efficiency data credibility.

        V2.20 P4-21 拆分: 抽 _has_efficiency_table 收口 4 个 regex 模式匹配,
        _score_table_rows 收口行验证 + 真实值检查.
        主函数仅 3 段分数累加.
        """
        if not self._has_efficiency_table(content):
            return 0.0

        score = 30.0  # Has table
        data_rows = self._extract_table_rows(content)
        if data_rows:
            score += 20.0
            score += self._score_table_rows(data_rows)
        return min(100.0, score)

    def _has_efficiency_table(self, content: str) -> bool:
        """检查 content 是否含效率对比表格 (中英文 4 种模式).

        Args:
            content: 案例内容

        Returns:
            True if 任一表格模式匹配
        """
        table_patterns = [
            r"\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|",
            r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|.*提升.*\|",
            r"\|.*指标.*\|.*使用 AI 前.*\|.*使用 AI 后.*\|.*提升.*\|",
            r"\|.*Metric.*\|.*Before.*\|.*After.*\|.*Boost.*\|",
        ]
        return any(re.search(p, content) for p in table_patterns)

    def _score_table_rows(self, data_rows: list[str]) -> float:
        """根据表格行数 + 真实值校验计算额外分数.

        Args:
            data_rows: 表格数据行列表

        Returns:
            0/20/30/50 (有效行 + 真实值) 累加
        """
        valid_rows = sum(1 for row in data_rows if self._validate_row_format(row))
        if valid_rows == 0:
            return 0.0
        score = float(min(valid_rows * 10, 30))
        if self._check_realistic_values(data_rows):
            score += 20.0
        return score

    def _is_table_header(self, line: str) -> bool:
        """判断行是否为表格表头 (含 阶段/总计/指标/Metric/--- 关键字).

        V2.18 P3-12 拆分: 从 _extract_table_rows (C=13) 抽出.
        """
        if "|" not in line:
            return False
        return any(keyword in line for keyword in ("阶段", "总计", "指标", "Metric", "---"))

    def _is_separator_row(self, line: str) -> bool:
        """判断行是否为表格分隔行 (markdown 表格的 |---|).

        V2.18 P3-12 拆分: 从 _extract_table_rows (C=13) 抽出.
        """
        return "---" in line

    def _extract_table_rows(self, content: str) -> list[str]:
        """Extract table data rows (orchestrator).

        V2.18 P3-12 拆分: 从 C=13 / 30 行主函数拆出 2 个行分类 helper.
        主函数仅负责: state machine (in_table) → 收集 data_rows.
        """
        data_rows: list[str] = []
        in_table = False

        for line in content.split("\n"):
            if self._is_table_header(line):
                in_table = True
            if not in_table:
                continue
            if not line.strip().startswith("|"):
                break
            if self._is_separator_row(line):
                continue
            data_rows.append(line)

        return data_rows

    def _validate_row_format(self, row: str) -> bool:
        """Validate table row has expected columns."""
        cols = [c.strip() for c in row.split("|")[1:-1]]
        return len(cols) >= 4

    def _check_realistic_values(self, data_rows: list[str]) -> bool:
        """Check if efficiency values are realistic.

        V2.20 P4-18 拆分: 抽 _parse_row_metrics 收口 3 个 re.search + 数值提取,
        _validate_metric_consistency 收口比值校验.
        V2.20 P4-23 拆分: 抽 _is_valid_total_row 收口行守卫 (>=4 列 + 总计),
        主函数仅遍历 + 委托.
        """
        for row in data_rows:
            metrics = self._extract_total_row_metrics(row)
            if metrics is None:
                continue
            if self._validate_metric_consistency(*metrics):
                return True
        return False

    def _is_valid_total_row(self, row: str) -> bool:
        """判断行是否为有效 '总计' 数据行 (>=4 列 + 含 '总计').

        Args:
            row: markdown 表格行

        Returns:
            True if 有效总计行
        """
        cols = [c.strip() for c in row.split("|")[1:-1]]
        if len(cols) < 4:
            return False
        return "总计" in cols[0]

    def _extract_total_row_metrics(self, row: str) -> tuple[float, float, float] | None:
        """提取总计行的 3 个 metric (t_hours, a_hours, boost_val).

        Args:
            row: markdown 表格行

        Returns:
            (t_hours, a_hours, boost_val) 或 None (非总计行/解析失败)
        """
        if not self._is_valid_total_row(row):
            return None
        cols = [c.strip() for c in row.split("|")[1:-1]]
        return self._parse_row_metrics(cols[1], cols[2], cols[3])

    def _parse_row_metrics(self, traditional: str, ai: str, boost: str) -> tuple[float, float, float] | None:
        """解析表格行 3 列 (traditional_hours, ai_hours, boost_factor).

        Args:
            traditional: 传统耗时字符串
            ai: AI 耗时字符串
            boost: 提升倍数字符串 (如 "3.5x")

        Returns:
            (t_hours, a_hours, boost_val) 或 None (解析失败)
        """
        try:
            t_match = re.search(r"([\d.]+)\s*小时", traditional)
            a_match = re.search(r"([\d.]+)\s*小时", ai)
            b_match = re.search(r"([\d.]+)x", boost)
            if not (t_match and a_match and b_match):
                return None
            return float(t_match.group(1)), float(a_match.group(1)), float(b_match.group(1))
        except (ValueError, ZeroDivisionError):
            return None

    def _validate_metric_consistency(self, t_hours: float, a_hours: float, boost_val: float) -> bool:
        """校验 t_hours / a_hours 与 boost_val 偏差是否在容差内.

        Args:
            t_hours: 传统耗时
            a_hours: AI 耗时
            boost_val: 报告的提升倍数

        Returns:
            True if 偏差在 50% (或绝对 0.5) 容差内
        """
        expected = t_hours / a_hours
        return abs(expected - boost_val) < max(0.5, expected * 0.5)

    def _analyze_insights(self, content: str) -> float:
        """Score insight quality and specificity.

        V2.20 P4-22 拆分: 抽 _count_specific_insights 收口 specific 检查,
        _count_code_references 收口 code_refs regex.
        主函数仅 3 段分数累加.
        """
        score = 0.0
        max_score = 100.0

        insights_text = self._extract_insights_section(content)
        if not insights_text:
            return 0.0
        score += 20  # Has insights section

        insights = self._extract_numbered_insights(insights_text)
        if not insights:
            return min(max_score, score)

        score += min(len(insights) * 10, 40)
        score += min(self._count_specific_insights(insights) * 5, 25)
        score += min(self._count_code_references(insights) * 5, 15)
        return min(max_score, score)

    def _count_specific_insights(self, insights: list[str]) -> int:
        """统计具体洞察 (含具体细节) 数.

        Args:
            insights: 编号洞察列表

        Returns:
            满足 _is_specific_insight 的数量
        """
        return sum(1 for i in insights if self._is_specific_insight(i))

    def _count_code_references(self, insights: list[str]) -> int:
        """统计含代码/模式引用的洞察数.

        Args:
            insights: 编号洞察列表

        Returns:
            含 函数/类/模块/API/pattern/模式 关键字的数量
        """
        return sum(1 for i in insights if re.search(r"(函数|类|模块|API|pattern|模式|pattern)", i))

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
        numbered = re.findall(r"^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$", insights_text, re.MULTILINE)
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
        if re.search(r"(Claude|GPT|Cursor|Copilot|ruff|mypy|pytest|ADG|AST|MCP)", insight):
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
        """Score cross-references to INDEX.md and MOC.md.

        V2.20 P4-20 拆分: 抽 _count_valid_wikilinks 收口 wikilink 解析 + 存在性检查,
        主函数仅 3 段分数累加.
        """
        score = 0.0
        max_score = 100.0

        wikilinks = re.findall(r"\[\[([^\]]+)\]\]", content)
        if wikilinks:
            valid_wikilinks = self._count_valid_wikilinks(wikilinks)
            score += min(len(wikilinks) * 5, 30)
            score += min(valid_wikilinks * 10, 40)

        if case_name in self.index_content:
            score += 20
        if case_name in self.moc_content:
            score += 10

        return min(max_score, score)

    def _count_valid_wikilinks(self, wikilinks: list[str]) -> int:
        """统计指向真实存在文件的 wikilink 数.

        V2.20 P4-36 拆分: 抽 _is_valid_wikilink_target 收口 wikilink 有效性判定,
        _parse_wikilink_target 收口 alias 拆分.
        主函数仅遍历 + 委托.

        Args:
            wikilinks: [[target]] 或 [[target|alias]] 列表

        Returns:
            有效 (文件存在) wikilink 数
        """
        return sum(1 for link in wikilinks if self._is_valid_wikilink_target(link))

    def _is_valid_wikilink_target(self, link: str) -> bool:
        """判断 wikilink 是否指向真实存在文件 (含 alias 拆分 + 路径前缀 + 存在性).

        Args:
            link: 单个 wikilink 字符串 (如 'docs/foo|alias')

        Returns:
            True if 有效 wikilink 目标
        """
        target = self._parse_wikilink_target(link)
        if not target.startswith(("docs/", "case-studies/", "examples/")):
            return False
        target_path = Path(target)
        return target_path.exists() or target_path.with_suffix(".md").exists()

    def _parse_wikilink_target(self, link: str) -> str:
        """解析 wikilink 字符串, 返回 target 部分 (无 alias).

        Args:
            link: wikilink 字符串

        Returns:
            target 路径 (无 |alias 后缀)
        """
        return link.split("|")[0].strip() if "|" in link else link.strip()

    def _generate_feedback(self, metrics: QualityMetrics, content: str) -> None:
        """Generate issues and strengths based on analysis.

        V2.20 P4-19 拆分: 抽 _add_threshold_feedback 收口阈值判定 + issue/strength 添加,
        主函数 5 段委托, 每段 1 行.
        """
        self._add_threshold_feedback(
            metrics,
            metrics.authenticity_score,
            low_issue="Low authenticity - missing concrete evidence (links, commits, file paths)",
            high_strength="High authenticity with concrete references",
        )
        self._add_threshold_feedback(
            metrics,
            metrics.efficiency_credibility,
            low_issue="Efficiency data lacks credibility - missing or unrealistic tables",
            high_strength="Credible efficiency data with validated calculations",
        )
        self._add_threshold_feedback(
            metrics,
            metrics.insight_quality,
            low_issue="Insights are vague or insufficient - need specific, actionable findings",
            high_strength="High-quality specific insights with code/tool references",
        )
        if metrics.completeness < 70:
            metrics.issues.append("Missing required sections")
        self._add_threshold_feedback(
            metrics,
            metrics.cross_references,
            low_issue="Poor cross-referencing - not linked in INDEX.md/MOC.md",
            high_strength="Well integrated with knowledge base",
            low_threshold=30,
            high_threshold=70,
        )

    def _add_threshold_feedback(
        self,
        metrics: QualityMetrics,
        score: float,
        low_issue: str,
        high_strength: str,
        low_threshold: int = 50,
        high_threshold: int = 80,
    ) -> None:
        """根据分数阈值添加 issue (低) 或 strength (高) 反馈.

        Args:
            metrics: 指标对象 (in-place 修改)
            score: 当前分数
            low_issue: 分数 < low_threshold 时添加的 issue
            high_strength: 分数 > high_threshold 时添加的 strength
            low_threshold: 低分阈值 (默认 50)
            high_threshold: 高分阈值 (默认 80)
        """
        if score < low_threshold:
            metrics.issues.append(low_issue)
        elif score > high_threshold:
            metrics.strengths.append(high_strength)

    def _build_summary(
        self,
        metrics_list: list[QualityMetrics],
    ) -> dict[str, Any]:
        """构建 summary 段: 平均分 + 三档分类.

        V2.18 P3-1 拆分: 从 generate_report (C=17) 抽出.
        V2.20 P4-17 拆分: 抽 _compute_average_scores 收口 6 项均值,
        _categorize_scores 收口三档分类.
        """
        averages = self._compute_average_scores(metrics_list)
        categories = self._categorize_scores(metrics_list)

        return {
            "total_cases": len(metrics_list),
            "average_scores": averages,
            "categories": categories,
        }

    def _compute_average_scores(self, metrics_list: list[QualityMetrics]) -> dict[str, float]:
        """计算 6 项平均分 (overall/authenticity/efficiency/insight/completeness/cross).

        V2.20 P4-33 拆分: 抽 _avg_score 收口单指标均值计算, 6 项字段各调一次.

        Args:
            metrics_list: 案例指标列表

        Returns:
            {key: rounded_avg}
        """
        return {
            "overall": self._avg_score(metrics_list, "overall_score"),
            "authenticity": self._avg_score(metrics_list, "authenticity_score"),
            "efficiency_credibility": self._avg_score(metrics_list, "efficiency_credibility"),
            "insight_quality": self._avg_score(metrics_list, "insight_quality"),
            "completeness": self._avg_score(metrics_list, "completeness"),
            "cross_references": self._avg_score(metrics_list, "cross_references"),
        }

    def _avg_score(self, metrics_list: list[QualityMetrics], attr: str) -> float:
        """计算 metrics_list 中指定属性的均值 (rounded to 1 decimal).

        Args:
            metrics_list: 案例指标列表
            attr: QualityMetrics 属性名

        Returns:
            均值 (rounded)
        """
        n = len(metrics_list)
        return round(sum(getattr(m, attr) for m in metrics_list) / n, 1)

    def _categorize_scores(self, metrics_list: list[QualityMetrics]) -> dict[str, int]:
        """按 overall_score 分为三档 (excellent/good/needs_improvement).

        V2.20 P4-34 拆分: 抽 _count_at_or_above 收口分数阈值判定,
        三档各调一次.

        Args:
            metrics_list: 案例指标列表

        Returns:
            {category: count}
        """
        return {
            "excellent": self._count_at_or_above(metrics_list, 80),
            "good": len(metrics_list) - self._count_at_or_above(metrics_list, 80) - self._count_below(metrics_list, 60),
            "needs_improvement": self._count_below(metrics_list, 60),
        }

    def _count_at_or_above(self, metrics_list: list[QualityMetrics], threshold: int) -> int:
        """统计 overall_score >= threshold 的案例数.

        Args:
            metrics_list: 案例指标列表
            threshold: 分数阈值

        Returns:
            达标数
        """
        return sum(1 for m in metrics_list if m.overall_score >= threshold)

    def _count_below(self, metrics_list: list[QualityMetrics], threshold: int) -> int:
        """统计 overall_score < threshold 的案例数.

        Args:
            metrics_list: 案例指标列表
            threshold: 分数阈值

        Returns:
            未达标数
        """
        return sum(1 for m in metrics_list if m.overall_score < threshold)

    def _build_extremes(
        self,
        sorted_metrics: list[QualityMetrics],
        count: int = 5,
    ) -> "tuple[list[dict[str, Any]], list[dict[str, Any]]]":
        """构建 top/bottom cases (按分数排序).

        V2.18 P3-1 拆分: 从 generate_report (C=17) 抽出.
        返回 (top_cases, bottom_cases) 元组.
        """
        case_summary = [{"name": m.case_name, "score": round(m.overall_score, 1)} for m in sorted_metrics]
        return case_summary[:count], case_summary[-count:]

    def _build_detailed(
        self,
        sorted_metrics: list[QualityMetrics],
    ) -> list[dict[str, Any]]:
        """构建 detailed 段: 每个 case 的完整指标.

        V2.18 P3-1 拆分: 从 generate_report (C=17) 抽出.
        """
        return [
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
        ]

    def generate_report(self, metrics_list: list[QualityMetrics]) -> dict[str, Any]:
        """Generate comprehensive quality report (orchestrator).

        V2.18 P3-1 拆分: 从 C=17 / 100+ 行主函数拆出 3 个 _build_* helper.
        主函数仅负责: 排序 → 4 段构建 → 合并.
        """
        if not metrics_list:
            return {"error": "No case studies analyzed"}

        sorted_metrics = sorted(metrics_list, key=lambda m: m.overall_score, reverse=True)

        top_cases, bottom_cases = self._build_extremes(sorted_metrics)

        return {
            "summary": self._build_summary(metrics_list),
            "top_cases": top_cases,
            "bottom_cases": bottom_cases,
            "common_issues": self._aggregate_issues(metrics_list),
            "common_strengths": self._aggregate_strengths(metrics_list),
            "detailed": self._build_detailed(sorted_metrics),
        }

    def _aggregate_issues(self, metrics_list: list[QualityMetrics]) -> dict[str, int]:
        """Aggregate common issues."""
        issues_count: dict[str, int] = {}
        for m in metrics_list:
            for issue in m.issues:
                issues_count[issue] = issues_count.get(issue, 0) + 1
        return dict(sorted(issues_count.items(), key=lambda x: x[1], reverse=True))

    def _aggregate_strengths(self, metrics_list: list[QualityMetrics]) -> dict[str, int]:
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
    lines.append(f"  Overall Average:        {summary['average_scores']['overall']}/100")
    lines.append(f"  Authenticity:           {summary['average_scores']['authenticity']}/100")
    lines.append(f"  Efficiency Credibility: {summary['average_scores']['efficiency_credibility']}/100")
    lines.append(f"  Insight Quality:        {summary['average_scores']['insight_quality']}/100")
    lines.append(f"  Completeness:           {summary['average_scores']['completeness']}/100")
    lines.append(f"  Cross-References:       {summary['average_scores']['cross_references']}/100")

    lines.append("\n📊 Categories:")
    lines.append(f"  Excellent (≥80):        {summary['categories']['excellent']}")
    lines.append(f"  Good (60-79):           {summary['categories']['good']}")
    lines.append(f"  Needs Improvement (<60): {summary['categories']['needs_improvement']}")

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
    lines.append(f"{'Case':<40} {'Overall':>7} {'Auth':>6} {'Eff':>6} {'Insight':>7} {'Complete':>8} {'X-Ref':>6}")
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

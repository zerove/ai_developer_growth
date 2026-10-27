"""Case study 校验与评分共用的纯函数。

`validate_case_study.py`（结构校验）与 `_case_quality.py`（质量评分）此前各自
维护一份表格/洞察解析逻辑，阈值与边界条件逐渐分叉。这里收口为单一实现，
调用方只保留各自的策略开关（是否需要 Boost 列、是否截断到下一节）。
"""

from __future__ import annotations

import re

INSIGHT_HEADERS = (
    "## 关键洞察",
    "## 💡 关键洞察",
    "## 洞察",
    "## 关键技术决策",
    "## 关键洞察与反思",
    "## 关键洞察与总结",
)

EFFICIENCY_TABLE_PATTERNS = (
    r"\|.*阶段.*\|.*传统.*\|.*AI.*\|.*提升.*\|",
    r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|.*提升.*\|",
    r"\|.*指标.*\|.*使用 AI 前.*\|.*使用 AI 后.*\|.*提升.*\|",
    r"\|.*Metric.*\|.*Before.*\|.*After.*\|.*Boost.*\|",
    r"\|.*阶段.*\|.*传统.*\|.*AI.*\|",
    r"\|.*指标.*\|.*优化前.*\|.*优化后.*\|",
    r"\|.*Metric.*\|.*Before.*\|.*After.*\|",
)

BOOST_COLUMN_PATTERN_COUNT = 4


def has_efficiency_table(content: str, *, require_boost_column: bool = False) -> bool:
    patterns = (
        EFFICIENCY_TABLE_PATTERNS[:BOOST_COLUMN_PATTERN_COUNT] if require_boost_column else EFFICIENCY_TABLE_PATTERNS
    )
    return any(re.search(pattern, content) for pattern in patterns)


def is_table_header(line: str, *, include_separator: bool = False) -> bool:
    if "|" not in line:
        return False
    keywords: tuple[str, ...] = ("阶段", "总计", "指标", "Metric")
    if include_separator:
        keywords += ("---",)
    return any(keyword in line for keyword in keywords)


def is_data_row(line: str) -> bool:
    return line.strip().startswith("|")


def is_separator_row(line: str) -> bool:
    return "---" in line


def extract_table_rows(
    content: str,
    *,
    include_header: bool = False,
    skip_separators: bool = False,
    separator_starts_table: bool = False,
) -> list[str]:
    rows: list[str] = []
    in_table = False
    for line in content.split("\n"):
        if not in_table:
            if not is_table_header(line, include_separator=separator_starts_table):
                continue
            in_table = True
            if not include_header:
                continue
        if not is_data_row(line):
            break
        if skip_separators and is_separator_row(line):
            continue
        rows.append(line)
    return rows


def extract_insights_section(content: str, *, stop_at_next_section: bool = False) -> str:
    for header in INSIGHT_HEADERS:
        parts = content.split(header)
        if len(parts) >= 2:
            if stop_at_next_section:
                return re.split(r"\n## ", parts[1])[0]
            return parts[1]
    return ""


def extract_numbered_insights(insights_text: str) -> list[str]:
    numbered = re.findall(r"^\d+\.\s+\*\*(洞察\s*\d+)?\*?\*\s*:?\s*(.+)$", insights_text, re.MULTILINE)
    if numbered:
        return [item[-1] for item in numbered]

    numbered = re.findall(r"^\d+\.\s+(.+)$", insights_text, re.MULTILINE)
    if numbered:
        return numbered

    numbered = re.findall(r"^[-*]\s+(.+)$", insights_text, re.MULTILINE)
    if numbered:
        return numbered

    return re.findall(r"^###\s+\d+\.\s+(.+)$", insights_text, re.MULTILINE)


def parse_efficiency_values(
    traditional: str,
    ai: str,
    boost: str,
    *,
    support_minutes: bool = True,
) -> tuple[float, float, float] | None:
    t_match = re.search(r"([\d.]+)\s*小时", traditional)
    a_match_hours = re.search(r"([\d.]+)\s*小时", ai)
    a_match_minutes = re.search(r"([\d.]+)\s*分钟", ai) if support_minutes else None
    b_match = re.search(r"([\d.]+)x", boost)

    if not (t_match and b_match and (a_match_hours or a_match_minutes)):
        return None

    t_hours = float(t_match.group(1))
    if a_match_hours:
        a_hours = float(a_match_hours.group(1))
    else:
        assert a_match_minutes is not None
        a_hours = float(a_match_minutes.group(1)) / 60
    return (t_hours, a_hours, float(b_match.group(1)))

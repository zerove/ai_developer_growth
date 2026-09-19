"""noqa 抑制处理模块。

处理 # noqa 注释的解析和问题过滤。
"""

from __future__ import annotations

import re

from tools.scripts.rules_engine.models import Issue


def parse_noqa_lines(content: str) -> dict[int, set[str]]:
    """解析 noqa 行，返回 行号 -> 忽略规则集合。

    支持格式：
    - # noqa: RULE1,RULE2
    - # noqa: RULE1, RULE2
    - # noqa (忽略所有)
    """
    result: dict[int, set[str]] = {}
    lines = content.splitlines()
    for i, line in enumerate(lines, 1):
        # 匹配 # noqa: RULE1,RULE2 或 # noqa
        match = re.search(r"#\s*noqa\s*(?::\s*([^\n]+))?", line)
        if match:
            rules_str = match.group(1)
            if rules_str:
                rules = {r.strip() for r in rules_str.split(",") if r.strip()}
                if rules:
                    result[i] = rules
            else:
                # # noqa (无冒号) - 忽略该行所有规则
                result[i] = {"*"}
    return result


def filter_suppressed_issues(filepath: str, issues: list[Issue], lines: list[str]) -> list[Issue]:
    """过滤被 # noqa 抑制的问题。

    Args:
        filepath: 文件路径（用于日志）
        issues: Issue 列表
        lines: 源代码行列表

    Returns:
        过滤后的 Issue 列表
    """
    if not issues:
        return issues

    noqa_map = parse_noqa_lines("\n".join(lines))

    if not noqa_map:
        return issues

    filtered: list[Issue] = []
    for issue in issues:
        line_no = issue.line
        if line_no in noqa_map:
            ignored_rules = noqa_map[line_no]
            if "*" in ignored_rules or issue.rule_id in ignored_rules:
                # 被抑制，跳过
                continue
        filtered.append(issue)
    return filtered


def is_issue_suppressed(issue: Issue, noqa_map: dict[int, set[str]]) -> bool:
    """判断单个问题是否被抑制。"""
    line_no = issue.line
    if line_no in noqa_map:
        ignored_rules = noqa_map[line_no]
        if "*" in ignored_rules or issue.rule_id in ignored_rules:
            return True
    return False


def _load_ignored_rules(content: str) -> set[str]:
    """从内容中加载全局忽略规则（如 # adg-ignore: RULE1,RULE2）。"""
    import re

    ignored = set()
    # 查找 # adg-ignore: RULE1,RULE2
    for match in re.finditer(r"#\s*adg-ignore\s*:\s*([^\n]+)", content):
        rules_str = match.group(1).strip()
        for rule in rules_str.split(","):
            ignored.add(rule.strip())
    return ignored


def filter_global_ignored(issues: list[Issue], ignored_rules: set[str]) -> list[Issue]:
    """过滤全局忽略规则。"""
    if not ignored_rules:
        return issues
    return [i for i in issues if i.rule_id not in ignored_rules]

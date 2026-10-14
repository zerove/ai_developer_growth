"""Noqa / suppression helpers for the rules engine."""

from __future__ import annotations

import re
from pathlib import Path

from .models import Issue


def _filter_suppressed_issues(
    filepath: Path,
    issues: list[Issue],
    lines: list[str],
) -> list[Issue]:
    """过滤被豁免的违规 (V2.21 P5-38 拆分: 抽 _parse_noqa_lines + _is_issue_suppressed).

    支持两种机制:
    1. 行级 noqa 注释: # noqa (全豁免) 或 # noqa: rule-id[,rule-id]
    2. 文件级豁免: .jcode/ignored-rules.toml 的 [[ignored_files]] 段
    """
    if not issues:
        return issues

    noqa_by_line = _parse_noqa_lines(lines)
    file_rules = _load_ignored_rules(filepath)

    result: list[Issue] = []
    for issue in issues:
        if not _is_issue_suppressed(issue, noqa_by_line, file_rules):
            result.append(issue)
    return result


def _parse_noqa_lines(lines: list[str]) -> dict[int, set[str] | None]:
    """解析行级 noqa 注释 (模块级 helper).

    Args:
        lines: 源码行列表

    Returns:
        {line_no: None | set(rule_ids)} 索引
    """
    noqa_by_line: dict[int, set[str] | None] = {}
    for idx, line in enumerate(lines, start=1):
        # \b 是必需的: 否则 `# noqas are bad` 这类普通注释因 `noqa` 只是前缀而被
        # 当成裸 noqa, 导致整行问题被错误抑制。
        m = re.search(r"#\s*noqa\b(?::\s*([A-Za-z0-9_,\-]+))?", line)
        if m:
            rules_str = m.group(1)
            noqa_by_line[idx] = None if not rules_str else {r.strip() for r in rules_str.split(",") if r.strip()}
    return noqa_by_line


def _is_issue_suppressed(issue: Issue, noqa_by_line: dict[int, set[str] | None], file_rules: set[str]) -> bool:
    """判断 issue 是否被豁免 (行级 noqa + 文件级 ignored-rules, 模块级 helper).

    检查违规行 + 前一行 (部分检测器把多行语句的违规归到语句尾/下一行).

    Args:
        issue: 单个 issue
        noqa_by_line: 行级 noqa 索引
        file_rules: 文件级豁免规则集

    Returns:
        是否被豁免
    """
    candidate_lines = (issue.line, issue.line - 1)
    for ln in candidate_lines:
        line_noqa = noqa_by_line.get(ln)
        if line_noqa is None and ln in noqa_by_line:
            return True  # 裸 noqa: 全豁免
        if line_noqa and issue.rule_id in line_noqa:
            return True
    if file_rules and issue.rule_id in file_rules:
        return True
    return False


def _load_ignored_rules(filepath: Path) -> set[str]:
    """从 .jcode/ignored-rules.toml 加载针对该文件的规则豁免列表。"""
    try:
        import tomllib
    except ImportError:
        return set()

    config_path = Path(".jcode/ignored-rules.toml")
    if not config_path.exists():
        return set()

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    path_str = str(filepath)
    ignored: set[str] = set()
    for entry in data.get("ignored_files", []):
        pattern = str(entry.get("file", ""))
        if pattern and pattern in path_str:
            ignored.update(str(r) for r in entry.get("rules", []))
    return ignored

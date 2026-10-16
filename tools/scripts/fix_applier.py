"""Auto-fix applier for language rules validation.

Provides regex-based auto-fix functionality for code issues.
Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import re
import sys
from pathlib import Path
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts.rules_engine.regex_cache import guard_pattern  # noqa: E402
from tools.scripts.rules_engine.validators.models import FixResult, Issue  # noqa: E402


def _read_file_content(filepath: Path) -> tuple[str, bool]:
    """Read file content, return (content, success)."""
    try:
        return filepath.read_text(encoding="utf-8"), True
    except (OSError, UnicodeDecodeError):
        return "", False


def _parse_regex_replacement(replacement: str, original_line: str) -> str | None:
    """Parse and apply sed-style regex replacement. Returns new line or None on error."""
    if not replacement.startswith("s/") or replacement.count("/") < 3:
        return None

    parts = replacement.split("/")
    pattern = parts[1]
    new_text = parts[2]
    flags = parts[3] if len(parts) > 3 else ""
    re_flags = re.IGNORECASE if "i" in flags else 0

    # pattern 来自 issue.fix_replacement (规则配置), 而 original_line 是被检查的
    # 源码行 —— 两者在 PR 场景都由外部贡献者控制, 直接 re.sub 可被 (a|aa)+$ 挂死。
    if guard_pattern(pattern, "fix_applier"):
        return None

    try:
        return re.sub(pattern, new_text, original_line, flags=re_flags)
    except re.error:
        return None


def _apply_literal_replacement(original_line: str, replacement: str, message: str) -> str:
    """Apply literal string replacement.

    ADR-072 配套修复：原实现直接 ``original_line.replace(match_text, ...)``，
    而 ``match_text`` 取自 ``message`` 最后一个冒号之后的文本。若 ``message``
    **不含冒号**，``match_text`` 就是空字符串，而 ``str.replace("", x)`` 会把
    ``x`` 插到**行首** —— 静默改坏一行仍然合法的代码。

        实测：original='x = "TODO"', message='probe marker'（无冒号）
              -> 'DONEx = "TODO"'   # 语义已变，语法却仍然合法，ADR-072 的
                                    # ast.parse 自检抓不到

    这是"写盘前语法自检"无法覆盖的一类损坏：语法合法但语义已错。故在此
    显式拒绝空 ``match_text``，交由调用方按"无可应用修复"处理。
    """
    match_text = message.split(":")[-1].strip() if ":" in message else ""
    if not match_text:
        # 无法从 message 推断出待替换文本 —— 宁可不改，也不在行首凭空插入。
        return original_line
    return original_line.replace(match_text, replacement, 1)


def _apply_fix_to_line(issue: Issue, original_line: str) -> str | None:
    """Apply a single fix to a line. Returns new line or None if no change/error."""
    if not issue.fix_replacement:
        return None

    replacement = issue.fix_replacement

    # Try regex replacement first
    if replacement.startswith("s/"):
        new_line = _parse_regex_replacement(replacement, original_line)
        if new_line is not None:
            return new_line
        return None  # Regex malformed, don't fallback

    # Literal replacement
    return _apply_literal_replacement(original_line, replacement, issue.message)


def _create_fix_result(filepath: Path, issue: Issue, original_line: str, new_line: str) -> FixResult:
    """Create a FixResult from fix details."""
    return FixResult(
        file=str(filepath),
        rule_id=issue.rule_id,
        line=issue.line,
        original=original_line.rstrip(),
        fixed=new_line.rstrip(),
        description=issue.fix_hint or f"Auto-fixed: {issue.rule_id}",
    )


def _process_issues(
    lines: list[str], issues: list[Issue], filepath: Path, dry_run: bool
) -> tuple[list[FixResult], list[str], bool]:
    """Process all issues against lines. Returns (fixes, modified_lines, modified).

    V2.20 P4-59 拆分: 抽 _should_skip_issue 收口守卫 (无 fix / line 越界),
    _apply_line_fix 收口 dry_run 守卫 + line 更新,
    主函数仅 for + 委托.
    """
    fixes: list[FixResult] = []
    modified_lines = lines[:]
    modified = False

    for issue in issues:
        if _should_skip_issue(issue, modified_lines):
            continue

        line_idx = issue.line - 1
        original_line = modified_lines[line_idx]

        new_line = _apply_fix_to_line(issue, original_line)
        if new_line is None or new_line == original_line:
            continue

        fixes.append(_create_fix_result(filepath, issue, original_line, new_line))

        if not dry_run:
            modified_lines[line_idx] = new_line
            modified = True

    return fixes, modified_lines, modified


def _should_skip_issue(issue: Issue, lines: list[str]) -> bool:
    """判断 issue 是否应跳过 (无 fix_replacement 或 line 越界, 模块级 helper).

    Args:
        issue: 待处理 issue
        lines: 当前行列表

    Returns:
        True if 应跳过
    """
    return bool(not issue.fix_replacement or issue.line < 1 or issue.line > len(lines))


def apply_fixes(filepath: Path, issues: list[Any], dry_run: bool = False) -> list[Any]:
    """Apply auto-fixes to a file based on issues with fix_replacement.

    ADR-072: 写盘前必须通过语法自检。本模块是仓库里**第四条**独立的
    代码改写写盘路径 (前三条: ``ast_fixer`` / ``auto_fix`` / ``FixEngine``),
    与它们同源于“正则或字符串改写代码”这一手法, 因而需要同一道兜底。

    实测 (本轮取证, 非推断): ``_apply_literal_replacement`` 取
    ``message`` 最后一个冒号后的文本做替换, 一旦 ``fix_replacement``
    本身是坏的就会把文件改坏, 而本函数仍如实报告“已修复”:

        输入: x = 1 / y = 2   替换 "2" -> "(2"
        磁盘: x = 1 / y = (2  -> SyntaxError: '(' was never closed
        返回: 1 个 FixResult (即**声称修复成功**)

    本路径当前**有生产调用方**: ``tools/scripts/rules_engine/validators/cli.py``
    的 ``_apply_auto_fix`` (CLI ``validate_language_rules.py --fix``), 以及
    ``tools/scripts/validate_language_rules.py`` 的同名包装。
    早先版本记为"无生产调用方"是**错的**, 已于收口复核更正 —— 见下方
    「收口复核更正」。

    Args:
        filepath: File to fix
        issues: Issues to fix (only those with fix_replacement set)
        dry_run: If True, report what would change without writing

    Returns:
        List of FixResult describing each change
    """
    content, success = _read_file_content(filepath)
    if not success:
        return []

    lines = content.splitlines(keepends=True)
    fixes, modified_lines, modified = _process_issues(lines, issues, filepath, dry_run)

    if modified and not dry_run:
        candidate = "".join(modified_lines)
        # 自检实现复用 auto_fix._verify_syntax, 不另写一份 —— 与 ADR-072
        # 对 auto_fix 的约束一致。Python 走 ast.parse 而非 tree-sitter:
        # tree-sitter 看不见 IndentationError, 等于没检查 (见 ADR-070)。
        from tools.scripts.rules_engine.auto_fix import _verify_syntax, detect_language

        checked, violation, error = _verify_syntax(candidate, detect_language(filepath))
        if checked and violation:
            # 一个字节都不写, 且如实回报“什么都没改成”。
            return [
                FixResult(
                    file=str(filepath),
                    rule_id="syntax-check-rejected",
                    line=0,
                    original="",
                    # 必须用 MANUAL FIX REQUIRED 哨兵: 汇总层以该字符串
                    # 判定“是否已自动修复”, 留空会被计入 auto-fixed,
                    # 正是 ADR-072 要消灭的那句假绿灯。
                    fixed="[MANUAL FIX REQUIRED]",
                    description=f"拒绝写盘: 修复结果无法解析 (ADR-072): {error}",
                )
            ]

        filepath.write_text(candidate, encoding="utf-8")

    return fixes

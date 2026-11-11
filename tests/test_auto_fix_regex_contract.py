"""I-01 契约收敛: ``RegexFixProvider.generate_fixes`` 的 pattern 解析与替换范围。

## 要锁住的缺陷

旧实现把 ``issue.rule_id`` 当**正则**用 —— rule_id 是标识符, 不是 pattern:

- "检测用的正则"与"修复用的正则"根本不是一回事, 修复可能落到行内与问题
  无关的位置;
- ``re.sub`` 会把整行**所有**匹配一并改写, 波及未被上报的那几处;
- 零长匹配 (如 ``x*``) 会在行首凭空插入内容。

## 收敛后的契约

1. pattern 优先取注册规则自身的 pattern (与文件级 ``apply_rules`` 同源);
2. 规则 pattern 按 ``issue.column`` 精确锚定到上报的那一处命中;
3. 只替换这一处匹配 —— 不再对整行所有匹配做替换;
4. 零长匹配不替换;
5. 未注册该 rule_id 时回退到历史行为 (rule_id 当 pattern), 保持向后兼容。
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts.auto_fix import FixSafetyLevel, RegexFixProvider
from tools.scripts.rules_engine.models import Issue

__all__ = [
    "TestAuthoritativePattern",
    "TestLegacyFallback",
    "TestReplacementSafety",
]


def _issue(rule_id: str, line: int = 1, column: int = 1, replacement: str = "safe_eval(") -> Issue:
    return Issue(
        rule_id=rule_id,
        severity="error",
        category="security",
        file="a.py",
        line=line,
        column=column,
        message="m",
        fix_replacement=replacement,
    )


def _provider(rules: dict[str, dict[str, Any]] | None = None) -> RegexFixProvider:
    return RegexFixProvider("regex", FixSafetyLevel.SAFE, rules=rules)


class TestAuthoritativePattern:
    """注册规则的 pattern 为权威来源, 并按 issue.column 锚定。"""

    RULES = {"py-eval": {"pattern": r"eval\(", "replacement": "safe_eval(", "language": "python"}}

    def test_rule_pattern_is_used_instead_of_rule_id(self, tmp_path: Path) -> None:
        target = tmp_path / "a.py"
        target.write_text("x = eval(expr)\n", encoding="utf-8")
        provider = _provider(self.RULES)

        actions = provider.generate_fixes(_issue("py-eval", column=5), str(target))

        assert actions, "注册规则的 pattern 命中时应产生 FixAction"
        assert actions[0].replacement == "x = safe_eval(expr)"

    def test_column_mismatch_is_skipped(self, tmp_path: Path) -> None:
        """上报列与规则 pattern 的命中位置不符 → 不修复, 避免改错位置。"""
        target = tmp_path / "a.py"
        target.write_text("x = eval(expr)\n", encoding="utf-8")
        provider = _provider(self.RULES)

        actions = provider.generate_fixes(_issue("py-eval", column=1), str(target))

        assert actions == [], "列信息与 pattern 命中位置不一致时不得产生 FixAction"

    def test_only_reported_occurrence_is_replaced(self, tmp_path: Path) -> None:
        """同一行多处命中时只改上报的那一处。"""
        target = tmp_path / "a.py"
        target.write_text("eval(a) + eval(b)\n", encoding="utf-8")
        provider = _provider(self.RULES)

        actions = provider.generate_fixes(_issue("py-eval", column=11), str(target))

        assert actions, "第二处命中应被修复"
        assert actions[0].replacement == "eval(a) + safe_eval(b)"


class TestLegacyFallback:
    """未注册规则时回退到历史行为 (rule_id 当 pattern), 保持兼容。"""

    def test_legacy_rule_id_as_pattern_still_works(self, tmp_path: Path) -> None:
        target = tmp_path / "a.py"
        target.write_text("x = eval(expr)\n", encoding="utf-8")
        provider = _provider()

        actions = provider.generate_fixes(_issue(r"eval\(", column=1), str(target))

        assert actions, "回退路径仍须能修复"
        assert actions[0].replacement == "x = safe_eval(expr)"

    def test_legacy_path_does_not_anchor_by_column(self, tmp_path: Path) -> None:
        """回退路径没有可验证的列对应关系 → 取首个匹配, 不因列不符而放弃。"""
        target = tmp_path / "a.py"
        target.write_text("x = eval(expr)\n", encoding="utf-8")
        provider = _provider()

        actions = provider.generate_fixes(_issue(r"eval\(", column=99), str(target))

        assert actions, "回退路径不应因列不符而放弃修复"


class TestReplacementSafety:
    """替换安全性: 零长匹配不替换, 非法模板不抛异常。"""

    def test_zero_length_match_is_skipped(self, tmp_path: Path) -> None:
        target = tmp_path / "a.py"
        target.write_text("value = 1\n", encoding="utf-8")
        provider = _provider({"py-empty": {"pattern": "x*", "replacement": "BUG"}})

        actions = provider.generate_fixes(_issue("py-empty", column=1), str(target))

        assert actions == [], "零长匹配不得产生 FixAction (否则会在行首凭空插入)"

    def test_invalid_replacement_template_is_skipped(self, tmp_path: Path) -> None:
        target = tmp_path / "a.py"
        target.write_text("x = eval(expr)\n", encoding="utf-8")
        provider = _provider({"py-eval": {"pattern": r"eval\(", "replacement": "safe_eval(", "language": "python"}})

        actions = provider.generate_fixes(_issue("py-eval", column=5, replacement=r"\9"), str(target))

        assert actions == [], "非法替换模板应被安全跳过"

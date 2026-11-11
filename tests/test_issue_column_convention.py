"""D-03 契约: ``Issue.column`` 统一为 **1-based** 列号。

## 背景

仓库里曾同时存在两套列号语义:

- 1-based: ``match.start() + 1``（anti-pattern 行级规则、ruff、tree-sitter、
  SARIF ``startColumn``）
- 0-based: ``match.start()``（naming 规则、validators pipeline、框架侧多行规则）

后果:

- 同一份报告里, 不同检查器给出的列号可能指向不同字符;
- SARIF 导出（``startColumn`` 规范为 1-based）会把 0-based 列号原样写出,
  定位偏移一列;
- ADR-081 的"按上报列锚定修复"无法成立 —— 锚点与命中位置差 1。

## 契约

- ``column`` 是 1-based 列号: 1 表示行首第一个字符;
- ``column == 0`` 表示"列未知"（不是行首）;
- 所有产出 ``Issue`` 的检查器必须遵守。
"""

from __future__ import annotations

from pathlib import Path

__all__ = [
    "TestAntiPatternColumns",
    "TestNamingColumns",
    "TestSarifColumns",
    "TestValidatorPipelineColumns",
]


class TestAntiPatternColumns:
    """anti_pattern_checker: 行级与多行规则都必须是 1-based。"""

    def test_line_pattern_column_is_one_based(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        target = tmp_path / "a.py"
        target.write_text("value = eval(x)\n", encoding="utf-8")
        rules = {
            "anti_patterns": [
                {"id": "t-eval", "pattern": r"eval\(", "message": "m", "severity": "error"},
            ]
        }

        issues = check_anti_patterns(target, "python", rules)

        assert issues, "应命中一条规则"
        assert issues[0].column == 9, "eval( 起始于第 9 列（1-based）"

    def test_line_pattern_at_line_start_column_is_one(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        target = tmp_path / "a.py"
        target.write_text("eval(x)\n", encoding="utf-8")
        rules = {
            "anti_patterns": [
                {"id": "t-eval", "pattern": r"eval\(", "message": "m", "severity": "error"},
            ]
        }

        issues = check_anti_patterns(target, "python", rules)

        assert issues and issues[0].column == 1, "行首命中的列号必须是 1"

    def test_multiline_pattern_column_is_one_based(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        target = tmp_path / "a.py"
        target.write_text("x = 1\ny = 2\neval(z)\n", encoding="utf-8")
        rules = {
            "anti_patterns": [
                {
                    "id": "t-multi",
                    "pattern": r"y = 2\neval\(",
                    "message": "m",
                    "severity": "error",
                    "multiline": True,
                },
            ]
        }

        issues = check_anti_patterns(target, "python", rules)

        assert issues, "多行规则应命中"
        assert issues[0].line == 2
        assert issues[0].column == 1, "多行命中的起始列必须是 1-based"


class TestNamingColumns:
    """naming_checker: 1-based。"""

    def test_naming_column_is_one_based(self) -> None:
        from tools.scripts.rules_engine.naming_checker import check_naming_conventions

        lines = ["    BadName = 1\n"]
        rules = {"naming": {"function": {"pattern": r"[A-Z][a-z]+", "message": "m"}}}

        issues = check_naming_conventions(lines, rules, "a.py", "python")

        assert issues, "应命中命名规则"
        assert issues[0].column == 5, "缩进 4 空格后命中, 列号应为 5（1-based）"


class TestValidatorPipelineColumns:
    """validators.pipeline: 1-based。"""

    def test_pipeline_column_is_one_based(self) -> None:
        from tools.scripts.rules_engine.validators.pipeline import check_anti_patterns

        lines = ["value = eval(x)\n"]
        rules = {
            "anti_patterns": [
                {"id": "t-eval", "pattern": r"eval\(", "message": "m", "severity": "error"},
            ]
        }

        issues = check_anti_patterns(lines, rules, "a.py")

        assert issues, "应命中一条规则"
        assert issues[0].column == 9, "eval( 起始于第 9 列（1-based）"


class TestSarifColumns:
    """SARIF 导出直接使用 Issue.column（规范要求 1-based）。"""

    def test_sarif_start_column_matches_issue_column(self) -> None:
        import json

        from tools.scripts.rules_engine.models import CheckResult, Issue
        from tools.scripts.rules_engine.sarif_exporter import to_sarif

        issue = Issue(
            rule_id="t-eval",
            severity="error",
            category="security",
            file="a.py",
            line=1,
            column=9,
            message="m",
        )
        payload = json.loads(to_sarif([CheckResult(file="a.py", issues=[issue])]))
        results = payload["runs"][0]["results"]
        assert results[0]["locations"][0]["physicalLocation"]["region"]["startColumn"] == 9

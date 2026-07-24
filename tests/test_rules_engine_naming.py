"""Tests for rules_engine/naming_checker.py (38% → target 85%)."""

from __future__ import annotations

from tools.scripts.rules_engine.naming_checker import check_naming_conventions


class TestCheckNamingConventions:
    """Tests for check_naming_conventions()."""

    def test_no_rules_returns_empty(self) -> None:
        result = check_naming_conventions(["x = 1"], {}, "test.py", "python")
        assert result == []

    def test_non_dict_convention_skipped(self) -> None:
        rules = {"naming": {"bad": "not-a-dict"}}
        result = check_naming_conventions(["x = 1"], rules, "test.py", "python")
        assert result == []

    def test_no_pattern_skipped(self) -> None:
        rules = {"naming": {"func": {"severity": "warning", "message": "msg"}}}
        result = check_naming_conventions(["x = 1"], rules, "test.py", "python")
        assert result == []

    def test_matching_pattern(self) -> None:
        rules = {
            "naming": {
                "no-camel": {
                    "pattern": r"[a-z][A-Z]",
                    "severity": "warning",
                    "message": "No camelCase",
                    "fix_hint": "Use snake_case",
                }
            }
        }
        lines = ["myVar = 1"]
        result = check_naming_conventions(lines, rules, "test.py", "python")
        assert len(result) == 1
        assert result[0].rule_id == "naming-no-camel"
        assert result[0].severity == "warning"
        assert result[0].fix_hint == "Use snake_case"

    def test_comment_lines_skipped(self) -> None:
        rules = {
            "naming": {
                "no-camel": {"pattern": r"[a-z][A-Z]", "severity": "warning", "message": "msg"}
            }
        }
        lines = ["# myVar = 1", "// myVar = 1"]
        result = check_naming_conventions(lines, rules, "test.py", "python")
        assert result == []

    def test_multiple_matches(self) -> None:
        rules = {
            "naming": {
                "no-camel": {"pattern": r"[a-z][A-Z]", "severity": "error", "message": "msg"}
            }
        }
        lines = ["myVar = 1", "yourVar = 2"]
        result = check_naming_conventions(lines, rules, "f.py", "python")
        assert len(result) == 2
        assert result[0].line == 1
        assert result[1].line == 2

    def test_default_severity(self) -> None:
        rules = {"naming": {"test": {"pattern": r"TODO", "message": "found TODO"}}}
        result = check_naming_conventions(["x = TODO"], rules, "f.py", "python")
        assert len(result) == 1
        assert result[0].severity == "warning"  # default

    def test_empty_lines(self) -> None:
        rules = {
            "naming": {
                "no-camel": {"pattern": r"[a-z][A-Z]", "severity": "warning", "message": "msg"}
            }
        }
        result = check_naming_conventions([], rules, "f.py", "python")
        assert result == []

    def test_fix_hint_empty(self) -> None:
        rules = {"naming": {"r": {"pattern": r"FIXME", "severity": "info", "message": "found"}}}
        result = check_naming_conventions(["x = FIXME"], rules, "f.py", "python")
        assert result[0].fix_hint == ""

    def test_category_is_naming(self) -> None:
        rules = {"naming": {"r": {"pattern": r"X", "severity": "info", "message": "m"}}}
        result = check_naming_conventions(["X"], rules, "f.py", "python")
        assert result[0].category == "naming"

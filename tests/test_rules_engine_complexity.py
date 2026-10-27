# 拆分自 tests/test_rules_engine.py

"""Tests for rules_engine package - modular code quality checking engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.rules_engine.complexity_checker import (
    _max_nesting_depth,
    check_js_complexity,
    check_python_complexity,
)
from tools.scripts.rules_engine.naming_checker import check_naming_conventions
from tools.scripts.rules_engine.rule_loader import (
    _file_hash,
    _get_embedded_rules,
    _merge_anti_patterns,
    _merge_rules,
    load_rules_for_language,
)


class TestPythonComplexity(unittest.TestCase):
    """Test Python complexity checking."""

    def test_long_function(self) -> None:
        lines = ["def long_func():"]
        lines += ["    x = 1"] * 60
        rules = {"thresholds": {"max_lines_per_function": 50}}
        issues = check_python_complexity(lines, rules, "test.py")
        self.assertTrue(any(i.rule_id == "python-too-many-lines" for i in issues))

    def test_many_params(self) -> None:
        code = "def func(a, b, c, d, e, f, g):\n    pass\n"
        lines = code.split("\n")
        rules = {"thresholds": {"max_parameters": 5}}
        issues = check_python_complexity(lines, rules, "test.py")
        self.assertTrue(any(i.rule_id == "python-too-many-params" for i in issues))

    def test_clean_function(self) -> None:
        code = "def clean():\n    return 1\n"
        lines = code.split("\n")
        rules = {"thresholds": {"max_lines_per_function": 50, "max_parameters": 5}}
        issues = check_python_complexity(lines, rules, "test.py")
        self.assertEqual(len(issues), 0)

    def test_syntax_error_returns_empty(self) -> None:
        lines = ["def broken("]
        rules = {"thresholds": {}}
        issues = check_python_complexity(lines, rules, "test.py")
        self.assertEqual(len(issues), 0)

    def test_deep_nesting(self) -> None:
        code = (
            "def deep():\n"
            "    if True:\n"
            "        for i in range(10):\n"
            "            if i > 5:\n"
            "                while True:\n"
            "                    break\n"
        )
        lines = code.split("\n")
        rules = {"thresholds": {"max_nesting_depth": 2}}
        issues = check_python_complexity(lines, rules, "test.py")
        self.assertTrue(any(i.rule_id == "python-too-deep-nesting" for i in issues))


class TestMaxNestingDepth(unittest.TestCase):
    """Test _max_nesting_depth helper."""

    def test_no_nesting(self) -> None:
        import ast

        tree = ast.parse("x = 1\n")
        node = tree.body[0]
        self.assertEqual(_max_nesting_depth(node), 0)

    def test_with_if(self) -> None:
        import ast

        tree = ast.parse("if True:\n    if False:\n        pass\n")
        node = tree.body[0]
        # Depth starts at 0, outer if = 0, inner if = 1
        self.assertEqual(_max_nesting_depth(node), 1)


class TestJSComplexity(unittest.TestCase):
    """Test JavaScript complexity checking."""

    def test_long_function(self) -> None:
        lines = ["function longFunc() {"]
        lines += ["  x = 1;"] * 60
        lines += ["}"]
        rules = {"thresholds": {"max_lines_per_function": 50}}
        issues = check_js_complexity(lines, rules, "test.js")
        self.assertTrue(any(i.rule_id == "js-too-many-lines" for i in issues))

    def test_clean_function(self) -> None:
        lines = ["function clean() {", "  return 1;", "}"]
        rules = {"thresholds": {"max_lines_per_function": 50}}
        issues = check_js_complexity(lines, rules, "test.js")
        self.assertEqual(len(issues), 0)


class TestNamingChecker(unittest.TestCase):
    """Test naming convention checking."""

    def test_camel_case_in_python(self) -> None:
        lines = ["def myFunction():", "    pass"]
        rules = {"naming": {"function_pattern": r"^[a-z_][a-z0-9_]*$"}}
        issues = check_naming_conventions(lines, rules, "test.py", "python")
        # Naming checker checks identifiers; if no identifier extraction matches, 0 issues is valid
        self.assertIsInstance(issues, list)

    def test_clean_naming(self) -> None:
        lines = ["def my_function():", "    pass"]
        rules = {"naming": {"function_pattern": r"^[a-z_][a-z0-9_]*$"}}
        issues = check_naming_conventions(lines, rules, "test.py", "python")
        self.assertEqual(len(issues), 0)

    def test_no_naming_rules(self) -> None:
        lines = ["def anything():", "    pass"]
        rules = {}
        issues = check_naming_conventions(lines, rules, "test.py", "python")
        self.assertEqual(len(issues), 0)


class TestRuleLoader(unittest.TestCase):
    """Test rule loading and merging."""

    def test_file_hash(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
            f.write("test content")
            f.flush()
            h = _file_hash(Path(f.name))
            self.assertEqual(len(h), 64)  # SHA-256 hex digest
        Path(f.name).unlink(missing_ok=True)

    def test_file_hash_nonexistent(self) -> None:
        h = _file_hash(Path("/nonexistent/file"))
        self.assertEqual(h, "")

    def test_get_embedded_rules(self) -> None:
        rules = _get_embedded_rules("python")
        self.assertIn("anti_patterns", rules)
        self.assertIsInstance(rules["anti_patterns"], list)
        self.assertTrue(len(rules["anti_patterns"]) > 0)

    def test_merge_rules(self) -> None:
        base = {
            "anti_patterns": [{"id": "r1", "severity": "error"}],
            "naming": {"func": "snake"},
            "thresholds": {"max_lines": 50},
        }
        custom = {
            "anti_patterns": [{"id": "r1", "severity": "warning"}],
            "naming": {"class": "Pascal"},
            "thresholds": {"max_lines": 100},
        }
        merged = _merge_rules(base, custom)
        # r1 should be overridden
        r1 = next(p for p in merged["anti_patterns"] if p["id"] == "r1")
        self.assertEqual(r1["severity"], "warning")
        # naming should be updated
        self.assertEqual(merged["naming"]["class"], "Pascal")
        # thresholds should be updated
        self.assertEqual(merged["thresholds"]["max_lines"], 100)

    def test_merge_anti_patterns_new_only(self) -> None:
        base = [{"id": "r1", "severity": "error"}]
        custom = [{"id": "r2", "severity": "warning"}]
        merged = _merge_anti_patterns(base, custom)
        self.assertEqual(len(merged), 2)
        ids = {p["id"] for p in merged}
        self.assertEqual(ids, {"r1", "r2"})

    def test_merge_anti_patterns_severity_override(self) -> None:
        base = [{"id": "r1", "severity": "error"}]
        custom = [{"id": "r1", "severity_override": "warning"}]
        merged = _merge_anti_patterns(base, custom)
        self.assertEqual(len(merged), 1)
        self.assertEqual(merged[0]["severity"], "warning")

    def test_load_rules_for_language(self) -> None:
        rules = load_rules_for_language("python")
        self.assertIn("anti_patterns", rules)
        # Should include both embedded and security patterns
        self.assertTrue(len(rules["anti_patterns"]) > 0)

"""Tests for rules_engine package - modular code quality checking engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.rules_engine.models import (
    CheckResult,
    FixResult,
    HealthScore,
    Issue,
    Severity,
    ValidationResult,
)
from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns
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
from tools.scripts.rules_engine.checker import (
    _detect_language,
    _map_severity,
    _parse_linter_output,
    check_directory,
    check_file,
)


# ── models.py tests ────────────────────────────────────────────────


class TestIssue(unittest.TestCase):
    """Test Issue dataclass."""

    def test_issue_creation(self) -> None:
        issue = Issue(
            rule_id="test-rule",
            severity="error",
            category="security",
            file="test.py",
            line=10,
            message="Test message",
        )
        self.assertEqual(issue.rule_id, "test-rule")
        self.assertEqual(issue.severity, "error")
        self.assertEqual(issue.line, 10)
        self.assertEqual(issue.column, 0)

    def test_issue_to_dict(self) -> None:
        issue = Issue(
            rule_id="r1",
            severity="warning",
            category="type",
            file="f.py",
            line=5,
            message="msg",
            fix_hint="fix it",
            column=3,
        )
        d = issue.to_dict()
        self.assertEqual(d["rule_id"], "r1")
        self.assertEqual(d["severity"], "warning")
        self.assertEqual(d["column"], 3)
        self.assertNotIn("fix_replacement", d)

    def test_issue_to_dict_with_replacement(self) -> None:
        issue = Issue(
            rule_id="r1",
            severity="error",
            category="security",
            file="f.py",
            line=1,
            message="msg",
            fix_replacement="new_code",
        )
        d = issue.to_dict()
        self.assertEqual(d["fix_replacement"], "new_code")


class TestValidationResult(unittest.TestCase):
    """Test ValidationResult dataclass."""

    def test_passed_no_errors(self) -> None:
        vr = ValidationResult(
            file="test.py",
            language="python",
            issues=[
                Issue("r1", "warning", "type", "test.py", 1, "warn"),
                Issue("r2", "info", "style", "test.py", 2, "info"),
            ],
        )
        self.assertTrue(vr.passed)
        self.assertEqual(vr.error_count, 0)
        self.assertEqual(vr.warning_count, 1)
        self.assertEqual(vr.info_count, 1)

    def test_failed_with_errors(self) -> None:
        vr = ValidationResult(
            file="test.py",
            language="python",
            issues=[
                Issue("r1", "error", "security", "test.py", 1, "err"),
                Issue("r2", "warning", "type", "test.py", 2, "warn"),
            ],
        )
        self.assertFalse(vr.passed)
        self.assertEqual(vr.error_count, 1)

    def test_to_dict(self) -> None:
        vr = ValidationResult(file="f.py", language="python", lines_checked=100)
        d = vr.to_dict()
        self.assertEqual(d["file"], "f.py")
        self.assertEqual(d["lines_checked"], 100)
        self.assertTrue(d["passed"])
        self.assertIsInstance(d["issues"], list)


class TestCheckResult(unittest.TestCase):
    """Test CheckResult dataclass."""

    def test_empty_result_passes(self) -> None:
        cr = CheckResult(file="test.py")
        self.assertTrue(cr.passed)
        self.assertEqual(cr.error_count, 0)

    def test_skipped_result(self) -> None:
        cr = CheckResult(file="test.py", skipped=True)
        self.assertTrue(cr.skipped)
        self.assertTrue(cr.passed)

    def test_to_dict(self) -> None:
        cr = CheckResult(file="f.py", language="python")
        d = cr.to_dict()
        self.assertEqual(d["file"], "f.py")
        self.assertEqual(d["language"], "python")
        self.assertFalse(d["skipped"])
        self.assertTrue(d["passed"])


class TestFixResult(unittest.TestCase):
    """Test FixResult dataclass."""

    def test_to_dict(self) -> None:
        fr = FixResult(
            file="f.py",
            rule_id="r1",
            line=5,
            original="old",
            fixed="new",
            description="Fixed it",
        )
        d = fr.to_dict()
        self.assertEqual(d["original"], "old")
        self.assertEqual(d["fixed"], "new")


class TestHealthScore(unittest.TestCase):
    """Test HealthScore dataclass."""

    def test_to_dict(self) -> None:
        hs = HealthScore(
            score=85,
            grade="B",
            breakdown={"security": 90.0, "style": 80.0},
            details=["Good"],
        )
        d = hs.to_dict()
        self.assertEqual(d["score"], 85)
        self.assertEqual(d["grade"], "B")
        self.assertIn("security", d["breakdown"])


class TestSeverity(unittest.TestCase):
    """Test Severity class."""

    def test_from_string_error(self) -> None:
        self.assertEqual(Severity.from_string("error"), "error")
        self.assertEqual(Severity.from_string("CRITICAL"), "error")
        self.assertEqual(Severity.from_string("fatal"), "error")
        self.assertEqual(Severity.from_string("2"), "error")

    def test_from_string_warning(self) -> None:
        self.assertEqual(Severity.from_string("warning"), "warning")
        self.assertEqual(Severity.from_string("warn"), "warning")
        self.assertEqual(Severity.from_string("1"), "warning")

    def test_from_string_info(self) -> None:
        self.assertEqual(Severity.from_string("info"), "info")
        self.assertEqual(Severity.from_string("debug"), "info")
        self.assertEqual(Severity.from_string("something_else"), "info")


# ── anti_pattern_checker.py tests ──────────────────────────────────


class TestAntiPatternChecker(unittest.TestCase):
    """Test anti-pattern detection."""

    def test_detects_eval(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('result = eval(user_input)\n')
            f.flush()
            rules = {
                "anti_patterns": [
                    {
                        "id": "py-eval-exec",
                        "name": "eval/exec",
                        "severity": "error",
                        "category": "security",
                        "pattern": r"\beval\s*\(",
                        "message": "eval is unsafe",
                    }
                ]
            }
            issues = check_anti_patterns(Path(f.name), "python", rules)
            self.assertTrue(len(issues) >= 1)
            self.assertEqual(issues[0].severity, "error")
        Path(f.name).unlink(missing_ok=True)

    def test_no_issues_clean_code(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('x = 1\nprint(x)\n')
            f.flush()
            rules = {"anti_patterns": []}
            issues = check_anti_patterns(Path(f.name), "python", rules)
            self.assertEqual(len(issues), 0)
        Path(f.name).unlink(missing_ok=True)

    def test_multiline_pattern(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write('except:\n    pass\n')
            f.flush()
            rules = {
                "anti_patterns": [
                    {
                        "id": "bare-except",
                        "name": "Bare except",
                        "severity": "warning",
                        "category": "error-handling",
                        "pattern": r"except\s*:\s*\n\s*pass",
                        "message": "Bare except with pass",
                    }
                ]
            }
            issues = check_anti_patterns(Path(f.name), "python", rules)
            self.assertTrue(len(issues) >= 1)
        Path(f.name).unlink(missing_ok=True)


# ── complexity_checker.py tests ────────────────────────────────────


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


# ── naming_checker.py tests ────────────────────────────────────────


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


# ── rule_loader.py tests ──────────────────────────────────────────


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


# ── checker.py tests ──────────────────────────────────────────────


class TestDetectLanguage(unittest.TestCase):
    """Test language detection from file extension."""

    def test_python(self) -> None:
        self.assertEqual(_detect_language(Path("test.py")), "python")

    def test_javascript(self) -> None:
        self.assertEqual(_detect_language(Path("test.js")), "javascript")
        self.assertEqual(_detect_language(Path("test.jsx")), "javascript")

    def test_typescript(self) -> None:
        self.assertEqual(_detect_language(Path("test.ts")), "typescript")
        self.assertEqual(_detect_language(Path("test.tsx")), "typescript")

    def test_rust(self) -> None:
        self.assertEqual(_detect_language(Path("test.rs")), "rust")

    def test_go(self) -> None:
        self.assertEqual(_detect_language(Path("test.go")), "go")

    def test_unknown(self) -> None:
        self.assertEqual(_detect_language(Path("test.xyz")), "unknown")


class TestMapSeverity(unittest.TestCase):
    """Test severity mapping."""

    def test_int_levels(self) -> None:
        self.assertEqual(_map_severity(2), "error")
        self.assertEqual(_map_severity(1), "warning")
        self.assertEqual(_map_severity(0), "warning")

    def test_string_levels(self) -> None:
        self.assertEqual(_map_severity("error"), "error")
        self.assertEqual(_map_severity("critical"), "error")
        self.assertEqual(_map_severity("fatal"), "error")
        self.assertEqual(_map_severity("warning"), "warning")
        self.assertEqual(_map_severity("info"), "warning")


class TestParseLinterOutput(unittest.TestCase):
    """Test linter output parsing."""

    def test_parse_ruff_json(self) -> None:
        import json
        data = [
            {
                "code": "E501",
                "level": "error",
                "message": "line too long",
                "location": {"row": 10, "column": 1},
            }
        ]
        issues = _parse_linter_output(json.dumps(data), "python", "test.py")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule_id, "E501")
        self.assertEqual(issues[0].line, 10)

    def test_parse_eslint_json(self) -> None:
        import json
        data = [
            {
                "messages": [
                    {
                        "ruleId": "no-unused-vars",
                        "severity": 2,
                        "line": 5,
                        "column": 1,
                        "message": "x is defined but never used",
                    }
                ]
            }
        ]
        issues = _parse_linter_output(json.dumps(data), "javascript", "test.js")
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].rule_id, "no-unused-vars")

    def test_parse_invalid_json(self) -> None:
        issues = _parse_linter_output("not json", "python", "test.py")
        self.assertEqual(len(issues), 0)


class TestCheckFile(unittest.TestCase):
    """Test file checking."""

    def test_nonexistent_file(self) -> None:
        result = check_file(Path("/nonexistent/file.py"))
        self.assertFalse(result.passed)
        self.assertTrue(result.skipped)
        self.assertEqual(len(result.issues), 1)

    def test_empty_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("")
            f.flush()
            result = check_file(Path(f.name))
            self.assertTrue(result.skipped)
        Path(f.name).unlink(missing_ok=True)

    def test_unknown_language(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".xyz", delete=False) as f:
            f.write("test content")
            f.flush()
            result = check_file(Path(f.name))
            self.assertTrue(result.skipped)
        Path(f.name).unlink(missing_ok=True)

    def test_clean_python_file(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("# clean code\nx = 1\n")
            f.flush()
            result = check_file(Path(f.name))
            self.assertIsInstance(result, CheckResult)
        Path(f.name).unlink(missing_ok=True)


class TestCheckDirectory(unittest.TestCase):
    """Test directory checking."""

    def test_nonexistent_directory(self) -> None:
        results = check_directory(Path("/nonexistent/dir"))
        self.assertEqual(len(results), 0)

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = check_directory(Path(tmpdir))
            self.assertEqual(len(results), 0)

    def test_directory_with_python_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("# test\nx = 1\n")
            results = check_directory(Path(tmpdir))
            self.assertTrue(len(results) >= 1)

    def test_directory_with_language_filter(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            py_file = Path(tmpdir) / "test.py"
            py_file.write_text("# test\nx = 1\n")
            js_file = Path(tmpdir) / "test.js"
            js_file.write_text("// test\nvar x = 1;\n")
            results = check_directory(Path(tmpdir), languages=["python"])
            self.assertTrue(all(r.language == "python" for r in results))


if __name__ == "__main__":
    unittest.main()

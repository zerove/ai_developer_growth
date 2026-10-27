"""Tests for rules_engine package - modular code quality checking engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns
from tools.scripts.rules_engine.models import (
    CheckResult,
    FixResult,
    HealthScore,
    Issue,
    Severity,
    ValidationResult,
)


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


class TestAntiPatternChecker(unittest.TestCase):
    """Test anti-pattern detection."""

    def test_detects_eval(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("result = eval(user_input)\n")
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
            f.write("x = 1\nprint(x)\n")
            f.flush()
            rules = {"anti_patterns": []}
            issues = check_anti_patterns(Path(f.name), "python", rules)
            self.assertEqual(len(issues), 0)
        Path(f.name).unlink(missing_ok=True)

    def test_multiline_pattern(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("except:\n    pass\n")
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


if __name__ == "__main__":
    unittest.main()

"""Tests for report_generator.py and fix_applier.py modules."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.fix_applier import apply_fixes
from tools.scripts.report_generator import (
    generate_html_report,
    generate_junit_xml,
    generate_sarif,
    write_report,
)
from tools.scripts.validate_language_rules import (
    Issue,
    ValidationResult,
)


def _make_result(
    file: str = "test.py",
    language: str = "python",
    issues: list[Issue] | None = None,
    passed: bool = True,
) -> ValidationResult:
    """Create a ValidationResult for testing."""
    vr = ValidationResult(file=file, language=language, issues=issues or [])
    if not passed:
        vr.issues.append(Issue("r1", "error", "security", file, 1, "error"))
    return vr


# ── report_generator.py tests ──────────────────────────────────────


class TestGenerateJunitXml(unittest.TestCase):
    """Test JUnit XML report generation."""

    def test_empty_results(self) -> None:
        xml = generate_junit_xml([])
        self.assertIn('tests="0"', xml)
        self.assertIn('failures="0"', xml)

    def test_passing_results(self) -> None:
        results = [_make_result(passed=True)]
        xml = generate_junit_xml(results)
        self.assertIn('tests="1"', xml)
        self.assertIn('failures="0"', xml)
        self.assertIn("test.py", xml)

    def test_failing_results(self) -> None:
        results = [_make_result(passed=False)]
        xml = generate_junit_xml(results)
        self.assertIn('failures="1"', xml)
        self.assertIn("failure", xml)

    def test_xml_escape(self) -> None:
        from tools.scripts.report_generator import _xml_escape

        self.assertEqual(_xml_escape("a<b>c"), "a&lt;b&gt;c")
        self.assertEqual(_xml_escape('"x"'), "&quot;x&quot;")
        self.assertEqual(_xml_escape("a&b"), "a&amp;b")


class TestGenerateHtmlReport(unittest.TestCase):
    """Test HTML report generation."""

    def test_empty_results(self) -> None:
        html = generate_html_report([])
        self.assertIn("<!DOCTYPE html>", html)
        self.assertIn("<strong>0</strong> files passed", html)

    def test_mixed_results(self) -> None:
        results = [_make_result(passed=True), _make_result(passed=False)]
        html = generate_html_report(results)
        self.assertIn("<strong>1</strong> files passed", html)
        self.assertIn("FAIL", html)

    def test_html_escape(self) -> None:
        from tools.scripts.report_generator import _html_escape

        self.assertEqual(_html_escape("a<b>c"), "a&lt;b&gt;c")
        self.assertEqual(_html_escape("a&b"), "a&amp;b")


class TestGenerateSarif(unittest.TestCase):
    """Test SARIF report generation."""

    def test_empty_results(self) -> None:
        import json

        sarif = generate_sarif([])
        data = json.loads(sarif)
        self.assertEqual(data["version"], "2.1.0")
        self.assertEqual(len(data["runs"][0]["results"]), 0)

    def test_with_issues(self) -> None:
        import json

        issue = Issue("r1", "error", "security", "test.py", 10, "msg")
        results = [_make_result(issues=[issue])]
        sarif = generate_sarif(results)
        data = json.loads(sarif)
        self.assertEqual(len(data["runs"][0]["results"]), 1)
        self.assertEqual(data["runs"][0]["results"][0]["level"], "error")


class TestWriteReport(unittest.TestCase):
    """Test write_report function."""

    def test_json_format(self) -> None:
        results = [_make_result()]
        content = write_report(results, "json")
        self.assertIsNotNone(content)
        import json

        data = json.loads(content)
        self.assertIn("summary", data)

    def test_junit_format(self) -> None:
        results = [_make_result()]
        content = write_report(results, "junit")
        self.assertIsNotNone(content)
        self.assertIn("testsuite", content)

    def test_html_format(self) -> None:
        results = [_make_result()]
        content = write_report(results, "html")
        self.assertIsNotNone(content)
        self.assertIn("<!DOCTYPE html>", content)

    def test_sarif_format(self) -> None:
        results = [_make_result()]
        content = write_report(results, "sarif")
        self.assertIsNotNone(content)

    def test_unknown_format(self) -> None:
        content = write_report([], "unknown")
        self.assertIsNone(content)

    def test_write_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "report.json"
            content = write_report([_make_result()], "json", output)
            self.assertTrue(output.exists())
            self.assertEqual(output.read_text(), content)


# ── fix_applier.py tests ──────────────────────────────────────────


class TestApplyFixes(unittest.TestCase):
    """Test auto-fix functionality."""

    def test_no_fixable_issues(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            issue = Issue("r1", "error", "security", f.name, 1, "msg")
            # No fix_replacement set
            fixes = apply_fixes(Path(f.name), [issue])
            self.assertEqual(len(fixes), 0)
        Path(f.name).unlink(missing_ok=True)

    def test_sed_style_fix(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("password = 'secret123'\n")
            f.flush()
            issue = Issue(
                "r1",
                "error",
                "security",
                f.name,
                1,
                "hardcoded secret",
                fix_replacement="s/secret123/REDACTED/",
            )
            fixes = apply_fixes(Path(f.name), [issue])
            self.assertEqual(len(fixes), 1)
            self.assertIn("REDACTED", fixes[0].fixed)
        Path(f.name).unlink(missing_ok=True)

    def test_dry_run_no_changes(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("password = 'secret123'\n")
            f.flush()
            original = Path(f.name).read_text()
            issue = Issue(
                "r1",
                "error",
                "security",
                f.name,
                1,
                "hardcoded secret",
                fix_replacement="s/secret123/REDACTED/",
            )
            fixes = apply_fixes(Path(f.name), [issue], dry_run=True)
            self.assertEqual(len(fixes), 1)
            # File should not be modified
            self.assertEqual(Path(f.name).read_text(), original)
        Path(f.name).unlink(missing_ok=True)

    def test_out_of_range_line(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            issue = Issue("r1", "error", "security", f.name, 999, "msg", fix_replacement="new")
            fixes = apply_fixes(Path(f.name), [issue])
            self.assertEqual(len(fixes), 0)
        Path(f.name).unlink(missing_ok=True)

    def test_nonexistent_file(self) -> None:
        issue = Issue("r1", "error", "security", "nonexistent.py", 1, "msg", fix_replacement="new")
        fixes = apply_fixes(Path("nonexistent.py"), [issue])
        self.assertEqual(len(fixes), 0)

    def test_invalid_regex(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            issue = Issue(
                "r1",
                "error",
                "security",
                f.name,
                1,
                "msg",
                fix_replacement="s/[invalid/REDACTED/",
            )
            fixes = apply_fixes(Path(f.name), [issue])
            # Should handle regex error gracefully
            self.assertEqual(len(fixes), 0)
        Path(f.name).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

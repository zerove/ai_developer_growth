# 拆分自 tests/test_rules_engine.py

"""Tests for rules_engine package - modular code quality checking engine."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.scripts.rules_engine.checker import (
    _detect_language,
    _map_severity,
    _parse_linter_output,
    check_directory,
    check_file,
)
from tools.scripts.rules_engine.models import (
    CheckResult,
)


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

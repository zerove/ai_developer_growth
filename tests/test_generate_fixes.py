"""Tests for generate_fixes.py heuristic fix generation."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.scripts.generate_fixes import (
    apply_fixes_to_yaml,
    generate_fixes,
    heuristic_fix,
    main,
)


class TestHeuristicFix(unittest.TestCase):
    """Test heuristic_fix function with various patterns."""

    def test_eval_pattern(self) -> None:
        result = heuristic_fix({"pattern": "eval(", "message": ""})
        self.assertEqual(result["source"], "heuristic")
        self.assertIn("literal_eval", result["fix_replacement"])

    def test_exec_pattern(self) -> None:
        result = heuristic_fix({"pattern": "exec(", "message": ""})
        self.assertEqual(result["source"], "heuristic")

    def test_bare_except_pattern(self) -> None:
        result = heuristic_fix({"pattern": "except:", "message": ""})
        self.assertIn("Exception", result["fix_replacement"])

    def test_as_any_pattern(self) -> None:
        result = heuristic_fix({"pattern": "as any", "message": ""})
        self.assertEqual(result["source"], "heuristic")

    def test_var_pattern(self) -> None:
        result = heuristic_fix({"pattern": "var ", "message": ""})
        self.assertIn("const", result["fix_replacement"])

    def test_os_system_pattern(self) -> None:
        result = heuristic_fix({"pattern": "os.system(", "message": ""})
        self.assertIn("subprocess", result["fix_replacement"])

    def test_md5_pattern(self) -> None:
        result = heuristic_fix({"pattern": "md5(", "message": ""})
        self.assertIn("sha256", result["fix_replacement"])

    def test_console_log_pattern(self) -> None:
        result = heuristic_fix({"pattern": "console.log(", "message": ""})
        self.assertEqual(result["fix_replacement"], "")

    def test_debugger_pattern(self) -> None:
        result = heuristic_fix({"pattern": "debugger", "message": ""})
        self.assertEqual(result["fix_replacement"], "")

    def test_message_bare_except(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "bare except clause"})
        self.assertIn("Exception", result["fix_replacement"])

    def test_message_eval(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "uses eval"})
        self.assertIn("literal_eval", result["fix_replacement"])

    def test_message_hardcoded_secret(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "hardcoded secret"})
        self.assertIn("environ", result["fix_replacement"])

    def test_message_sql_inject(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "sql injection risk"})
        self.assertIn("query", result["fix_replacement"])

    def test_message_print_logging(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "use logging instead of print"})
        self.assertIn("logging", result["fix_replacement"])

    def test_message_type_any(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "use specific type instead of any"})
        self.assertNotEqual(result["fix_replacement"], "")

    def test_message_console_log(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "remove console.log"})
        self.assertEqual(result["fix_replacement"], "")

    def test_message_debugger(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "remove debugger statement"})
        self.assertEqual(result["fix_replacement"], "")

    def test_message_shadowing(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "variable shadowing"})
        self.assertEqual(result["fix_replacement"], "")

    def test_message_todo(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "fix TODO item"})
        self.assertEqual(result["fix_replacement"], "")

    def test_fix_hint_fallback(self) -> None:
        result = heuristic_fix(
            {
                "pattern": "unknown_pattern",
                "message": "unknown message",
                "fix_hint": "use xyz instead",
            }
        )
        self.assertEqual(result["source"], "fix_hint")
        self.assertEqual(result["fix_replacement"], "use xyz instead")

    def test_no_fix_fallback(self) -> None:
        result = heuristic_fix({"pattern": "unknown", "message": "unknown"})
        self.assertEqual(result["source"], "none")
        self.assertEqual(result["fix_replacement"], "")


class TestApplyFixesToYaml(unittest.TestCase):
    """Test apply_fixes_to_yaml function."""

    def test_dry_run(self) -> None:
        fixes = [{"id": "test", "fix_replacement": "foo", "file": "bar.yml"}]
        count = apply_fixes_to_yaml(fixes, dry_run=True)
        self.assertEqual(count, 1)

    def test_empty_fixes(self) -> None:
        count = apply_fixes_to_yaml([], dry_run=False)
        self.assertEqual(count, 0)

    def test_apply_to_yaml(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("anti_patterns:\n  - id: test-rule\n    pattern: bad\n")
            f.flush()
            fixes = [
                {
                    "id": "test-rule",
                    "fix_replacement": "s/bad/good/",
                    "file": f.name,
                }
            ]
            count = apply_fixes_to_yaml(fixes, dry_run=False)
            self.assertEqual(count, 1)
        Path(f.name).unlink(missing_ok=True)

    def test_apply_no_fix_replacement(self) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yml", delete=False) as f:
            f.write("anti_patterns:\n  - id: test-rule\n    pattern: bad\n")
            f.flush()
            fixes = [
                {
                    "id": "test-rule",
                    "fix_replacement": "",
                    "file": f.name,
                }
            ]
            count = apply_fixes_to_yaml(fixes, dry_run=False)
            self.assertEqual(count, 0)
        Path(f.name).unlink(missing_ok=True)


class TestGenerateFixes(unittest.TestCase):
    """Test generate_fixes function."""

    def test_generate_fixes_nonexistent_lang(self) -> None:
        fixes = generate_fixes(["nonexistent_lang_xyz"])
        self.assertEqual(fixes, [])

    def test_generate_fixes_returns_list(self) -> None:
        result = generate_fixes(["python"], dry_run=True)
        self.assertIsInstance(result, list)


class TestGenerateFixesMain(unittest.TestCase):
    """Test the main() entry point."""

    def test_main_no_args(self) -> None:
        with patch("sys.argv", ["generate_fixes.py"]):
            with self.assertRaises(SystemExit):
                main()

    def test_main_with_all(self) -> None:
        with patch("sys.argv", ["generate_fixes.py", "--all", "--dry-run"]):
            result = main()
            self.assertEqual(result, 0)

    def test_main_with_lang(self) -> None:
        with patch("sys.argv", ["generate_fixes.py", "--lang", "python", "--dry-run"]):
            result = main()
            self.assertEqual(result, 0)

    def test_main_with_json_output(self) -> None:
        with patch("sys.argv", ["generate_fixes.py", "--lang", "python", "--json"]):
            result = main()
            self.assertEqual(result, 0)

    def test_main_with_verbose(self) -> None:
        with patch("sys.argv", ["generate_fixes.py", "--lang", "python", "--verbose"]):
            result = main()
            self.assertEqual(result, 0)

    def test_main_with_output_file(self) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            out_path = f.name
        with patch("sys.argv", ["generate_fixes.py", "--lang", "python", "-o", out_path]):
            result = main()
            self.assertEqual(result, 0)
            self.assertTrue(Path(out_path).exists())
        Path(out_path).unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()

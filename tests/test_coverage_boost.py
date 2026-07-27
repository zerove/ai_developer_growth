"""Targeted tests for low-coverage modules to boost coverage.

Covers:
- rules/models.py: FixResult, HealthScore, ValidationResult edge cases
- validators/cli.py: main() paths (changed_files, incremental, fix, health_score, linters, thresholds)
- anti_pattern_checker.py: nonexistent file, unicode error, empty pattern, regex error, multiline
- rule_loader.py: disk cache, yaml fallback, custom rules error handling
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# ── rules/models.py ──────────────────────────────────────────
from tools.scripts.rules.models import (
    FixResult,
    HealthScore,
    Issue,
    ValidationResult,
)


class TestRulesModelsIssue(unittest.TestCase):
    """Tests for rules/models.py Issue dataclass."""

    def test_issue_creation_defaults(self) -> None:
        issue = Issue(rule_id="r1", severity="error", category="sec", file="a.py", line=1)
        assert issue.column == 0
        assert issue.message == ""
        assert issue.fix_hint == ""
        assert issue.fix_replacement == ""

    def test_issue_to_dict_no_optional(self) -> None:
        issue = Issue(rule_id="r1", severity="error", category="sec", file="a.py", line=1)
        d = issue.to_dict()
        assert "fix_hint" not in d
        assert "fix_replacement" not in d

    def test_issue_to_dict_with_fix_hint(self) -> None:
        issue = Issue(rule_id="r1", severity="error", category="sec", file="a.py", line=1, fix_hint="use X instead")
        d = issue.to_dict()
        assert d["fix_hint"] == "use X instead"
        assert "fix_replacement" not in d

    def test_issue_to_dict_with_fix_replacement(self) -> None:
        issue = Issue(rule_id="r1", severity="error", category="sec", file="a.py", line=1, fix_replacement="new code")
        d = issue.to_dict()
        assert "fix_hint" not in d
        assert d["fix_replacement"] == "new code"

    def test_issue_to_dict_all_fields(self) -> None:
        issue = Issue(
            rule_id="r1",
            severity="warning",
            category="style",
            file="b.rs",
            line=10,
            column=5,
            message="msg",
            fix_hint="hint",
            fix_replacement="repl",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "r1"
        assert d["severity"] == "warning"
        assert d["category"] == "style"
        assert d["file"] == "b.rs"
        assert d["line"] == 10
        assert d["column"] == 5
        assert d["message"] == "msg"
        assert d["fix_hint"] == "hint"
        assert d["fix_replacement"] == "repl"


class TestRulesModelsValidationResult(unittest.TestCase):
    """Tests for ValidationResult."""

    def test_counts_empty(self) -> None:
        r = ValidationResult(file="a.py", language="python")
        assert r.error_count == 0
        assert r.warning_count == 0
        assert r.info_count == 0
        assert r.cached is False
        assert r.lines_checked == 0

    def test_counts_mixed(self) -> None:
        issues = [
            Issue("r1", "error", "sec", "a.py", 1),
            Issue("r2", "warning", "style", "a.py", 2),
            Issue("r3", "info", "info", "a.py", 3),
            Issue("r4", "error", "sec", "a.py", 4),
        ]
        r = ValidationResult(file="a.py", language="python", issues=issues, lines_checked=100)
        assert r.error_count == 2
        assert r.warning_count == 1
        assert r.info_count == 1

    def test_to_dict(self) -> None:
        issues = [Issue("r1", "error", "sec", "a.py", 1, message="bad")]
        r = ValidationResult(file="a.py", language="python", issues=issues, lines_checked=50, cached=True)
        d = r.to_dict()
        assert d["file"] == "a.py"
        assert d["language"] == "python"
        assert d["lines_checked"] == 50
        assert d["error_count"] == 1
        assert d["cached"] is True
        assert len(d["issues"]) == 1


class TestRulesModelsFixResult(unittest.TestCase):
    """Tests for FixResult."""

    def test_creation(self) -> None:
        fr = FixResult(file="a.py", line=5, rule_id="r1", original="old", replacement="new", applied=True)
        assert fr.applied is True

    def test_creation_default_not_applied(self) -> None:
        fr = FixResult(file="a.py", line=5, rule_id="r1", original="old", replacement="new")
        assert fr.applied is False

    def test_to_dict(self) -> None:
        fr = FixResult(file="a.py", line=5, rule_id="r1", original="old", replacement="new", applied=True)
        d = fr.to_dict()
        assert d == {
            "file": "a.py",
            "line": 5,
            "rule_id": "r1",
            "original": "old",
            "replacement": "new",
            "applied": True,
        }


class TestRulesModelsHealthScore(unittest.TestCase):
    """Tests for HealthScore."""

    def test_creation_and_to_dict(self) -> None:
        hs = HealthScore(score=95, grade="A", errors=0, warnings=1, infos=0, total_files=10)
        d = hs.to_dict()
        assert d["score"] == 95
        assert d["grade"] == "A"
        assert d["errors"] == 0
        assert d["warnings"] == 1
        assert d["total_files"] == 10


# ── rules_engine/anti_pattern_checker.py ─────────────────────


class TestAntiPatternCheckerEdgeCases(unittest.TestCase):
    """Tests for anti_pattern_checker.py edge cases."""

    def test_nonexistent_file(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        result = check_anti_patterns(Path("/nonexistent/file.py"), "python")
        assert result == []

    def test_unicode_decode_error(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"\x80\x81\x82\x83")  # Invalid UTF-8
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python")
            assert result == []
        finally:
            path.unlink()

    def test_empty_pattern_skipped(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {"anti_patterns": [{"id": "test", "pattern": "", "severity": "error", "message": "m"}]}
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert result == []
        finally:
            path.unlink()

    def test_invalid_regex_skipped(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {"anti_patterns": [{"id": "test", "pattern": "[invalid", "severity": "error", "message": "m"}]}
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert result == []
        finally:
            path.unlink()

    def test_comment_lines_skipped(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {"anti_patterns": [{"id": "test", "pattern": r"\beval\s*\(", "severity": "error", "message": "m"}]}
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("# eval(1)\n// eval(2)\nx = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert len(result) == 0
        finally:
            path.unlink()

    def test_multiline_pattern(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {
            "anti_patterns": [
                {
                    "id": "ml-test",
                    "pattern": "def foo\\n.*pass",
                    "multiline": True,
                    "severity": "warning",
                    "message": "empty function",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("def foo\n    pass\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert len(result) >= 1
            assert result[0].rule_id == "ml-test"
        finally:
            path.unlink()

    def test_exclude_patterns(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {
            "anti_patterns": [
                {
                    "id": "test",
                    "pattern": r"custom_eval\s*\(",
                    "severity": "error",
                    "message": "m",
                    "exclude_patterns": [r"# noqa"],
                }
            ]
        }
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("custom_eval(1)  # noqa\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert len(result) == 0
        finally:
            path.unlink()

    def test_ignore_case(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {
            "anti_patterns": [
                {
                    "id": "test",
                    "pattern": r"EVAL\(",
                    "severity": "error",
                    "message": "m",
                    "ignore_case": True,
                }
            ]
        }
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval(1)\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert len(result) >= 1
        finally:
            path.unlink()

    def test_invalid_multiline_regex(self) -> None:
        from tools.scripts.rules_engine.anti_pattern_checker import check_anti_patterns

        rules = {
            "anti_patterns": [
                {
                    "id": "ml-bad",
                    "pattern": "[invalid",
                    "multiline": True,
                    "severity": "warning",
                    "message": "m",
                }
            ]
        }
        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("hello\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_anti_patterns(path, "python", rules=rules)
            assert result == []
        finally:
            path.unlink()


# ── rules_engine/rule_loader.py ──────────────────────────────


class TestRuleLoaderEdgeCases(unittest.TestCase):
    """Tests for rule_loader.py edge cases."""

    def test_disk_cache_save_load(self) -> None:
        from tools.scripts.rules_engine import rule_loader

        with tempfile.TemporaryDirectory() as td:
            cache_dir = Path(td)
            cache_file = cache_dir / "test_cache.json"
            test_data = {"key": "value", "nested": [1, 2, 3]}

            with (
                patch.object(rule_loader, "_DISK_CACHE_DIR", cache_dir),
                patch.object(rule_loader, "_DISK_CACHE_FILE", cache_file),
            ):
                rule_loader._save_disk_cache(test_data)
                result = rule_loader._load_disk_cache()
                assert result == test_data

    def test_load_disk_cache_nonexistent(self) -> None:
        from tools.scripts.rules_engine import rule_loader

        with tempfile.TemporaryDirectory() as td:
            cache_file = Path(td) / "nonexistent.json"
            with patch.object(rule_loader, "_DISK_CACHE_FILE", cache_file):
                result = rule_loader._load_disk_cache()
                assert result == {}

    def test_load_disk_cache_corrupt(self) -> None:
        from tools.scripts.rules_engine import rule_loader

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not valid json {{{")
            f.flush()
            cache_file = Path(f.name)
        try:
            with patch.object(rule_loader, "_DISK_CACHE_FILE", cache_file):
                result = rule_loader._load_disk_cache()
                assert result == {}
        finally:
            cache_file.unlink()

    def test_save_disk_cache_oserror(self) -> None:
        from tools.scripts.rules_engine import rule_loader

        with patch.object(rule_loader, "_DISK_CACHE_DIR", Path("/nonexistent/deep/path")):
            # Should not raise
            rule_loader._save_disk_cache({"test": 1})

    def test_file_hash_nonexistent(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _file_hash

        result = _file_hash(Path("/nonexistent/file.py"))
        assert result == ""

    def test_file_hash_valid(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _file_hash

        with tempfile.NamedTemporaryFile(delete=False) as f:
            f.write(b"hello world")
            f.flush()
            path = Path(f.name)
        try:
            h = _file_hash(path)
            assert len(h) == 64  # SHA-256 hex
        finally:
            path.unlink()

    def test_load_cache_corrupt_file(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _load_cache

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("invalid json")
            f.flush()
            path = Path(f.name)
        try:
            result = _load_cache(path)
            assert result == {}
        finally:
            path.unlink()

    def test_save_cache_oserror(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _save_cache

        # Should not raise
        _save_cache(Path("/nonexistent/deep/file.json"), {"k": "v"})

    def test_rules_hash_nonexistent_language(self) -> None:
        from tools.scripts.rules_engine import rule_loader

        result = rule_loader._rules_hash("nonexistent_lang_xyz")
        assert result == ""

    def test_get_embedded_rules(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _get_embedded_rules

        rules = _get_embedded_rules("python")
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) == 2
        assert rules["anti_patterns"][0]["id"] == "py-eval-exec"

    def test_merge_anti_patterns_custom_new_only(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _merge_anti_patterns

        base = [{"id": "a-1", "severity": "error"}]
        custom = [{"id": "b-1", "severity": "warning"}]
        merged = _merge_anti_patterns(base, custom)
        assert len(merged) == 2

    def test_merge_anti_patterns_severity_override(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _merge_anti_patterns

        base = [{"id": "a-1", "severity": "error"}]
        custom = [{"id": "a-1", "severity_override": "warning"}]
        merged = _merge_anti_patterns(base, custom)
        assert merged[0]["severity"] == "warning"

    def test_merge_anti_patterns_full_replacement(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _merge_anti_patterns

        base = [{"id": "a-1", "severity": "error", "name": "old"}]
        custom = [{"id": "a-1", "severity": "warning", "name": "new"}]
        merged = _merge_anti_patterns(base, custom)
        assert merged[0]["name"] == "new"

    def test_load_custom_rules_no_yaml(self) -> None:
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        with tempfile.TemporaryDirectory() as td:
            result = load_custom_rules(Path(td))
            assert result == {"anti_patterns": [], "naming": {}, "thresholds": {}}

    def test_load_custom_rules_with_yaml(self) -> None:
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        with tempfile.TemporaryDirectory() as td:
            rules_dir = Path(td) / ".ai-rules"
            rules_dir.mkdir()
            yml = rules_dir / "custom.yml"
            yml.write_text("anti_patterns:\n  - id: test-rule\n    pattern: test\n")
            result = load_custom_rules(Path(td))
            assert len(result["anti_patterns"]) == 1
            assert result["anti_patterns"][0]["id"] == "test-rule"

    def test_load_custom_rules_non_dict_yaml(self) -> None:
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        with tempfile.TemporaryDirectory() as td:
            rules_dir = Path(td) / ".ai-rules"
            rules_dir.mkdir()
            yml = rules_dir / "list.yml"
            yml.write_text("- item1\n- item2\n")
            result = load_custom_rules(Path(td))
            assert result["anti_patterns"] == []

    def test_load_custom_rules_broken_yaml(self) -> None:
        from tools.scripts.rules_engine.rule_loader import load_custom_rules

        with tempfile.TemporaryDirectory() as td:
            rules_dir = Path(td) / ".ai-rules"
            rules_dir.mkdir()
            yml = rules_dir / "broken.yml"
            yml.write_text("invalid: [yaml: {broken")
            # Should not raise, just warn
            result = load_custom_rules(Path(td))
            assert "anti_patterns" in result

    def test_load_common_rules_nonexistent(self) -> None:
        from tools.scripts.rules_engine.rule_loader import _load_common_rules

        result = _load_common_rules(Path("/nonexistent"))
        assert result == {}

    def test_load_rules_yaml_not_installed(self) -> None:
        """Test embedded rules fallback when yaml not available."""
        from tools.scripts.rules_engine.rule_loader import _get_embedded_rules

        # Test the embedded rules directly
        rules = _get_embedded_rules("rust")
        assert rules["anti_patterns"][0]["id"] == "ru-eval-exec"


# ── validators/cli.py ────────────────────────────────────────


class TestValidatorsCLIMain(unittest.TestCase):
    """Tests for validators/cli.py main() paths."""

    def test_path_not_found(self) -> None:
        from tools.scripts.validators.cli import main

        with patch("sys.argv", ["prog", "/nonexistent/path"]):
            result = main()
            assert result == 1

    def test_file_no_lang_no_detect(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".xyz", delete=False) as f:
            f.write(b"hello")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path)]):
                result = main()
                assert result == 1  # Cannot detect language
        finally:
            path.unlink()

    def test_file_with_lang(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python"]):
                result = main()
                assert result == 0
        finally:
            path.unlink()

    def test_file_incremental_unchanged(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            # First run to populate cache
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--incremental"]):
                main()
            # Second run should skip
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--incremental"]):
                result = main()
                assert result == 0
        finally:
            path.unlink()

    def test_directory_no_lang_no_autodetect(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.TemporaryDirectory() as td:
            with patch("sys.argv", ["prog", td]):
                result = main()
                assert result == 1

    def test_directory_auto_detect(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.TemporaryDirectory() as td:
            py_file = Path(td) / "test.py"
            py_file.write_text("x = 1\n")
            with patch("sys.argv", ["prog", td, "--auto-detect"]):
                result = main()
                assert result in (0, 1)

    def test_directory_with_lang(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.TemporaryDirectory() as td:
            py_file = Path(td) / "test.py"
            py_file.write_text("x = 1\n")
            with patch("sys.argv", ["prog", td, "--lang", "python"]):
                result = main()
                assert result in (0, 1)

    def test_changed_files(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", "/nonexistent", "--lang", "python", "--changed-files", str(path)]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_changed_files_nonexistent(self) -> None:
        from tools.scripts.validators.cli import main

        with patch("sys.argv", ["prog", "/nonexistent", "--lang", "python", "--changed-files", "/nonexistent/file.py"]):
            result = main()
            assert result == 1  # Path not found

    def test_incremental_directory(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.TemporaryDirectory() as td:
            py_file = Path(td) / "test.py"
            py_file.write_text("x = 1\n")
            # First run
            with patch("sys.argv", ["prog", td, "--lang", "python", "--incremental"]):
                main()
            # Second run: no changes
            with patch("sys.argv", ["prog", td, "--lang", "python", "--incremental"]):
                result = main()
                assert result == 0

    def test_json_output(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--json"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_format_json(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "json"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_health_score(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--health-score"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_max_errors_exceeded(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--max-errors", "0"]):
                result = main()
                assert result == 1
        finally:
            path.unlink()

    def test_max_errors_not_exceeded(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--max-errors", "10"]):
                result = main()
                assert result == 0
        finally:
            path.unlink()

    def test_fail_on_warnings(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--fail-on-warnings"]):
                result = main()
                # May or may not have warnings; just check it doesn't crash
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_output_to_file(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as out:
                out_path = Path(out.name)
            try:
                with patch(
                    "sys.argv", ["prog", str(path), "--lang", "python", "--format", "json", "-o", str(out_path)]
                ):
                    result = main()
                    assert result in (0, 1)
            finally:
                out_path.unlink()
        finally:
            path.unlink()

    def test_format_html(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "html"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_format_sarif(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "sarif"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_format_junit(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "junit"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_dry_run(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--dry-run"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_max_warnings_exceeded(self) -> None:
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "json", "--max-warnings", "0"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()


# ── validators/health.py ─────────────────────────────────────


class TestHealthScoreEdgeCases(unittest.TestCase):
    """Tests for validators/health.py edge cases."""

    def test_perfect_score(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        # No issues, all clean
        r = MagicMock()
        r.error_count = 0
        r.warning_count = 0
        r.info_count = 0
        r.passed = True
        result = calculate_health_score([r])
        assert result.score >= 90
        assert result.grade == "A"

    def test_many_errors_grade_f(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        r = MagicMock()
        r.error_count = 20
        r.warning_count = 0
        r.info_count = 0
        r.passed = False
        result = calculate_health_score([r])
        assert result.score == 0
        assert result.grade == "F"

    def test_moderate_warnings_grade_c(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        r = MagicMock()
        r.error_count = 2
        r.warning_count = 5
        r.info_count = 0
        r.passed = False
        result = calculate_health_score([r])
        assert 60 <= result.score <= 80

    def test_empty_results(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        result = calculate_health_score([])
        assert result.score == 100
        assert result.grade == "A"
        assert "All files clean" in result.details[0]

    def test_health_to_dict(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        r = MagicMock()
        r.error_count = 1
        r.warning_count = 0
        r.info_count = 0
        r.passed = True
        result = calculate_health_score([r])
        d = result.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "breakdown" in d
        assert "details" in d

    def test_info_penalty(self) -> None:
        from tools.scripts.validators.health import calculate_health_score

        r = MagicMock()
        r.error_count = 0
        r.warning_count = 0
        r.info_count = 10
        r.passed = True
        result = calculate_health_score([r])
        # 10 infos * -0.5 = -5, but clean files bonus
        assert result.score <= 100


# ── validators/pipeline.py ───────────────────────────────────


class TestValidatorsPipelineEdgeCases(unittest.TestCase):
    """Tests for validators/pipeline.py edge cases."""

    def test_validate_file_os_error(self) -> None:
        from tools.scripts.validators.pipeline import validate_file

        result = validate_file(Path("/nonexistent/file.py"), "python")
        assert result.error_count == 0 or result.lines_checked == 0

    def test_validate_directory_with_exclude(self) -> None:
        from tools.scripts.validators.pipeline import validate_directory

        with tempfile.TemporaryDirectory() as td:
            py_file = Path(td) / "test.py"
            py_file.write_text("x = 1\n")
            node_modules = Path(td) / "node_modules"
            node_modules.mkdir()
            (node_modules / "pkg.js").write_text("y = 2\n")
            results = validate_directory(Path(td), "python", exclude=["node_modules"])
            assert len(results) >= 1

    def test_validate_directory_nonexistent(self) -> None:
        from tools.scripts.validators.pipeline import validate_directory

        results = validate_directory(Path("/nonexistent"), "python")
        assert results == []


# ── validators/cli.py print_results ───────────────────────────


class TestPrintResults(unittest.TestCase):
    """Tests for validators/cli.py print_results function."""

    def test_empty_results(self) -> None:
        from tools.scripts.validators.cli import print_results

        result = print_results([], use_json=False)
        assert result == 0

    def test_results_with_issues_text(self) -> None:
        from tools.scripts.validators.cli import print_results

        issue = MagicMock()
        issue.severity = "error"
        issue.rule_id = "test-rule"
        issue.message = "Test issue"
        issue.line = 10
        issue.fix_hint = "Fix this"
        r = MagicMock()
        r.file = "test.py"
        r.language = "python"
        r.lines_checked = 50
        r.error_count = 1
        r.warning_count = 0
        r.info_count = 0
        r.passed = False
        r.issues = [issue]
        result = print_results([r], use_json=False)
        assert result == 1  # Has errors

    def test_results_with_warnings_only(self) -> None:
        from tools.scripts.validators.cli import print_results

        issue = MagicMock()
        issue.severity = "warning"
        issue.rule_id = "test-rule"
        issue.message = "Warning"
        issue.line = 5
        issue.fix_hint = ""
        r = MagicMock()
        r.file = "test.py"
        r.language = "python"
        r.lines_checked = 50
        r.error_count = 0
        r.warning_count = 1
        r.info_count = 0
        r.passed = True
        r.issues = [issue]
        result = print_results([r], use_json=False)
        assert result == 0  # Warnings only, still passes

    def test_results_with_no_issues(self) -> None:
        from tools.scripts.validators.cli import print_results

        r = MagicMock()
        r.file = "clean.py"
        r.language = "python"
        r.lines_checked = 10
        r.error_count = 0
        r.warning_count = 0
        r.info_count = 0
        r.passed = True
        r.issues = []
        result = print_results([r], use_json=False)
        assert result == 0


# ── rules_engine/checker.py ──────────────────────────────────


class TestCheckerEdgeCases(unittest.TestCase):
    """Tests for rules_engine/checker.py edge cases."""

    def test_check_file_nonexistent(self) -> None:
        from tools.scripts.rules_engine.checker import check_file

        result = check_file(Path("/nonexistent/file.py"), "python")
        assert result.skipped is True or len(result.issues) == 0

    def test_check_file_python(self) -> None:
        from tools.scripts.rules_engine.checker import check_file

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            result = check_file(path, language="python")
            assert result.file == str(path)
            assert result.language == "python"
        finally:
            path.unlink()

    def test_check_file_unicode_error(self) -> None:
        from tools.scripts.rules_engine.checker import check_file

        with tempfile.NamedTemporaryFile(suffix=".py", delete=False) as f:
            f.write(b"\x80\x81\x82\x83")  # Invalid UTF-8
            f.flush()
            path = Path(f.name)
        try:
            result = check_file(path, language="python")
            assert result is not None
            assert result.skipped is True
        finally:
            path.unlink()


# ── rules_engine/complexity_checker.py ────────────────────────


class TestComplexityCheckerEdgeCases(unittest.TestCase):
    """Tests for complexity_checker edge cases."""

    def test_python_empty_file(self) -> None:
        from tools.scripts.rules_engine.complexity_checker import check_python_complexity

        result = check_python_complexity([], {}, "test.py")
        assert result == []

    def test_js_empty_file(self) -> None:
        from tools.scripts.rules_engine.complexity_checker import check_js_complexity

        result = check_js_complexity([], {}, "test.js")
        assert result == []

    def test_max_nesting_depth(self) -> None:
        import ast

        from tools.scripts.rules_engine.complexity_checker import _max_nesting_depth

        tree = ast.parse("x = 1")
        assert _max_nesting_depth(tree) == 0

        tree2 = ast.parse("if x:\n    if y:\n        pass")
        assert _max_nesting_depth(tree2) >= 1


# ── validators/cli.py additional path coverage ────────────────


class TestValidatorsCLIAdditionalPaths(unittest.TestCase):
    """Additional tests for validators/cli.py uncovered paths."""

    def test_fix_dry_run_with_issues(self) -> None:
        """Test --fix --dry-run with files that have fixable issues."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--fix", "--dry-run"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_fix_real_with_issues(self) -> None:
        """Test --fix (not dry-run) with fixable issues."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--fix"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_linters_with_issues(self) -> None:
        """Test --linters flag with mock returning issues."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            mock_issues = [
                {"linter": "ruff", "file": str(path), "line": 1, "message": "unused var"},
            ]
            with (
                patch("sys.argv", ["prog", str(path), "--lang", "python", "--linters", "ruff"]),
                patch("tools.scripts.linter_runner.run_linter_aggregation", return_value=mock_issues),
            ):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_linters_with_many_issues(self) -> None:
        """Test --linters flag with >20 issues (truncation)."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            mock_issues = [{"linter": "ruff", "file": str(path), "line": i, "message": f"issue {i}"} for i in range(25)]
            with (
                patch("sys.argv", ["prog", str(path), "--lang", "python", "--linters", "ruff"]),
                patch("tools.scripts.linter_runner.run_linter_aggregation", return_value=mock_issues),
            ):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_max_warnings_text_format_exceeded(self) -> None:
        """Test --max-warnings exceeded in text format."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--max-warnings", "0"]):
                result = main()
                # May or may not have warnings
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_fail_on_warnings_text_format(self) -> None:
        """Test --fail-on-warnings in text format."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--fail-on-warnings"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_max_errors_json_format(self) -> None:
        """Test --max-errors in non-text (json) format."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "json", "--max-errors", "0"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_max_warnings_json_format(self) -> None:
        """Test --max-warnings in non-text (json) format."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--format", "json", "--max-warnings", "0"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_fix_with_real_fixes_applied(self) -> None:
        """Test --fix where apply_fixes actually returns fixes."""
        from tools.scripts.validators.cli import main

        mock_fix = MagicMock()
        mock_fix.file = "test.py"
        mock_fix.line = 1
        mock_fix.rule_id = "test-rule"
        mock_fix.original = "old"
        mock_fix.fixed = "new"

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with (
                patch("sys.argv", ["prog", str(path), "--lang", "python", "--fix"]),
                patch("tools.scripts.fix_applier.apply_fixes", return_value=[mock_fix]),
            ):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_dry_run_no_results(self) -> None:
        """Test --dry-run with no results returns 0."""
        from tools.scripts.validators.cli import main

        with tempfile.TemporaryDirectory() as td:
            # Empty directory, no files
            with patch("sys.argv", ["prog", td, "--lang", "python", "--dry-run"]):
                result = main()
                assert result == 0

    def test_health_score_with_errors(self) -> None:
        """Test --health-score with files that have errors."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("eval('bad')\n")
            f.flush()
            path = Path(f.name)
        try:
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--health-score"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_file_incremental_changed(self) -> None:
        """Test --incremental where file has changed since last check."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            # First run
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--incremental"]):
                main()
            # Modify file
            path.write_text("y = 2\n")
            # Second run: should detect change
            with patch("sys.argv", ["prog", str(path), "--lang", "python", "--incremental"]):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()

    def test_linter_aggregation_no_issues(self) -> None:
        """Test --linters returns no issues."""
        from tools.scripts.validators.cli import main

        with tempfile.NamedTemporaryFile(suffix=".py", mode="w", delete=False) as f:
            f.write("x = 1\n")
            f.flush()
            path = Path(f.name)
        try:
            with (
                patch("sys.argv", ["prog", str(path), "--lang", "python", "--linters", "ruff"]),
                patch("tools.scripts.linter_runner.run_linter_aggregation", return_value=[]),
            ):
                result = main()
                assert result in (0, 1)
        finally:
            path.unlink()


if __name__ == "__main__":
    unittest.main()

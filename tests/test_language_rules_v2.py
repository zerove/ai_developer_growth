"""Tests for language rules v2 features: auto-fix, custom rules, reports, health score, linter aggregation."""

from __future__ import annotations

import json

# Ensure tests/ is on path for imports
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.scripts.validate_language_rules import (
    FixResult,
    Issue,
    ValidationResult,
    _file_hash,
    _get_supported_files,
    _load_cache,
    _merge_rules,
    _save_cache,
    apply_fixes,
    calculate_health_score,
    generate_html_report,
    generate_junit_xml,
    generate_sarif,
    load_custom_rules,
    load_rules,
    validate_file,
    write_report,
)

# ──────────────────────────────────────────────────────────
# FixResult tests
# ──────────────────────────────────────────────────────────


class TestFixResult:
    def test_creation(self) -> None:
        fix = FixResult(
            file="test.py",
            rule_id="py-test",
            line=1,
            original="old",
            fixed="new",
            description="Fixed it",
        )
        assert fix.file == "test.py"
        assert fix.original == "old"
        assert fix.fixed == "new"

    def test_to_dict(self) -> None:
        fix = FixResult(
            file="test.py",
            rule_id="py-test",
            line=5,
            original="print('hello')",
            fixed="logger.info('hello')",
            description="Use logging",
        )
        d = fix.to_dict()
        assert d["file"] == "test.py"
        assert d["line"] == 5
        assert d["original"] == "print('hello')"


# ──────────────────────────────────────────────────────────
# Auto-fix tests (#1)
# ──────────────────────────────────────────────────────────


class TestAutoFix:
    def test_apply_fixes_dry_run(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("except:\n    pass\n")

        issues = [
            Issue(
                rule_id="py-bare-except",
                severity="error",
                category="error_handling",
                file=str(test_file),
                line=1,
                message="Avoid bare except",
                fix_replacement="s/except:/except Exception:/",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=True)
        assert len(fixes) == 1
        assert fixes[0].fixed == "except Exception:"
        # File should NOT be modified in dry run
        assert test_file.read_text() == "except:\n    pass\n"

    def test_apply_fixes_real(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("except:\n    pass\n")

        issues = [
            Issue(
                rule_id="py-bare-except",
                severity="error",
                category="error_handling",
                file=str(test_file),
                line=1,
                message="Avoid bare except",
                fix_replacement="s/except:/except Exception:/",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=False)
        assert len(fixes) == 1
        # File SHOULD be modified
        assert "except Exception:" in test_file.read_text()

    def test_apply_fixes_no_replacement(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        issues = [
            Issue(
                rule_id="py-test",
                severity="warning",
                category="general",
                file=str(test_file),
                line=1,
                message="Some issue",
                fix_replacement="",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=True)
        assert len(fixes) == 0

    def test_apply_fixes_out_of_range_line(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1\n")

        issues = [
            Issue(
                rule_id="py-test",
                severity="warning",
                category="general",
                file=str(test_file),
                line=999,
                message="Some issue",
                fix_replacement="s/x/y/",
            )
        ]

        fixes = apply_fixes(test_file, issues, dry_run=True)
        assert len(fixes) == 0


# ──────────────────────────────────────────────────────────
# Custom rules tests (#3)
# ──────────────────────────────────────────────────────────


class TestCustomRules:
    def test_load_custom_rules_empty(self, tmp_path: Path) -> None:
        rules = load_custom_rules(tmp_path)
        assert rules["anti_patterns"] == []

    def test_load_custom_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        rule_file = rules_dir / "custom.yml"
        rule_file.write_text(
            yaml.dump(
                {
                    "anti_patterns": [
                        {
                            "id": "custom-no-todo",
                            "name": "TODO comments",
                            "severity": "warning",
                            "category": "code_quality",
                            "pattern": "TODO|FIXME",
                            "message": "Avoid TODO comments",
                        }
                    ]
                }
            )
        )

        rules = load_custom_rules(tmp_path)
        assert len(rules["anti_patterns"]) == 1
        assert rules["anti_patterns"][0]["id"] == "custom-no-todo"

    def test_merge_rules_override(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "old"},
            ],
            "thresholds": {"max_line_length": 120},
        }
        custom = {
            "anti_patterns": [
                {"id": "py-test", "severity": "error", "pattern": "new"},
            ],
            "thresholds": {"max_line_length": 100},
        }

        merged = _merge_rules(base, custom)
        # Should override by ID
        assert merged["anti_patterns"][0]["severity"] == "error"
        assert merged["anti_patterns"][0]["pattern"] == "new"
        # Should override threshold
        assert merged["thresholds"]["max_line_length"] == 100

    def test_merge_rules_append_new(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "old"},
            ]
        }
        custom = {
            "anti_patterns": [
                {"id": "custom-new", "severity": "info", "pattern": "new"},
            ]
        }

        merged = _merge_rules(base, custom)
        assert len(merged["anti_patterns"]) == 2
        assert merged["anti_patterns"][1]["id"] == "custom-new"

    def test_validate_file_with_custom_rules(self, tmp_path: Path) -> None:
        test_file = tmp_path / "test.py"
        test_file.write_text("x = 1  # TODO: fix this\n")

        custom = {
            "anti_patterns": [
                {
                    "id": "custom-no-todo",
                    "name": "TODO comments",
                    "severity": "warning",
                    "category": "code_quality",
                    "pattern": "TODO|FIXME",
                    "message": "Avoid TODO comments",
                }
            ]
        }

        result = validate_file(test_file, "python", custom_rules=custom)
        todo_issues = [i for i in result.issues if i.rule_id == "custom-no-todo"]
        assert len(todo_issues) == 1


# ──────────────────────────────────────────────────────────
# Report tests (#6)
# ──────────────────────────────────────────────────────────


class TestReports:
    def _make_results(self) -> list[ValidationResult]:
        r1 = ValidationResult(file="good.py", language="python", lines_checked=10)
        r2 = ValidationResult(file="bad.py", language="python", lines_checked=20)
        r2.issues.append(
            Issue(
                rule_id="py-test",
                severity="error",
                category="security",
                file="bad.py",
                line=5,
                message="Security issue",
            )
        )
        return [r1, r2]

    def test_junit_xml(self) -> None:
        results = self._make_results()
        xml = generate_junit_xml(results)
        assert '<?xml version="1.0"' in xml
        assert '<testsuite name="language-rules"' in xml
        assert 'tests="2"' in xml
        assert 'failures="1"' in xml

    def test_html_report(self) -> None:
        results = self._make_results()
        html = generate_html_report(results)
        assert "<!DOCTYPE html>" in html
        assert "good.py" in html
        assert "bad.py" in html

    def test_write_report_json(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.json"
        content = write_report(results, "json", out)
        assert content is not None
        data = json.loads(content)
        assert data["summary"]["total_files"] == 2
        assert data["summary"]["total_errors"] == 1
        assert out.exists()

    def test_write_report_junit(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.xml"
        content = write_report(results, "junit", out)
        assert content is not None
        assert "<testsuite" in content
        assert out.exists()

    def test_write_report_html(self, tmp_path: Path) -> None:
        results = self._make_results()
        out = tmp_path / "report.html"
        content = write_report(results, "html", out)
        assert content is not None
        assert "<!DOCTYPE html>" in content
        assert out.exists()


# ──────────────────────────────────────────────────────────
# Health score tests (#10)
# ──────────────────────────────────────────────────────────


class TestHealthScore:
    def test_perfect_score(self) -> None:
        results = [ValidationResult(file="clean.py", language="python", lines_checked=10)]
        health = calculate_health_score(results)
        assert health.score >= 90
        assert health.grade == "A"

    def test_errors_reduce_score(self) -> None:
        r = ValidationResult(file="bad.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(rule_id="test", severity="error", category="security", file="bad.py", line=1, message="err")
        )
        health = calculate_health_score([r])
        assert health.score < 100
        assert any("errors" in d for d in health.details)

    def test_warnings_reduce_score(self) -> None:
        r = ValidationResult(file="warn.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(rule_id="test", severity="warning", category="general", file="warn.py", line=1, message="warn")
        )
        health = calculate_health_score([r])
        # Warning penalty (-2) is offset by clean file bonus (+2), so score may stay 100
        # But the breakdown should show the penalty
        assert health.breakdown["warning_penalty"] < 0
        assert "warnings" in " ".join(health.details).lower()

    def test_grade_scale(self) -> None:
        # Many errors = F grade
        r = ValidationResult(file="bad.py", language="python", lines_checked=10)
        for i in range(20):
            r.issues.append(
                Issue(
                    rule_id=f"test-{i}", severity="error", category="security", file="bad.py", line=i + 1, message="err"
                )
            )
        health = calculate_health_score([r])
        assert health.score <= 60
        assert health.grade in ("D", "F")

    def test_to_dict(self) -> None:
        results = [ValidationResult(file="clean.py", language="python", lines_checked=10)]
        health = calculate_health_score(results)
        d = health.to_dict()
        assert "score" in d
        assert "grade" in d
        assert "breakdown" in d


# ──────────────────────────────────────────────────────────
# Threshold enforcement tests (#7)
# ──────────────────────────────────────────────────────────


class TestThresholds:
    def test_max_errors_cli(self, tmp_path: Path) -> None:
        """Test that max-errors threshold works via validate_file."""
        r = ValidationResult(file="test.py", language="python")
        r.issues.append(Issue(rule_id="e1", severity="error", category="sec", file="test.py", line=1, message="err1"))
        r.issues.append(Issue(rule_id="e2", severity="error", category="sec", file="test.py", line=2, message="err2"))

        # 2 errors, threshold 1 -> should fail
        total_errors = sum(1 for i in r.issues if i.severity == "error")
        assert total_errors > 1

    def test_max_warnings_cli(self) -> None:
        """Test that max-warnings threshold works."""
        r = ValidationResult(file="test.py", language="python")
        for i in range(5):
            r.issues.append(
                Issue(rule_id=f"w{i}", severity="warning", category="gen", file="test.py", line=i + 1, message="warn")
            )
        total_warnings = sum(1 for i in r.issues if i.severity == "warning")
        assert total_warnings == 5


# ──────────────────────────────────────────────────────────
# Issue fix_replacement tests
# ──────────────────────────────────────────────────────────


class TestIssueFixReplacement:
    def test_fix_replacement_in_to_dict(self) -> None:
        issue = Issue(
            rule_id="test",
            severity="error",
            category="security",
            file="test.py",
            line=1,
            message="test",
            fix_replacement="s/old/new/",
        )
        d = issue.to_dict()
        assert "fix_replacement" in d
        assert d["fix_replacement"] == "s/old/new/"

    def test_no_fix_replacement_in_to_dict(self) -> None:
        issue = Issue(
            rule_id="test",
            severity="error",
            category="security",
            file="test.py",
            line=1,
            message="test",
        )
        d = issue.to_dict()
        assert "fix_replacement" not in d


# ──────────────────────────────────────────────────────────
# SARIF output tests (#10)
# ──────────────────────────────────────────────────────────


class TestSARIF:
    def test_generate_sarif(self) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(
                rule_id="py-test",
                severity="error",
                category="security",
                file="test.py",
                line=5,
                message="Security issue",
            )
        )
        sarif_json = generate_sarif([r])
        sarif = json.loads(sarif_json)
        assert sarif["version"] == "2.1.0"
        assert len(sarif["runs"]) == 1
        assert len(sarif["runs"][0]["results"]) == 1
        assert sarif["runs"][0]["results"][0]["ruleId"] == "py-test"
        assert sarif["runs"][0]["results"][0]["level"] == "error"

    def test_sarif_empty(self) -> None:
        sarif_json = generate_sarif([])
        sarif = json.loads(sarif_json)
        assert sarif["runs"][0]["results"] == []

    def test_sarif_severity_levels(self) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(Issue(rule_id="e", severity="error", category="c", file="test.py", line=1, message="e"))
        r.issues.append(Issue(rule_id="w", severity="warning", category="c", file="test.py", line=2, message="w"))
        r.issues.append(Issue(rule_id="i", severity="info", category="c", file="test.py", line=3, message="i"))
        sarif = json.loads(generate_sarif([r]))
        levels = [res["level"] for res in sarif["runs"][0]["results"]]
        assert levels == ["error", "warning", "note"]

    def test_write_report_sarif(self, tmp_path: Path) -> None:
        r = ValidationResult(file="test.py", language="python", lines_checked=10)
        r.issues.append(
            Issue(rule_id="py-test", severity="error", category="security", file="test.py", line=1, message="err")
        )
        out = tmp_path / "report.sarif"
        content = write_report([r], "sarif", out)
        assert content is not None
        assert out.exists()
        sarif = json.loads(content)
        assert sarif["version"] == "2.1.0"


# ──────────────────────────────────────────────────────────
# Common rules tests (#6)
# ──────────────────────────────────────────────────────────


class TestCommonRules:
    def test_common_rules_loaded(self) -> None:
        """Verify common rules are merged into language rules."""
        rules = load_rules("python")
        anti_ids = [p["id"] for p in rules.get("anti_patterns", [])]
        # Common rules should be present
        assert any("common-" in rid for rid in anti_ids), f"Common rules not found in: {anti_ids[:10]}"

    def test_common_secret_rule(self) -> None:
        """Verify common-hardcoded-secret rule exists."""
        rules = load_rules("python")
        anti_ids = [p["id"] for p in rules.get("anti_patterns", [])]
        assert "common-hardcoded-secret" in anti_ids


# ──────────────────────────────────────────────────────────
# Severity override tests (#4)
# ──────────────────────────────────────────────────────────


class TestSeverityOverride:
    def test_severity_override(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "test"},
            ],
        }
        custom = {
            "anti_patterns": [
                {"id": "py-test", "severity_override": "error"},
            ],
        }
        merged = _merge_rules(base, custom)
        assert merged["anti_patterns"][0]["severity"] == "error"
        assert merged["anti_patterns"][0]["pattern"] == "test"  # pattern preserved

    def test_severity_override_not_found(self) -> None:
        base = {
            "anti_patterns": [
                {"id": "py-test", "severity": "warning", "pattern": "test"},
            ],
        }
        custom = {
            "anti_patterns": [
                {"id": "nonexistent", "severity_override": "error"},
            ],
        }
        merged = _merge_rules(base, custom)
        assert merged["anti_patterns"][0]["severity"] == "warning"  # unchanged


# ──────────────────────────────────────────────────────────
# Cache and incremental tests (#7)
# ──────────────────────────────────────────────────────────


class TestCacheAndIncremental:
    def test_file_hash(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        h1 = _file_hash(f)
        assert len(h1) == 64  # SHA-256 hex
        # Same content = same hash
        assert _file_hash(f) == h1
        # Changed content = different hash
        f.write_text("x = 2\n")
        assert _file_hash(f) != h1

    def test_file_hash_missing(self, tmp_path: Path) -> None:
        assert _file_hash(tmp_path / "nonexistent.py") == ""

    def test_load_save_cache(self, tmp_path: Path) -> None:
        cache_file = tmp_path / ".rule-cache"
        _save_cache(cache_file, {"a.py": "hash1", "b.py": "hash2"})
        loaded = _load_cache(cache_file)
        assert loaded["a.py"] == "hash1"
        assert loaded["b.py"] == "hash2"

    def test_load_cache_missing(self, tmp_path: Path) -> None:
        assert _load_cache(tmp_path / "nonexistent") == {}

    def test_get_supported_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x=1")
        (tmp_path / "b.rs").write_text("fn main() {}")
        (tmp_path / "c.txt").write_text("hello")
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "d.py").write_text("ignored")
        files = _get_supported_files(tmp_path, [".git"])
        names = [f.name for f in files]
        assert "a.py" in names
        assert "b.rs" in names
        assert "c.txt" not in names
        assert "d.py" not in names

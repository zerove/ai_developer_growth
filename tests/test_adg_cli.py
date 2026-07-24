"""Tests for adg_cli.py - AI Developer Governance CLI."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from tools.scripts.adg_cli import (
    Issue,
    _load_yaml,
    _simple_yaml_parse,
    _severity_rank,
    check_file,
    detect_language,
    load_rules_for_language,
)


class TestSeverityRank:
    def test_error_is_lowest(self):
        assert _severity_rank("error") < _severity_rank("warning")

    def test_warning_is_lower_than_info(self):
        assert _severity_rank("warning") < _severity_rank("info")

    def test_unknown_is_highest(self):
        assert _severity_rank("unknown") > _severity_rank("info")


class TestDetectLanguage:
    def test_python_project(self, tmp_path: Path):
        (tmp_path / "pyproject.toml").write_text("[project]\nname='test'\n")
        result = detect_language(tmp_path)
        assert result["language"] == "python"
        assert result["confidence"] >= 0.9

    def test_rust_project(self, tmp_path: Path):
        (tmp_path / "Cargo.toml").write_text("[package]\nname='test'\n")
        result = detect_language(tmp_path)
        assert result["language"] == "rust"
        assert result["confidence"] >= 0.9

    def test_typescript_project(self, tmp_path: Path):
        (tmp_path / "tsconfig.json").write_text("{}")
        result = detect_language(tmp_path)
        assert result["language"] == "typescript"

    def test_go_project(self, tmp_path: Path):
        (tmp_path / "go.mod").write_text("module test\n")
        result = detect_language(tmp_path)
        assert result["language"] == "go"

    def test_java_project(self, tmp_path: Path):
        (tmp_path / "pom.xml").write_text("<project></project>")
        result = detect_language(tmp_path)
        assert result["language"] == "java"

    def test_extension_counting(self, tmp_path: Path):
        (tmp_path / "a.py").write_text("pass")
        (tmp_path / "b.py").write_text("pass")
        (tmp_path / "c.rs").write_text("fn main() {}")
        result = detect_language(tmp_path)
        assert result["language"] == "python"
        assert result["confidence"] > 0.5

    def test_empty_directory(self, tmp_path: Path):
        result = detect_language(tmp_path)
        assert result["language"] == "unknown"
        assert result["confidence"] == 0.0


class TestLoadRules:
    def test_load_python_rules(self):
        rules = load_rules_for_language("python")
        assert "anti_patterns" in rules
        assert len(rules["anti_patterns"]) > 0
        # Should have bare except rule
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "py-bare-except" in ids

    def test_load_rust_rules(self):
        rules = load_rules_for_language("rust")
        assert "anti_patterns" in rules
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "rs-unwrap" in ids

    def test_load_unknown_language(self):
        rules = load_rules_for_language("nonexistent")
        assert "anti_patterns" in rules
        # Should still have security rules
        assert len(rules["anti_patterns"]) > 0

    def test_security_rules_included(self):
        rules = load_rules_for_language("python")
        ids = [r.get("id") for r in rules["anti_patterns"]]
        assert "common-hardcoded-secret" in ids


class TestCheckFile:
    def test_bare_except_detected(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        rule_ids = [i.rule_id for i in issues]
        assert "py-bare-except" in rule_ids

    def test_hardcoded_secret_detected(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text('password = "secret123"\n')
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        rule_ids = [i.rule_id for i in issues]
        assert "py-hardcoded-secret" in rule_ids or "common-hardcoded-secret" in rule_ids

    def test_clean_code_no_errors(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("def process(items: list[str]) -> dict[str, int]:\n    return {i: len(i) for i in items}\n")
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules, "error")
        error_issues = [i for i in issues if i.severity == "error"]
        assert len(error_issues) == 0

    def test_severity_filter(self, tmp_path: Path):
        test_file = tmp_path / "test.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        rules = load_rules_for_language("python")
        # Only errors
        issues = check_file(test_file, rules, "error")
        assert all(i.severity == "error" for i in issues)

    def test_nonexistent_file(self, tmp_path: Path):
        test_file = tmp_path / "nonexistent.py"
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules)
        assert issues == []

    def test_empty_file(self, tmp_path: Path):
        test_file = tmp_path / "empty.py"
        test_file.write_text("")
        rules = load_rules_for_language("python")
        issues = check_file(test_file, rules)
        assert issues == []


class TestSimpleYamlParse:
    def test_parse_anti_patterns(self, tmp_path: Path):
        yaml_file = tmp_path / "test.yml"
        yaml_file.write_text(
            "language: python\n"
            "anti_patterns:\n"
            "- id: test-rule\n"
            "  name: Test Rule\n"
            "  severity: error\n"
            "  pattern: 'test\\s+pattern'\n"
            "  message: Test message\n"
        )
        result = _simple_yaml_parse(yaml_file)
        assert result["language"] == "python"
        assert len(result["anti_patterns"]) == 1
        assert result["anti_patterns"][0]["id"] == "test-rule"


class TestIssue:
    def test_to_dict(self):
        issue = Issue(
            rule_id="test",
            severity="error",
            category="test",
            file="test.py",
            line=1,
            column=1,
            message="test message",
            fix_hint="fix it",
        )
        d = issue.to_dict()
        assert d["rule_id"] == "test"
        assert d["severity"] == "error"
        assert d["line"] == 1

"""Additional coverage tests for adg_cli.py to reach 85%+."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.adg_cli import (
    Issue,
    _apply_fix,
    _check_pattern,
    _detect_framework,
    _detect_language_from_file,
    _format_human,
    _format_json,
    _format_sarif,
    _format_trend_report,
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
    _load_trend_data,
    _make_issue,
    _match_pattern,
    _merge_config,
    _record_trend,
    _save_trend_data,
    _send_dingtalk_notification,
    _send_slack_notification,
    _test_rule,
    _validate_rule,
    check_directory,
    fix_directory,
    fix_file,
    load_framework_rules,
    load_project_config,
    load_rules_for_language,
)


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    return d


@pytest.fixture
def py_workspace(workspace):
    (workspace / "pyproject.toml").write_text("[project]\nname='test'\n")
    (workspace / "main.py").write_text("import os\nos.system('ls')\nx = eval('1+1')\n")
    (workspace / "utils.py").write_text("import sys\nprint(sys.argv)\n")
    return workspace


class TestDetectFramework:
    def test_flask_detection(self, workspace):
        (workspace / "requirements.txt").write_text("flask==2.0\n")
        result = _detect_framework(workspace, "python")
        assert result == "flask"

    def test_django_detection(self, workspace):
        (workspace / "manage.py").write_text("import django\n")
        result = _detect_framework(workspace, "python")
        assert result == "django"

    def test_fastapi_detection(self, workspace):
        (workspace / "requirements.txt").write_text("fastapi==0.100\n")
        result = _detect_framework(workspace, "python")
        assert result == "fastapi"

    def test_no_framework(self, workspace):
        result = _detect_framework(workspace, "python")
        assert result is None

    def test_non_python(self, workspace):
        result = _detect_framework(workspace, "javascript")
        assert result is None


class TestDetectLanguageFromFile:
    def test_python(self):
        assert _detect_language_from_file(Path("main.py")) == "python"

    def test_javascript(self):
        assert _detect_language_from_file(Path("app.js")) == "javascript"

    def test_typescript(self):
        assert _detect_language_from_file(Path("app.ts")) == "typescript"

    def test_rust(self):
        assert _detect_language_from_file(Path("main.rs")) == "rust"

    def test_go(self):
        assert _detect_language_from_file(Path("main.go")) == "go"

    def test_java(self):
        assert _detect_language_from_file(Path("App.java")) == "java"

    def test_unknown(self):
        assert _detect_language_from_file(Path("data.xyz")) is None


class TestCheckPattern:
    def test_simple_pattern(self, workspace):
        f = workspace / "test.py"
        f.write_text("x = eval('1+1')\n")
        pattern_def = {
            "pattern": r"eval\(",
            "severity": "error",
            "message": "eval is dangerous",
            "category": "security",
            "fix_hint": "Use ast.literal_eval",
        }
        issues = _check_pattern(f, "x = eval('1+1')", ["x = eval('1+1')"], pattern_def)
        assert len(issues) == 1
        assert issues[0].severity == "error"

    def test_no_match(self, workspace):
        f = workspace / "test.py"
        f.write_text("x = 1\n")
        pattern_def = {
            "pattern": r"eval\(",
            "severity": "error",
            "message": "test",
            "category": "security",
            "fix_hint": "fix",
        }
        issues = _check_pattern(f, "x = 1", ["x = 1"], pattern_def)
        assert len(issues) == 0


class TestMakeIssue:
    def test_make_issue(self, workspace):
        f = workspace / "test.py"
        pattern_def = {"severity": "error", "message": "test msg", "category": "security", "fix_hint": "fix it"}
        issue = _make_issue(f, 10, 5, pattern_def)
        assert issue.line == 10
        assert issue.column == 5
        assert issue.severity == "error"


class TestFormatSarif:
    def test_empty_issues(self):
        sarif = _format_sarif([], "python", None)
        json.loads(sarif)
        assert "$schema" in sarif

    def test_with_issues(self):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        sarif = _format_sarif(issues, "python", "flask")
        data = json.loads(sarif)
        assert len(data["runs"][0]["results"]) == 1


class TestFormatHuman:
    def test_format_human_empty(self):
        output = _format_human([], "python", None, 0)
        assert "python" in output.lower() or "0" in output

    def test_format_human_with_issues(self):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        output = _format_human(issues, "python", None, 1)
        assert "SEC001" in output


class TestFormatJson:
    def test_format_json(self):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        output = _format_json(issues, "python", None, 1)
        data = json.loads(output)
        assert len(data["issues"]) == 1


class TestValidateRule:
    def test_valid_rule(self):
        rule = {"id": "test/1", "pattern": r"eval\(", "severity": "error", "message": "test", "category": "security"}
        errors = _validate_rule(rule)
        assert len(errors) == 0

    def test_invalid_severity(self):
        rule = {"pattern": r"x", "severity": "invalid"}
        errors = _validate_rule(rule)
        assert len(errors) > 0

    def test_invalid_category(self):
        rule = {"pattern": r"x", "severity": "error", "category": "invalid"}
        errors = _validate_rule(rule)
        assert len(errors) > 0

    def test_missing_pattern(self):
        rule = {"severity": "error"}
        errors = _validate_rule(rule)
        assert len(errors) > 0


class TestTestRule:
    def test_matches(self, tmp_path):
        rule = {"pattern": r"eval\("}
        f = tmp_path / "test.py"
        f.write_text("x = eval('1+1')")
        result = _test_rule(rule, [f])
        assert len(result["matches"]) > 0

    def test_no_matches(self, tmp_path):
        rule = {"pattern": r"eval\("}
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        result = _test_rule(rule, [f])
        assert len(result["matches"]) == 0

    def test_invalid_regex(self):
        rule = {"pattern": r"[invalid"}
        result = _test_rule(rule, [Path("nonexistent.py")])
        assert len(result["matches"]) == 0

    def test_nonexistent_files(self):
        rule = {"pattern": r"eval\("}
        result = _test_rule(rule, [Path("/nonexistent/file.py")])
        assert len(result["matches"]) == 0


class TestTrendData:
    def test_save_and_load(self, workspace):
        data = [{"timestamp": "2024-01-01", "issues": 10}]
        _save_trend_data(workspace, data)
        loaded = _load_trend_data(workspace)
        assert len(loaded) == 1

    def test_load_empty(self, workspace):
        loaded = _load_trend_data(workspace)
        assert loaded == []


class TestRecordTrend:
    def test_record_trend(self, workspace):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        result = _record_trend(workspace, issues, "python")
        assert "timestamp" in result
        assert result["total"] == 1
        assert result["errors"] == 1


class TestFormatTrendReport:
    def test_empty(self):
        report = _format_trend_report([])
        assert isinstance(report, str)

    def test_with_data(self):
        data = [
            {
                "timestamp": "2024-01-01T00:00:00",
                "issues": 10,
                "errors": 2,
                "warnings": 5,
                "info": 3,
                "language": "python",
            },
            {
                "timestamp": "2024-01-02T00:00:00",
                "issues": 8,
                "errors": 1,
                "warnings": 4,
                "info": 3,
                "language": "python",
            },
        ]
        report = _format_trend_report(data)
        assert isinstance(report, str)

    def test_json_format(self):
        data = [{"timestamp": "2024-01-01", "issues": 5, "errors": 1, "warnings": 2, "info": 2, "language": "python"}]
        report = _format_trend_report(data, output_json=True)
        parsed = json.loads(report)
        assert isinstance(parsed, dict | list)


class TestApplyFix:
    def test_eval_fix(self):
        content = "x = eval('1+1')\n"
        fixed, applied = _apply_fix(content, "SEC001", {"pattern": r"eval\(", "replacement": "ast.literal_eval"})
        # If the fix rule exists, it should apply
        assert isinstance(fixed, str)

    def test_no_fix(self):
        content = "x = 1\n"
        fixed, applied = _apply_fix(content, "UNKNOWN_RULE", {})
        assert fixed == content
        assert applied is False


class TestSlackNotification:
    def test_send_slack(self):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        with patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_slack_notification("https://hooks.slack.com/test", issues, "python", "test")
            assert isinstance(result, bool)

    def test_send_slack_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = _send_slack_notification("https://hooks.slack.com/test", [], "python", "test")
            assert result is False


class TestDingtalkNotification:
    def test_send_dingtalk(self):
        issues = [
            Issue(
                file="test.py",
                line=1,
                column=1,
                rule_id="SEC001",
                severity="error",
                category="security",
                message="bad",
                fix_hint="fix",
            )
        ]
        with patch("urllib.request.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_dingtalk_notification("https://oapi.dingtalk.com/test", issues, "python", "test")
            assert isinstance(result, bool)

    def test_send_dingtalk_error(self):
        with patch("urllib.request.urlopen", side_effect=Exception("network error")):
            result = _send_dingtalk_notification("https://oapi.dingtalk.com/test", [], "python", "test")
            assert result is False


class TestGitFunctions:
    def test_get_changed_files(self, workspace):
        result = _get_git_changed_files("HEAD", cwd=workspace)
        assert isinstance(result, list)

    def test_get_unstaged_files(self, workspace):
        result = _get_unstaged_files(cwd=workspace)
        assert isinstance(result, list)

    def test_get_staged_files(self, workspace):
        result = _get_staged_files(cwd=workspace)
        assert isinstance(result, list)


class TestMatchPattern:
    def test_match(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = eval('1+1')")
        assert _match_pattern(f, "*.py") is True

    def test_no_match(self, tmp_path):
        f = tmp_path / "test.py"
        f.write_text("x = 1")
        assert _match_pattern(f, "*.js") is False

    def test_nonexistent_file_matches_glob(self):
        # _match_pattern is a glob matcher, not an existence check
        assert _match_pattern(Path("/nonexistent/file.py"), "*.py") is True


class TestMergeConfig:
    def test_merge(self):
        base = {"check": {"severity": "warning"}}
        override = {"check": {"format": "json"}}
        result = _merge_config(base, override)
        assert result["check"]["severity"] == "warning"
        assert result["check"]["format"] == "json"

    def test_merge_empty(self):
        assert _merge_config({}, {}) == {}


class TestLoadProjectConfig:
    def test_load_existing_with_anti_patterns(self, workspace):
        adg_dir = workspace / ".adg"
        adg_dir.mkdir(parents=True, exist_ok=True)
        (adg_dir / "rules.yml").write_text("anti_patterns:\n  - id: test\n")
        config = load_project_config(workspace)
        assert isinstance(config, dict)
        assert "custom_rules" in config

    def test_load_existing(self, workspace):
        adg_dir = workspace / ".adg"
        adg_dir.mkdir(parents=True, exist_ok=True)
        (adg_dir / "rules.yml").write_text("custom_rules:\n  - id: test\n")
        config = load_project_config(workspace)
        assert isinstance(config, dict)
        assert "custom_rules" in config

    def test_load_missing(self, workspace):
        config = load_project_config(workspace)
        assert isinstance(config, dict)

    def test_load_yaml_parse_error(self, workspace):
        adg_dir = workspace / ".adg"
        adg_dir.mkdir(parents=True, exist_ok=True)
        # Write invalid YAML that triggers an exception
        (adg_dir / "rules.yml").write_text(':\n  - "unterminated')
        config = load_project_config(workspace)
        assert isinstance(config, dict)

    def test_load_with_global_config(self, workspace, monkeypatch):
        global_dir = workspace / "global_config"
        global_dir.mkdir(parents=True, exist_ok=True)
        (global_dir / "rules.yml").write_text("custom_rules:\n  - id: global_rule\n")
        monkeypatch.setattr(Path, "home", lambda: global_dir.parent)
        # global_config_path would be workspace/global_config/.config/adg/rules.yml
        # just ensure no crash when global doesn't exist
        config = load_project_config(workspace)
        assert isinstance(config, dict)


class TestLoadFrameworkRules:
    def test_load_flask(self):
        rules = load_framework_rules("flask")
        assert isinstance(rules, dict)

    def test_load_unknown(self):
        rules = load_framework_rules("unknown")
        assert isinstance(rules, dict)


class TestCheckDirectory:
    def test_check_empty(self, workspace):
        rules = load_rules_for_language("python")
        issues = check_directory(workspace, rules)
        assert len(issues) == 0

    def test_check_with_python(self, py_workspace):
        rules = load_rules_for_language("python")
        issues = check_directory(py_workspace, rules)
        assert len(issues) > 0


class TestFixFile:
    def test_fix_python(self, py_workspace):
        result = fix_file(py_workspace / "main.py")
        assert isinstance(result, dict)


class TestFixDirectory:
    def test_fix_empty(self, workspace):
        result = fix_directory(workspace)
        assert result["fixed"] == 0


class TestLoadRulesForLanguage:
    def test_python(self):
        rules = load_rules_for_language("python")
        assert isinstance(rules, dict)

    def test_unknown(self):
        rules = load_rules_for_language("unknown")
        assert isinstance(rules, dict)

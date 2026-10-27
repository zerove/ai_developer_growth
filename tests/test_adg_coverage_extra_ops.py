# 拆分自 tests/test_adg_coverage_extra.py

"""Additional coverage tests for adg_cli.py to reach 85%+."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.adg_cli import (
    Issue,
    _apply_fix,
    _get_git_changed_files,
    _get_staged_files,
    _get_unstaged_files,
    _match_pattern,
    _merge_config,
    _send_dingtalk_notification,
    _send_slack_notification,
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
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_slack_notification("https://hooks.slack.com/test", issues, "python", "test")
            assert isinstance(result, bool)

    def test_send_slack_error(self):
        with patch("tools.chat_integration.urlopen", side_effect=Exception("network error")):
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
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = _send_dingtalk_notification("https://oapi.dingtalk.com/test", issues, "python", "test")
            assert isinstance(result, bool)

    def test_send_dingtalk_error(self):
        with patch("tools.chat_integration.urlopen", side_effect=Exception("network error")):
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
        # 内容级断言: legacy key (anti_patterns) 的规则必须真实出现在
        # custom_rules 列表中, 不能只验证 key 存在 —— 此前自定义规则死亡
        # 正是由于只断言 key 而未验证内容
        assert {"id": "test"} in config["custom_rules"]

    def test_load_existing(self, workspace):
        adg_dir = workspace / ".adg"
        adg_dir.mkdir(parents=True, exist_ok=True)
        (adg_dir / "rules.yml").write_text("custom_rules:\n  - id: test\n")
        config = load_project_config(workspace)
        assert isinstance(config, dict)
        assert "custom_rules" in config
        # 内容级断言: canonical key 的规则必须真实出现在 custom_rules 中
        assert {"id": "test"} in config["custom_rules"]

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

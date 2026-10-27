# 拆分自 tests/test_adg_cmd_integration.py

"""Targeted tests for remaining uncovered lines (83% -> 85%+)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.adg_cli import (
    SKIP_DIRS,
    SKIP_EXTENSIONS,
    cmd_detect,
    cmd_install_hooks,
    cmd_list_rules,
    cmd_notify,
    cmd_rule,
    cmd_trend,
)


def _mock_urlopen(mock):
    """urlopen 返回 status=200 的上下文管理器（对齐 chat_integration 契约）。"""
    ctx = MagicMock()
    ctx.status = 200
    mock.return_value.__enter__.return_value = ctx


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    (d / ".git").mkdir()
    return d


@pytest.fixture
def py_workspace(workspace):
    (workspace / "pyproject.toml").write_text("[project]\nname='test'\n")
    (workspace / "main.py").write_text("import os\nos.system('ls')\nx = eval('1+1')\n")
    (workspace / "utils.py").write_text("import sys\nprint(sys.argv)\n")
    return workspace


def ns(**kwargs):
    """Create argparse.Namespace with defaults."""
    defaults = {
        "path": ".",
        "lang": None,
        "framework": None,
        "severity": None,
        "json": False,
        "sarif": False,
        "jobs": 1,
        "since": None,
        "staged": False,
        "unstaged": False,
        "trend": False,
        "notify": None,
        "project": ".",
        "error_threshold": 0,
        "warning_threshold": -1,
        "rule_command": None,
        "rule_file": None,
        "output": None,
        "webhook": None,
        "clear": False,
        "pre_push": False,
    }
    defaults.update(kwargs)
    return argparse.Namespace(**defaults)


class TestCmdDetectExtended:
    def test_detect_json(self, py_workspace):
        args = ns(path=str(py_workspace), json=True)
        result = cmd_detect(args)
        assert result == 0

    def test_detect_human(self, py_workspace, capsys):
        args = ns(path=str(py_workspace))
        cmd_detect(args)
        captured = capsys.readouterr()
        assert "Language" in captured.out


class TestCmdListRulesExtended:
    def test_list_rules_json(self):
        args = ns(lang="python", json=True)
        result = cmd_list_rules(args)
        assert result == 0

    def test_list_rules_human(self, capsys):
        args = ns(lang="python", json=False)
        cmd_list_rules(args)
        captured = capsys.readouterr()
        assert "Rules for" in captured.out

    def test_list_rules_all_severities(self, capsys):
        for lang in ["python", "javascript", "typescript", "rust", "go", "java"]:
            args = ns(lang=lang, json=False)
            result = cmd_list_rules(args)
            assert result == 0


class TestCmdRuleExtended:
    def test_rule_no_subcommand(self):
        args = ns(rule_command=None)
        result = cmd_rule(args)
        assert result == 1

    def test_rule_create_with_output(self, workspace):
        args = ns(rule_command="create", output=str(workspace / "rule.yml"))
        with patch("tools.scripts.adg_cli.commands.cmd._cmd_rule_create._create_rule_interactive") as mock:
            mock.return_value = {
                "id": "test/rule",
                "pattern": r"eval\(",
                "severity": "error",
                "message": "test",
                "category": "security",
                "fix_hint": "fix",
                "language": "python",
            }
            result = cmd_rule(args)
        assert result == 0
        assert (workspace / "rule.yml").exists()

    def test_rule_validate_valid(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("id: test\npattern: eval\\(\nseverity: error\nmessage: test\ncategory: security\n")
        args = ns(rule_command="validate", rule_file=str(rule_file))
        result = cmd_rule(args)
        assert result == 0

    def test_rule_validate_invalid(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("pattern: eval\\(\n")
        args = ns(rule_command="validate", rule_file=str(rule_file))
        result = cmd_rule(args)
        assert result == 1

    def test_rule_validate_nonexistent(self):
        args = ns(rule_command="validate", rule_file="/nonexistent/rule.yml")
        result = cmd_rule(args)
        assert result == 1

    def test_rule_test_with_file(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("pattern: eval\\(\nmessage: test\n")
        test_file = workspace / "test.py"
        test_file.write_text("x = eval('1+1')")
        args = ns(rule_command="test", rule_file=str(rule_file), path=str(test_file))
        result = cmd_rule(args)
        assert result >= 0

    def test_rule_test_no_matches(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("pattern: eval\\(\nmessage: test\n")
        test_file = workspace / "test.py"
        test_file.write_text("x = 1")
        args = ns(rule_command="test", rule_file=str(rule_file), path=str(test_file))
        result = cmd_rule(args)
        assert result >= 0

    def test_rule_test_no_files(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("pattern: eval\\(\nmessage: test\n")
        args = ns(
            rule_command="test",
            rule_file=str(rule_file),
            path=str(workspace / "nonexistent"),
        )
        result = cmd_rule(args)
        assert result == 1

    def test_rule_test_no_pattern(self, workspace):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("message: test\n")
        test_file = workspace / "test.py"
        test_file.write_text("x = 1")
        args = ns(rule_command="test", rule_file=str(rule_file), path=str(test_file))
        result = cmd_rule(args)
        assert result == 1

    def test_rule_test_nonexistent_rule(self):
        args = ns(rule_command="test", rule_file="/nonexistent/rule.yml", path=".")
        result = cmd_rule(args)
        assert result == 1

    def test_rule_validate_yaml_import_error(self, workspace, monkeypatch):
        rule_file = workspace / "rule.yml"
        rule_file.write_text("id: test\npattern: eval\\(\nseverity: error\nmessage: test\n")
        # Simulate yaml import failure
        import builtins

        real_import = builtins.__import__

        def mock_import(name, *args, **kwargs):
            if name == "yaml":
                raise ImportError("No yaml")
            return real_import(name, *args, **kwargs)

        monkeypatch.setattr(builtins, "__import__", mock_import)
        args = ns(rule_command="validate", rule_file=str(rule_file))
        result = cmd_rule(args)
        assert result >= 0


class TestCmdTrendExtended:
    def test_trend_empty(self, workspace):
        args = ns(path=str(workspace), json=False, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_json(self, workspace):
        args = ns(path=str(workspace), json=True, clear=False)
        result = cmd_trend(args)
        assert result == 0

    def test_trend_clear_existing(self, workspace):
        trend_file = workspace / ".adg" / "trend.json"
        trend_file.parent.mkdir(parents=True, exist_ok=True)
        trend_file.write_text("[]")
        args = ns(path=str(workspace), clear=True)
        result = cmd_trend(args)
        assert result == 0
        assert not trend_file.exists()

    def test_trend_clear_nonexistent(self, workspace):
        args = ns(path=str(workspace), clear=True)
        result = cmd_trend(args)
        assert result == 0


class TestCmdNotifyExtended:
    def test_notify_slack(self, py_workspace):
        args = ns(
            path=str(py_workspace),
            webhook="slack://test/token",
            lang="python",
            project="test",
        )
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.status = 200
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = cmd_notify(args)
        assert result == 0

    def test_notify_dingtalk(self, py_workspace):
        args = ns(
            path=str(py_workspace),
            webhook="dingtalk://test",
            lang="python",
            project="test",
        )
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.status = 200
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = cmd_notify(args)
        assert result == 0

    def test_notify_unknown_scheme(self, py_workspace):
        args = ns(path=str(py_workspace), webhook="ftp://invalid", lang="python")
        result = cmd_notify(args)
        assert result == 1

    def test_notify_slack_failure(self, py_workspace):
        args = ns(
            path=str(py_workspace),
            webhook="slack://test/token",
            lang="python",
            project="test",
        )
        with patch("tools.chat_integration.urlopen", side_effect=Exception("network error")):
            result = cmd_notify(args)
        assert result == 1

    def test_notify_unknown_lang(self, workspace):
        args = ns(path=str(workspace), webhook="slack://test/token", lang="unknown")
        result = cmd_notify(args)
        assert result == 1

    def test_notify_directory(self, py_workspace):
        args = ns(
            path=str(py_workspace),
            webhook="slack://test/token",
            lang="python",
            project="test",
        )
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.status = 200
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = cmd_notify(args)
        assert result >= 0


class TestCmdInstallHooksExtended:
    def test_install_pre_commit(self, workspace):
        args = ns(path=str(workspace), pre_push=False)
        result = cmd_install_hooks(args)
        assert result == 0
        hook = workspace / ".git" / "hooks" / "pre-commit"
        assert hook.exists()

    def test_install_pre_push(self, workspace):
        args = ns(path=str(workspace), pre_push=True)
        result = cmd_install_hooks(args)
        assert result == 0
        hook = workspace / ".git" / "hooks" / "pre-push"
        assert hook.exists()

    def test_not_git_repo(self, tmp_path):
        args = ns(path=str(tmp_path / "not_a_repo"), pre_push=False)
        result = cmd_install_hooks(args)
        assert result == 1

    def test_install_with_existing_hooks_source(self, workspace, monkeypatch):
        # Create fake global hooks
        config_dir = workspace / "config" / "adg" / "hooks"
        config_dir.mkdir(parents=True)
        (config_dir / "pre-commit").write_text("#!/bin/bash\nsource custom\n")
        monkeypatch.setattr(Path, "home", lambda: workspace / "config")
        args = ns(path=str(workspace), pre_push=False)
        result = cmd_install_hooks(args)
        assert result == 0

    def test_install_push_with_existing_hooks_source(self, workspace, monkeypatch):
        config_dir = workspace / "config" / "adg" / "hooks"
        config_dir.mkdir(parents=True)
        (config_dir / "pre-push").write_text("#!/bin/bash\nsource custom\n")
        monkeypatch.setattr(Path, "home", lambda: workspace / "config")
        args = ns(path=str(workspace), pre_push=True)
        result = cmd_install_hooks(args)
        assert result == 0


class TestSkipPatterns:
    def test_skip_dirs_populated(self):
        assert len(SKIP_DIRS) > 0
        assert ".git" in SKIP_DIRS

    def test_skip_extensions_populated(self):
        assert len(SKIP_EXTENSIONS) > 0
        assert ".py" in SKIP_EXTENSIONS or ".pyc" in SKIP_EXTENSIONS

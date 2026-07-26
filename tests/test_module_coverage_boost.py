"""Extended coverage tests for tools modules.

Covers: fix_engine, multiproject, chat_integration, dashboard, cicd
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


# ─────────────────────────────────────────────────────────────
# fix_engine
# ─────────────────────────────────────────────────────────────


class TestFixEngine:
    """Test FixEngine class comprehensively."""

    def test_init_default(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        assert isinstance(engine.fixes, dict)

    def test_init_with_extra_fixes(self):
        from tools.fix_engine import FixEngine

        extra = {"python": {"custom-rule": {"pattern": r"pass", "replacement": "raise NotImplementedError"}}}
        engine = FixEngine(extra_fixes=extra)
        assert "custom-rule" in engine.fixes["python"]

    def test_get_fixes_for_language(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        fixes = engine.get_fixes_for_language("python")
        assert isinstance(fixes, dict)

    def test_get_fixes_unknown_language(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        fixes = engine.get_fixes_for_language("brainfuck")
        assert fixes == {}

    def test_fix_content_no_match(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        content = "x = 42\n"
        fixed, applied = engine.fix_content(content, "python")
        assert fixed == content

    def test_fix_content_dry_run(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        content = "except:\n    pass\n"
        fixed, applied = engine.fix_content(content, "python", dry_run=True)
        # In dry run, content should not change
        assert fixed == content

    def test_fix_content_with_rule_filter(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        content = "except:\n    pass\n"
        fixed, applied = engine.fix_content(content, "python", rule_ids=["nonexistent-rule"])
        assert len(applied) == 0

    def test_fix_file_not_found(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        result = engine.fix_file("/nonexistent/file.py")
        assert result["success"] is False

    def test_fix_file_unknown_language(self, tmp_path):
        from tools.fix_engine import FixEngine

        f = tmp_path / "test.xyz"
        f.write_text("hello")
        engine = FixEngine()
        result = engine.fix_file(f)
        assert result["success"] is False

    def test_fix_file_python(self, tmp_path):
        from tools.fix_engine import FixEngine

        f = tmp_path / "test.py"
        f.write_text("except:\n    pass\n")
        engine = FixEngine()
        result = engine.fix_file(f)
        assert result["success"] is True
        assert result["language"] == "python"

    def test_fix_file_dry_run(self, tmp_path):
        from tools.fix_engine import FixEngine

        f = tmp_path / "test.py"
        f.write_text("except:\n    pass\n")
        original = f.read_text()
        engine = FixEngine()
        result = engine.fix_file(f, dry_run=True)
        assert result["success"] is True
        assert result["dry_run"] is True
        # File should not be modified
        assert f.read_text() == original

    def test_fix_directory_not_found(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        result = engine.fix_directory("/nonexistent/dir")
        assert result["success"] is False

    def test_fix_directory(self, tmp_path):
        from tools.fix_engine import FixEngine

        (tmp_path / "a.py").write_text("except:\n    pass\n")
        (tmp_path / "b.txt").write_text("not python")
        engine = FixEngine()
        result = engine.fix_directory(tmp_path)
        assert result["success"] is True
        assert result["files_checked"] >= 1

    def test_fix_directory_with_language(self, tmp_path):
        from tools.fix_engine import FixEngine

        (tmp_path / "a.py").write_text("except:\n    pass\n")
        engine = FixEngine()
        result = engine.fix_directory(tmp_path, language="python")
        assert result["success"] is True

    def test_fix_directory_skip_dirs(self, tmp_path):
        from tools.fix_engine import FixEngine

        nm = tmp_path / "node_modules" / "pkg"
        nm.mkdir(parents=True)
        (nm / "index.js").write_text("var x = 1;")
        (tmp_path / "app.py").write_text("x = 1\n")
        engine = FixEngine()
        result = engine.fix_directory(tmp_path)
        assert result["success"] is True


class TestLoadCustomFixes:
    """Test load_custom_fixes and save_custom_fix."""

    def test_load_no_file(self, tmp_path):
        from tools.fix_engine import load_custom_fixes

        result = load_custom_fixes(tmp_path)
        assert result == {}

    def test_load_with_file(self, tmp_path):
        from tools.fix_engine import load_custom_fixes

        adg = tmp_path / ".adg"
        adg.mkdir()
        (adg / "fixes.yml").write_text("fixes:\n  python:\n    test-rule:\n      pattern: pass\n      replacement: raise\n")
        result = load_custom_fixes(tmp_path)
        assert "test-rule" in result.get("python", {})

    def test_save_custom_fix(self, tmp_path):
        from tools.fix_engine import save_custom_fix

        result = save_custom_fix(
            tmp_path, "python", "my-rule", r"pass", "raise NotImplementedError", "test fix"
        )
        assert result is True
        assert (tmp_path / ".adg" / "fixes.yml").exists()

    def test_save_custom_fix_append(self, tmp_path):
        from tools.fix_engine import save_custom_fix

        save_custom_fix(tmp_path, "python", "rule1", r"pass", "raise", "")
        save_custom_fix(tmp_path, "python", "rule2", r"\.\.\.", "raise NotImplementedError", "")
        from tools.fix_engine import load_custom_fixes

        fixes = load_custom_fixes(tmp_path)
        assert "rule1" in fixes["python"]
        assert "rule2" in fixes["python"]


# ─────────────────────────────────────────────────────────────
# multiproject
# ─────────────────────────────────────────────────────────────


class TestMultiproject:
    """Test multiproject module."""

    def test_import(self):
        from tools.multiproject import MonorepoChecker

        assert MonorepoChecker is not None

    def test_checker_init(self, tmp_path):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(root_dir=tmp_path)
        assert checker is not None

    def test_discover_projects(self, tmp_path):
        from tools.multiproject import MonorepoChecker

        (tmp_path / "pyproject.toml").write_text("[project]\nname='a'\n")
        sub = tmp_path / "packages" / "b"
        sub.mkdir(parents=True)
        (sub / "pyproject.toml").write_text("[project]\nname='b'\n")
        checker = MonorepoChecker(root_dir=tmp_path)
        projects = checker.discover_projects()
        assert len(projects) >= 1

    def test_check_project(self, tmp_path):
        from tools.multiproject import MonorepoChecker

        (tmp_path / "pyproject.toml").write_text("[project]\nname='a'\n")
        checker = MonorepoChecker(root_dir=tmp_path)
        projects = checker.discover_projects()
        if projects:
            result = checker.check_project(projects[0])
            assert result is not None


# ─────────────────────────────────────────────────────────────
# chat_integration
# ─────────────────────────────────────────────────────────────


class TestChatIntegration:
    """Test chat integration module."""

    def test_import_slack(self):
        from tools.chat_integration import SlackNotifier

        assert SlackNotifier is not None

    def test_slack_notifier_init(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        assert notifier.webhook_url == "https://hooks.slack.com/test"

    def test_slack_send_report(self):
        from tools.chat_integration import SlackNotifier
        from tools.scripts.rules_engine.models import Issue

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        issues = [
            Issue(rule_id="r1", severity="error", category="security", file="a.py", line=1, message="e1"),
            Issue(rule_id="r2", severity="warning", category="quality", file="a.py", line=2, message="w1"),
        ]
        with patch.object(notifier, "_post", return_value=True):
            result = notifier.send_report(
                title="Test Report",
                project="test-project",
                language="python",
                issues=issues,
            )
            assert result is True

    def test_slack_send_report_no_issues(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        with patch.object(notifier, "_post", return_value=True):
            result = notifier.send_report(
                title="Clean Report",
                project="test",
                language="python",
                issues=[],
            )
            assert result is True

    def test_slack_send_alert(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        with patch.object(notifier, "_post", return_value=True):
            result = notifier.send_alert("Test alert", level="error")
            assert result is True

    def test_slack_send_alert_levels(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier(webhook_url="https://hooks.slack.com/test")
        for level in ["error", "warning", "info", "unknown"]:
            with patch.object(notifier, "_post", return_value=True):
                notifier.send_alert("msg", level=level)

    def test_import_feishu(self):
        from tools.chat_integration import FeishuNotifier

        assert FeishuNotifier is not None

    def test_feishu_notifier_init(self):
        from tools.chat_integration import FeishuNotifier

        notifier = FeishuNotifier(webhook_url="https://open.feishu.cn/test")
        assert notifier.webhook_url == "https://open.feishu.cn/test"

    def test_feishu_send_report(self):
        from tools.chat_integration import FeishuNotifier
        from tools.scripts.rules_engine.models import Issue

        notifier = FeishuNotifier(webhook_url="https://open.feishu.cn/test")
        issues = [
            Issue(rule_id="r1", severity="error", category="security", file="a.py", line=1, message="e1"),
        ]
        with patch.object(notifier, "_post", return_value=True):
            result = notifier.send_report(
                title="Test",
                project="proj",
                language="python",
                issues=issues,
            )
            assert result is True


# ─────────────────────────────────────────────────────────────
# dashboard
# ─────────────────────────────────────────────────────────────


class TestDashboard:
    """Test dashboard module."""

    def test_import(self):
        from tools.dashboard import generate_dashboard_html

        assert callable(generate_dashboard_html)

    def test_generate_html(self, tmp_path):
        from tools.dashboard import generate_dashboard_html

        result = generate_dashboard_html(tmp_path)
        assert isinstance(result, str)
        assert len(result) > 0

    def test_generate_static_html(self, tmp_path):
        from tools.dashboard import generate_dashboard_html

        output = tmp_path / "dashboard.html"
        generate_dashboard_html(tmp_path, str(output))
        assert output.exists()
        content = output.read_text()
        assert len(content) > 0


# ─────────────────────────────────────────────────────────────
# cicd
# ─────────────────────────────────────────────────────────────


class TestCICD:
    """Test CI/CD module."""

    def test_list_templates(self):
        from tools.cicd import list_templates

        templates = list_templates()
        assert isinstance(templates, list)

    def test_get_template(self):
        from tools.cicd import get_template

        templates = __import__("tools.cicd", fromlist=["list_templates"]).list_templates()
        if templates:
            content = get_template(templates[0])
            assert content is not None

    def test_format_template_info(self):
        from tools.cicd import format_template_info

        info = format_template_info()
        assert isinstance(info, str)

    def test_generate_ci_config(self):
        from tools.cicd import generate_ci_config

        result = generate_ci_config("github", "python")
        assert isinstance(result, str)
        assert len(result) > 0


# ─────────────────────────────────────────────────────────────
# report
# ─────────────────────────────────────────────────────────────


class TestReport:
    """Test report module."""

    def test_generate_html_report(self):
        from tools.report import generate_html_report

        assert callable(generate_html_report)

    def test_save_html_report(self):
        from tools.report import save_html_report

        assert callable(save_html_report)

# 拆分自 tests/test_adg_new_modules.py

"""Tests for new ADG modules: HTML report, AI recommender, marketplace, multiproject, fix engine, chat integration, dashboard, cicd, benchmarks, LSP."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.adg_cli import Issue


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    (d / ".git").mkdir()
    (d / "pyproject.toml").write_text("[project]\nname='test'\n")
    (d / "main.py").write_text("import os\nos.system('ls')\nx = eval('1+1')\nimport pickle\n")
    (d / "utils.py").write_text("import sys\nprint(sys.argv)\n")
    return d


class TestFixEngine:
    def test_fix_content_python(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        content = "x = eval('1+1')\n"
        fixed, applied = engine.fix_content(content, "python", ["SEC001"])
        assert len(applied) > 0
        assert "ast.literal_eval" in fixed

    def test_fix_content_javascript(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        content = "var x = 1;\n"
        fixed, applied = engine.fix_content(content, "javascript", ["CQ010"])
        assert len(applied) > 0

    def test_fix_file(self, tmp_path):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        f = tmp_path / "test.py"
        f.write_text("x = eval('1+1')\n")
        result = engine.fix_file(f, dry_run=True)
        assert result["success"] is True
        assert result["dry_run"] is True

    def test_fix_file_nonexistent(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        result = engine.fix_file("/nonexistent/file.py")
        assert result["success"] is False

    def test_fix_file_rejects_syntax_breaking_result(self, tmp_path):
        """ADR-072: 正则改坏语法时必须拒绝写盘且如实回报失败.

        ``fixes.yml`` 的 ``os\\.system\\(([^)]+)\\)`` 遇嵌套括号即在
        第一个 ``)`` 处截断, 这是规则自带的缺陷, 无需注入。
        """
        from tools.fix_engine import FixEngine

        src = "import os\ncmd = os.system(get_cmd())\n"
        f = tmp_path / "broken.py"
        f.write_text(src)

        result = FixEngine().fix_file(f, "python")

        assert result["success"] is False, "改坏语法却报告成功"
        assert result["fixes_applied"] == 0
        assert result.get("syntax_violation") is True
        assert "拒绝写盘" in result["error"]
        assert f.read_text() == src, "磁盘被改坏了"

    def test_fix_file_control_healthy_still_fixed(self, tmp_path):
        """对照组: 合法样本照常修复 —— 兜底不得变成永不修复."""
        from tools.fix_engine import FixEngine

        f = tmp_path / "ok.py"
        f.write_text("import os\ncmd = os.system('ls')\n")

        result = FixEngine().fix_file(f, "python")

        assert result["success"] is True
        assert result["fixes_applied"] >= 1
        assert "subprocess.run" in f.read_text()

    def test_fix_directory(self, tmp_path):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        (tmp_path / "a.py").write_text("x = eval('1+1')\n")
        (tmp_path / "b.py").write_text("print('hello')\n")
        result = engine.fix_directory(tmp_path, dry_run=True)
        assert result["success"] is True
        assert result["files_checked"] >= 2

    def test_get_fixes_for_language(self):
        from tools.fix_engine import FixEngine

        engine = FixEngine()
        fixes = engine.get_fixes_for_language("python")
        assert len(fixes) > 0
        assert "SEC001" in fixes


class TestChatIntegration:
    def test_create_slack_notifier(self):
        from tools.chat_integration import SlackNotifier, create_notifier

        notifier = create_notifier("https://hooks.slack.com/services/T/B")
        assert isinstance(notifier, SlackNotifier)

    def test_create_feishu_notifier(self):
        from tools.chat_integration import FeishuNotifier, create_notifier

        notifier = create_notifier("https://open.feishu.cn/open-apis/bot/v2/hook/xxx")
        assert isinstance(notifier, FeishuNotifier)

    def test_create_dingtalk_notifier(self):
        from tools.chat_integration import DingTalkNotifier, create_notifier

        notifier = create_notifier("https://oapi.dingtalk.com/robot/send?access_token=xxx")
        assert isinstance(notifier, DingTalkNotifier)

    def test_send_report(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier("https://hooks.slack.com/test")
        issues = [Issue("SEC001", "error", "security", "main.py", 1, 1, "eval", "fix")]
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = notifier.send_report(issues, "python", "test-project")
            assert isinstance(result, bool)

    def test_send_alert(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier("https://hooks.slack.com/test")
        with patch("tools.chat_integration.urlopen") as mock:
            mock.return_value.__enter__ = lambda s: s
            mock.return_value.__exit__ = MagicMock(return_value=False)
            result = notifier.send_alert("Test alert", "warning")
            assert isinstance(result, bool)

    def test_send_report_failure(self):
        from tools.chat_integration import SlackNotifier

        notifier = SlackNotifier("https://hooks.slack.com/test")
        with patch("tools.chat_integration.urlopen", side_effect=Exception("network")):
            result = notifier.send_report([], "python")
            assert result is False


class TestDashboard:
    def test_generate_dashboard_html(self, workspace):
        from tools.dashboard import generate_dashboard_html

        html = generate_dashboard_html(workspace)
        assert "<!DOCTYPE html>" in html
        assert "ADG" in html

    def test_generate_dashboard_static(self, workspace, tmp_path):
        from tools.dashboard import generate_dashboard_html

        output = tmp_path / "dashboard.html"
        html = generate_dashboard_html(workspace, output)
        assert output.exists()
        assert "<!DOCTYPE html>" in html


class TestCicd:
    def test_list_templates(self):
        from tools.cicd import list_templates

        templates = list_templates()
        assert "github" in templates
        assert "gitlab" in templates

    def test_get_template(self):
        from tools.cicd import get_template

        template = get_template("github")
        assert template is not None
        assert "ADG Governance" in template

    def test_generate_github(self, tmp_path):
        from tools.cicd import generate_ci_config

        generate_ci_config("github", tmp_path)
        assert (tmp_path / ".github" / "workflows" / "adg-governance.yml").exists()

    def test_generate_gitlab(self, tmp_path):
        from tools.cicd import generate_ci_config

        generate_ci_config("gitlab", tmp_path)
        assert (tmp_path / ".gitlab-ci.yml").exists()

    def test_generate_unknown(self):
        from tools.cicd import generate_ci_config

        with pytest.raises(ValueError):
            generate_ci_config("unknown")

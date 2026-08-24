"""Tests for new ADG modules: HTML report, AI recommender, marketplace, multiproject, fix engine, chat integration, dashboard, cicd, benchmarks, LSP."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
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


# ─────────────────────────────────────────────────────────────
# HTML Report
# ─────────────────────────────────────────────────────────────


class TestHtmlReport:
    def test_generate_html_report(self):
        from tools.report import generate_html_report

        issues = [
            Issue(
                "SEC001",
                "error",
                "security",
                "main.py",
                1,
                1,
                "eval",
                "Use ast.literal_eval",
            ),
            Issue(
                "CQ001",
                "warning",
                "code_quality",
                "main.py",
                5,
                1,
                "print",
                "Use logging",
            ),
        ]
        html = generate_html_report(issues, "python", "flask", 2)
        assert "<!DOCTYPE html>" in html
        assert "eval" in html
        assert "flask" in html
        assert "1 error" in html.lower() or "Errors" in html

    def test_save_html_report(self, tmp_path):
        from tools.report import save_html_report

        issues = [Issue("SEC001", "error", "security", "main.py", 1, 1, "eval", "fix")]
        path = save_html_report(issues, tmp_path / "report.html", "python")
        assert path.exists()
        content = path.read_text()
        assert "<!DOCTYPE html>" in content

    def test_empty_report(self):
        from tools.report import generate_html_report

        html = generate_html_report([], "python")
        assert "<!DOCTYPE html>" in html
        assert "0" in html


# ─────────────────────────────────────────────────────────────
# AI Recommender
# ─────────────────────────────────────────────────────────────


class TestAiRecommender:
    def test_analyze_code_patterns(self):
        from tools.ai_recommender import analyze_code_patterns

        content = "x = eval('1+1')\nos.system('ls')\nexcept:\n"
        recs = analyze_code_patterns(Path("test.py"), content, "python")
        assert len(recs) > 0
        rules = [r["rule"] for r in recs]
        assert "SEC001" in rules

    def test_recommend_rules(self, workspace):
        from tools.ai_recommender import recommend_rules

        result = recommend_rules(workspace, 10)
        assert result["language"] == "python"
        assert result["files_scanned"] > 0

    def test_format_recommendations_text(self):
        from tools.ai_recommender import format_recommendations_text

        result = {
            "language": "python",
            "files_scanned": 10,
            "files_with_issues": 5,
            "total_recommendations": 2,
            "recommendations": [
                {
                    "rule_id": "SEC001",
                    "name": "eval",
                    "severity": "error",
                    "category": "security",
                    "reason": "dangerous",
                    "affected_files": 3,
                    "example": {"file": "a.py", "line": 1, "code": "eval()"},
                },
            ],
        }
        text = format_recommendations_text(result)
        assert "python" in text
        assert "SEC001" in text

    def test_javascript_patterns(self):
        from tools.ai_recommender import analyze_code_patterns

        content = "eval('x')\nvar y = 1;\n"
        recs = analyze_code_patterns(Path("test.js"), content, "javascript")
        rules = [r["rule"] for r in recs]
        assert "SEC001" in rules or "CQ010" in rules

    def test_rust_patterns(self):
        from tools.ai_recommender import analyze_code_patterns

        content = 'let x = vec![1];\nx.unwrap();\nprintln!("hi");\n'
        recs = analyze_code_patterns(Path("main.rs"), content, "rust")
        rules = [r["rule"] for r in recs]
        assert "CQ030" in rules or "CQ032" in rules

    def test_unknown_language(self):
        from tools.ai_recommender import analyze_code_patterns

        recs = analyze_code_patterns(Path("test.xyz"), "code", "unknown")
        assert recs == []


# ─────────────────────────────────────────────────────────────
# Marketplace
# ─────────────────────────────────────────────────────────────


class TestMarketplace:
    def test_list_packs(self):
        from tools.marketplace import list_packs

        packs = list_packs()
        assert len(packs) >= 3
        ids = [p["id"] for p in packs]
        assert "security-essentials" in ids

    def test_search_packs(self):
        from tools.marketplace import search_packs

        results = search_packs("security")
        assert len(results) >= 1

    def test_install_pack(self, workspace):
        from tools.marketplace import install_pack

        result = install_pack("security-essentials", workspace)
        assert result["success"] is True
        assert result["rules_installed"] > 0

    def test_install_nonexistent(self, workspace):
        from tools.marketplace import install_pack

        result = install_pack("nonexistent", workspace)
        assert result["success"] is False

    def test_uninstall_pack(self, workspace):
        from tools.marketplace import install_pack, uninstall_pack

        install_pack("security-essentials", workspace)
        result = uninstall_pack("security-essentials", workspace)
        assert result["success"] is True

    def test_format_packs_list(self):
        from tools.marketplace import format_packs_list, list_packs

        packs = list_packs()
        text = format_packs_list(packs)
        assert "Available" in text

    def test_format_empty(self):
        from tools.marketplace import format_packs_list

        text = format_packs_list([])
        assert "No packs" in text


# ─────────────────────────────────────────────────────────────
# Multi-project
# ─────────────────────────────────────────────────────────────


class TestMultiProject:
    def test_discover_projects(self, workspace):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(workspace)
        projects = checker.discover_projects()
        assert len(projects) >= 1

    def test_check_project(self, workspace):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(workspace)
        projects = checker.discover_projects()
        if projects:
            result = checker.check_project(projects[0])
            assert "issues" in result
            assert "summary" in result

    def test_check_all(self, workspace):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(workspace)
        results = checker.check_all()
        assert "projects_found" in results
        assert "total_summary" in results

    def test_generate_report(self, workspace):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(workspace)
        results = checker.check_all()
        report = checker.generate_report(results)
        assert "Governance Report" in report

    def test_generate_json_report(self, workspace):
        from tools.multiproject import MonorepoChecker

        checker = MonorepoChecker(workspace)
        results = checker.check_all()
        report = checker.generate_report(results, "json")
        parsed = json.loads(report)
        assert "projects_found" in parsed


# ─────────────────────────────────────────────────────────────
# Fix Engine
# ─────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────
# Chat Integration
# ─────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────
# Dashboard
# ─────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────
# CI/CD
# ─────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────
# CLI Integration
# ─────────────────────────────────────────────────────────────


class TestNewCliCommands:
    def test_html_report_command(self, workspace):
        from tools.scripts.adg_cli import cmd_html_report

        args = argparse.Namespace(path=str(workspace), output=str(workspace / "report.html"), lang=None)
        result = cmd_html_report(args)
        assert result == 0
        assert (workspace / "report.html").exists()

    def test_recommend_command(self, workspace):
        from tools.scripts.adg_cli import cmd_recommend

        args = argparse.Namespace(path=str(workspace), json=False, max=5)
        result = cmd_recommend(args)
        assert result == 0

    def test_recommend_json(self, workspace):
        from tools.scripts.adg_cli import cmd_recommend

        args = argparse.Namespace(path=str(workspace), json=True, max=5)
        result = cmd_recommend(args)
        assert result == 0

    def test_marketplace_list(self):
        from tools.scripts.adg_cli import cmd_marketplace

        args = argparse.Namespace(marketplace_command="list")
        result = cmd_marketplace(args)
        assert result == 0

    def test_marketplace_install(self, workspace):
        from tools.scripts.adg_cli import cmd_marketplace

        args = argparse.Namespace(marketplace_command="install", pack_id="security-essentials", lang=None)
        result = cmd_marketplace(args)
        assert result == 0

    def test_marketplace_no_command(self):
        from tools.scripts.adg_cli import cmd_marketplace

        args = argparse.Namespace(marketplace_command=None)
        result = cmd_marketplace(args)
        assert result == 1

    def test_monorepo_command(self, workspace):
        from tools.scripts.adg_cli import cmd_monorepo

        args = argparse.Namespace(path=str(workspace), json=False, lang=None)
        result = cmd_monorepo(args)
        assert result >= 0

    def test_monorepo_json(self, workspace):
        from tools.scripts.adg_cli import cmd_monorepo

        args = argparse.Namespace(path=str(workspace), json=True, lang=None)
        result = cmd_monorepo(args)
        assert result >= 0

    def test_dashboard_static(self, workspace, tmp_path):
        from tools.scripts.adg_cli import cmd_dashboard

        output = tmp_path / "dash.html"
        args = argparse.Namespace(path=str(workspace), static=str(output), port=8080, host="127.0.0.1")
        result = cmd_dashboard(args)
        assert result == 0
        assert output.exists()

    def test_cicd_command(self, tmp_path):
        from tools.scripts.adg_cli import cmd_cicd

        args = argparse.Namespace(platform="github", output=str(tmp_path))
        result = cmd_cicd(args)
        assert result == 0
        assert (tmp_path / ".github" / "workflows" / "adg-governance.yml").exists()

    def test_bench_command(self, tmp_path):
        from tools.scripts.adg_cli import cmd_bench

        output = tmp_path / "bench.json"
        args = argparse.Namespace(files="10", languages="python", output=str(output))
        result = cmd_bench(args)
        assert result == 0
        assert output.exists()

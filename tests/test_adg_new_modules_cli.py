# 拆分自 tests/test_adg_new_modules.py

"""Tests for new ADG modules: HTML report, AI recommender, marketplace, multiproject, fix engine, chat integration, dashboard, cicd, benchmarks, LSP."""

from __future__ import annotations

import argparse

import pytest


@pytest.fixture
def workspace(tmp_path):
    d = tmp_path / "project"
    d.mkdir()
    (d / ".git").mkdir()
    (d / "pyproject.toml").write_text("[project]\nname='test'\n")
    (d / "main.py").write_text("import os\nos.system('ls')\nx = eval('1+1')\nimport pickle\n")
    (d / "utils.py").write_text("import sys\nprint(sys.argv)\n")
    return d


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

        args = argparse.Namespace(
            marketplace_command="install",
            pack_id="security-essentials",
            lang=None,
            path=str(workspace),  # 防止默认 "." 污染项目根 .adg/rules.yml
        )
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

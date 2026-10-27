"""Tests for new ADG modules: HTML report, AI recommender, marketplace, multiproject, fix engine, chat integration, dashboard, cicd, benchmarks, LSP."""

from __future__ import annotations

import json
from pathlib import Path

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

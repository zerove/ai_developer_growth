#!/usr/bin/env python3
"""Tests for contributor_dashboard.py"""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.contributor_dashboard import ContributorDashboard


class TestContributorDashboard:
    """Test ContributorDashboard class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.repo_root = Path(self.temp_dir)
        self.dashboard = ContributorDashboard(self.repo_root)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_case_study(self, name: str, content: str):
        """Helper to write a case study file."""
        cases_dir = self.repo_root / "docs" / "case-studies"
        cases_dir.mkdir(parents=True, exist_ok=True)
        (cases_dir / f"{name}.md").write_text(content, encoding="utf-8")

    def _write_tool_matrix(self, content: str):
        """Helper to write tool matrix file."""
        tools_dir = self.repo_root / "docs" / "tools"
        tools_dir.mkdir(parents=True, exist_ok=True)
        (tools_dir / "ai-tool-matrix.md").write_text(content, encoding="utf-8")

    def _write_docs(self, category: str, files: list[str]):
        """Helper to write docs files."""
        cat_dir = self.repo_root / "docs" / category
        cat_dir.mkdir(parents=True, exist_ok=True)
        for f in files:
            (cat_dir / f).write_text("# Doc\n", encoding="utf-8")

    def test_analyze_case_studies_empty(self):
        """Test case studies analysis with no files."""
        result = self.dashboard.analyze_case_studies()
        assert result["total"] == 0
        assert result["by_type"] == {}
        assert result["by_tool"] == {}
        assert result["avg_boost"] == 0

    def test_analyze_case_studies_with_data(self):
        """Test case studies analysis with valid data."""
        content = """# Test Case
项目类型: Web 开发
AI 工具栈: Cursor, GitHub Copilot
效率提升: 3.5x
"""
        self._write_case_study("case1", content)

        content2 = """# Test Case 2
项目类型: 移动开发
AI 工具栈: Cursor
效率提升: 2x
"""
        self._write_case_study("case2", content2)

        result = self.dashboard.analyze_case_studies()
        assert result["total"] == 2
        assert result["by_type"]["Web 开发"] == 1
        assert result["by_type"]["移动开发"] == 1
        assert result["by_tool"]["Cursor, GitHub Copilot"] == 1
        assert result["by_tool"]["Cursor"] == 1
        assert result["avg_boost"] == 2.8
        assert result["max_boost"] == 3.5

    def test_analyze_case_studies_skips_readme(self):
        """Test that README.md and INDEX.md are skipped."""
        self._write_case_study("README", "# Readme\n项目类型: Web\n效率提升: 5x")
        self._write_case_study("INDEX", "# Index\n")
        self._write_case_study("real_case", "# Real\n项目类型: API\n效率提升: 2x")

        result = self.dashboard.analyze_case_studies()
        assert result["total"] == 1
        assert result["by_type"]["API"] == 1

    def test_analyze_tool_matrix_empty(self):
        """Test tool matrix analysis with no file."""
        result = self.dashboard.analyze_tool_matrix()
        assert result["recommended"] == 0
        assert result["stable"] == 0
        assert result["legacy"] == 0
        assert result["total"] == 0

    def test_analyze_tool_matrix_with_data(self):
        """Test tool matrix analysis with data."""
        content = """# AI Tool Matrix
✅ **推荐** Tool A
✅ **推荐** Tool B
⚠️ **稳定** Tool C
❌ **遗留** Tool D
"""
        self._write_tool_matrix(content)

        result = self.dashboard.analyze_tool_matrix()
        assert result["recommended"] == 2
        assert result["stable"] == 1
        assert result["legacy"] == 1
        assert result["total"] == 4

    @patch("subprocess.run")
    def test_analyze_contributors(self, mock_run):
        """Test contributors analysis."""
        mock_result = MagicMock()
        mock_result.stdout = "10\tJohn Doe\n5\tJane Smith\n"
        mock_result.stderr = ""
        mock_run.return_value = mock_result

        result = self.dashboard.analyze_contributors()
        assert result["total_contributors"] == 2
        assert result["top_contributors"][0]["name"] == "John Doe"
        assert result["top_contributors"][0]["commits"] == 10
        assert result["top_contributors"][1]["name"] == "Jane Smith"
        assert result["top_contributors"][1]["commits"] == 5

    @patch("subprocess.run")
    def test_analyze_contributors_error(self, mock_run):
        """Test contributors analysis on error."""
        import subprocess

        mock_run.side_effect = subprocess.SubprocessError("git not found")

        result = self.dashboard.analyze_contributors()
        assert result["total_contributors"] == 0
        assert result["top_contributors"] == []
        assert result["all"] == []

    def test_analyze_docs_coverage(self):
        """Test docs coverage analysis."""
        self._write_docs("efficiency", ["workflow.md", "metrics.md"])
        self._write_docs("learning", ["prompt.md"])

        result = self.dashboard.analyze_docs_coverage()
        assert result["total"] == 3
        assert result["categories"]["efficiency"] == 2
        assert result["categories"]["learning"] == 1

    def test_generate_dashboard_markdown(self):
        """Test dashboard generation in markdown format."""
        self._write_case_study("case1", "# Case\n项目类型: Web\n效率提升: 2x")
        self._write_tool_matrix("✅ **推荐** Tool A")
        self._write_docs("efficiency", ["workflow.md"])

        with patch.object(
            self.dashboard,
            "analyze_contributors",
            return_value={
                "total_contributors": 1,
                "top_contributors": [{"name": "Test", "commits": 5}],
                "all": [],
            },
        ):
            result = self.dashboard.generate_dashboard("markdown")

        assert "# 📊 贡献者仪表板" in result
        assert "案例研究统计" in result
        assert "1 个真实案例" in result
        assert "平均效率提升" in result
        assert "AI 工具矩阵" in result
        assert "文档覆盖率" in result
        assert "贡献者排行榜" in result

    def test_generate_dashboard_json(self):
        """Test dashboard generation in JSON format."""
        self._write_case_study("case1", "# Case\n项目类型: Web\n效率提升: 2x")

        with patch.object(
            self.dashboard,
            "analyze_contributors",
            return_value={"total_contributors": 0, "top_contributors": [], "all": []},
        ):
            result = self.dashboard.generate_dashboard("json")

        import json

        data = json.loads(result)
        assert "generated_at" in data
        assert "case_studies" in data
        assert "tool_matrix" in data
        assert "contributors" in data
        assert "docs_coverage" in data
        assert data["case_studies"]["total"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

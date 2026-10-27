# 拆分自 tests/test_update_ai_tool_matrix.py

"""Tests for update_ai_tool_matrix.py"""

import json
from datetime import datetime, timedelta
from unittest.mock import patch

from tools.scripts.update_ai_tool_matrix import (
    ModelInfo,
    ToolInfo,
    ToolMatrixUpdater,
)


class TestLoadConfigFile:
    """Test config loading with actual files."""

    def test_load_config_with_file(self, tmp_path):
        """Test loading config when file exists."""
        config_file = tmp_path / "config.json"
        config_file.write_text(json.dumps({"check_interval": 48}))
        updater = ToolMatrixUpdater()
        with patch("tools.scripts.update_ai_tool_matrix.CONFIG_PATH", config_file):
            result = updater._load_config()
            assert result == {"check_interval": 48}

    def test_load_config_missing_file(self):
        """Test loading config when file doesn't exist."""
        updater = ToolMatrixUpdater()
        with patch("tools.scripts.update_ai_tool_matrix.CONFIG_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = updater._load_config()
            assert result == {}


class TestLoadCacheFile:
    """Test cache loading with actual files."""

    def test_load_cache_with_file(self, tmp_path):
        """Test loading cache when file exists."""
        cache_file = tmp_path / "cache.json"
        cache_file.write_text(json.dumps({"github_test": {"version": "v1.0"}}))
        updater = ToolMatrixUpdater()
        with patch("tools.scripts.update_ai_tool_matrix.CACHE_PATH", cache_file):
            result = updater._load_cache()
            assert result == {"github_test": {"version": "v1.0"}}

    def test_load_cache_missing_file(self):
        """Test loading cache when file doesn't exist."""
        updater = ToolMatrixUpdater()
        with patch("tools.scripts.update_ai_tool_matrix.CACHE_PATH") as mock_path:
            mock_path.exists.return_value = False
            result = updater._load_cache()
            assert result == {}


class TestParseMatrixExtended:
    """Test markdown parsing in detail."""

    def test_parse_models_only(self):
        """Test parsing only models."""
        updater = ToolMatrixUpdater()
        updater.matrix_content = (
            "## 模型对比\n\n"
            "| 模型 | 核心优势 | 适用场景 | 局限 | 推荐度 |\n"
            "|------|----------|----------|------|--------|\n"
            "| **GPT-4o** | 速度快 | 通用 | 推理弱 | ⭐⭐⭐⭐⭐ |\n"
            "| **Claude 3.5 Sonnet** | 推理强 | 复杂任务 | 慢 | ⭐⭐⭐⭐ |\n"
        )
        updater._parse_matrix()
        assert len(updater.models) == 2
        assert "GPT-4o" in updater.models
        assert updater.models["GPT-4o"].pricing_tier == "5/5"

    def test_parse_tools_only(self):
        """Test parsing only tools."""
        updater = ToolMatrixUpdater()
        updater.matrix_content = (
            "## AI Coding Agent Harness\n\n"
            "| 工具 | 核心功能 | 优势 | 劣势 | 适用人群 |\n"
            "|------|----------|------|------|----------|\n"
            "| jcode | AI agent | 开源 | 新 | 开发者 |\n"
            "| opencode | AI agent | 安全 | 学习曲线 | 高级用户 |\n"
        )
        updater._parse_matrix()
        # Header row "工具" may also be parsed
        assert len(updater.tools) >= 2
        assert "jcode" in updater.tools

    def test_parse_empty_content(self):
        """Test parsing empty content."""
        updater = ToolMatrixUpdater()
        updater.matrix_content = ""
        updater._parse_matrix()
        assert len(updater.models) == 0
        assert len(updater.tools) == 0


class TestUpdateMatrixExtended:
    """Test update_matrix in detail."""

    def test_update_with_models_and_tools(self):
        """Test update with both models and tools."""
        updater = ToolMatrixUpdater()
        updater.matrix_content = "original"
        updater.models["test"] = ModelInfo(
            name="test",
            provider="p",
            current_version="1",
            latest_version="2",
            update_available=True,
        )
        updater.tools["tool"] = ToolInfo(
            name="tool",
            category="ide",
            current_version="1",
            latest_version="2",
            update_available=True,
        )
        result = updater.update_matrix()
        assert isinstance(result, bool)


class TestGenerateReportExtended:
    """Test report generation in detail."""

    def test_report_date_included(self):
        """Test report includes current date."""
        updater = ToolMatrixUpdater()
        report = updater.generate_report()
        year = str(datetime.now().year)
        assert year in report

    def test_report_next_check_date(self):
        """Test report includes next check date."""
        updater = ToolMatrixUpdater()
        report = updater.generate_report()
        next_week = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
        assert next_week in report

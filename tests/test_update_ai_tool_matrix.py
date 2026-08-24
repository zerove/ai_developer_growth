#!/usr/bin/env python3
"""Tests for update_ai_tool_matrix.py"""

import asyncio
import json
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.update_ai_tool_matrix import (
    ModelInfo,
    SourceType,
    ToolInfo,
    ToolMatrixUpdater,
    main,
)


class TestToolInfo:
    """Test ToolInfo dataclass."""

    def test_tool_info_creation(self):
        """Test ToolInfo creation with defaults."""
        tool = ToolInfo(name="TestTool", category="ide", current_version="1.0.0")
        assert tool.name == "TestTool"
        assert tool.category == "ide"
        assert tool.current_version == "1.0.0"
        assert tool.latest_version is None
        assert tool.update_available is False

    def test_tool_info_with_all_fields(self):
        """Test ToolInfo with all fields specified."""
        tool = ToolInfo(
            name="Cursor",
            category="ide",
            current_version="0.45.0",
            latest_version="0.46.0",
            release_date="2026-01-01",
            source_url="https://cursor.sh",
            source_type=SourceType.STATIC,
            description="AI IDE",
            pricing="Free",
            last_checked="2026-01-01",
            update_available=True,
        )
        assert tool.update_available is True
        assert tool.latest_version == "0.46.0"


class TestModelInfo:
    """Test ModelInfo dataclass."""

    def test_model_info_defaults(self):
        """Test ModelInfo defaults for strengths and use_cases."""
        model = ModelInfo(name="GPT-5", provider="OpenAI", current_version="latest")
        assert model.strengths == []
        assert model.use_cases == []

    def test_model_info_with_values(self):
        """Test ModelInfo with explicit values."""
        model = ModelInfo(
            name="Claude-4",
            provider="Anthropic",
            current_version="latest",
            strengths=["Long context"],
            use_cases=["Coding"],
        )
        assert model.strengths == ["Long context"]
        assert model.use_cases == ["Coding"]


class TestToolMatrixUpdater:
    """Test ToolMatrixUpdater class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.updater = ToolMatrixUpdater()

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_load_config_missing(self):
        """Test loading config when file doesn't exist."""
        updater = ToolMatrixUpdater()
        # Config loading uses global CONFIG_PATH, may or may not exist
        assert isinstance(updater.config, dict)

    def test_load_cache_missing(self):
        """Test loading cache when file doesn't exist."""
        updater = ToolMatrixUpdater()
        assert isinstance(updater.cache, dict)

    def test_generate_report_no_updates(self):
        """Test report generation with no updates."""
        self.updater.tools["Cursor"] = ToolInfo(name="Cursor", category="ide", current_version="1.0.0")
        self.updater.models["GPT-5"] = ModelInfo(name="GPT-5", provider="OpenAI", current_version="latest")

        report = self.updater.generate_report()
        assert "AI Tool Matrix Update Report" in report
        assert "All Models Up to Date" in report
        assert "All Tools Up to Date" in report
        assert "No immediate updates" in report

    def test_generate_report_with_updates(self):
        """Test report generation with available updates."""
        self.updater.models["DeepSeek V3"] = ModelInfo(
            name="DeepSeek V3",
            provider="DeepSeek",
            current_version="v2.0",
            latest_version="v3.0",
            update_available=True,
        )
        self.updater.tools["jcode"] = ToolInfo(
            name="jcode",
            category="utility",
            current_version="1.0.0",
            latest_version="2.0.0",
            update_available=True,
        )

        report = self.updater.generate_report()
        assert "Model Updates Available" in report
        assert "Tool Updates Available" in report
        assert "Update the matrix" in report

    def test_generate_report_cli_versions(self):
        """Test report with installed CLI versions."""
        self.updater.tools["jcode"] = ToolInfo(
            name="jcode",
            category="utility",
            current_version="1.2.3",
        )

        report = self.updater.generate_report()
        assert "jcode: 1.2.3" in report

    def test_update_matrix_empty(self):
        """Test update_matrix with no tools or models."""
        result = self.updater.update_matrix()
        assert result is False

    def test_update_matrix_no_updates(self):
        """Test update_matrix with tools but no updates available."""
        self.updater.tools["Cursor"] = ToolInfo(name="Cursor", category="ide", current_version="1.0.0")
        self.updater.matrix_content = "some content"
        result = self.updater.update_matrix()
        assert result is False

    @patch("subprocess.run")
    def test_check_cli_versions(self, mock_run):
        """Test CLI version checking."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.2.3\n"
        mock_run.return_value = mock_result

        self.updater.tools["jcode"] = ToolInfo(name="jcode", category="utility", current_version="latest")
        self.updater._check_cli_versions()
        assert self.updater.tools["jcode"].current_version == "1.2.3"

    @patch("subprocess.run")
    def test_check_cli_versions_file_not_found(self, mock_run):
        """Test CLI version checking when command not found."""
        mock_run.side_effect = FileNotFoundError("not found")

        self.updater.tools["jcode"] = ToolInfo(name="jcode", category="utility", current_version="latest")
        # Should not raise
        self.updater._check_cli_versions()

    @patch("subprocess.run")
    def test_check_github_releases(self, mock_run):
        """Test GitHub releases checking."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"tagName": "v3.0.0"}])
        mock_run.return_value = mock_result

        # Clear cache to force check
        self.updater.cache = {}

        import asyncio

        result = asyncio.run(self.updater._check_github_releases("DeepSeek V3", "deepseek"))
        assert result == "v3.0.0"

    def test_check_github_releases_caching(self):
        """Test GitHub releases caching."""
        from datetime import datetime, timedelta

        # Pre-populate cache
        self.updater.cache = {
            "github_deepseek-ai/DeepSeek-V3": {
                "latest_version": "v2.5.0",
                "checked_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            }
        }

        result = asyncio.run(self.updater._check_github_releases("DeepSeek V3", "deepseek"))
        assert result == "v2.5.0"

    @patch("subprocess.run")
    def test_check_pypi(self, mock_run):
        """Test PyPI version checking."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Available versions: 1.0.0, 1.0.1, 1.1.0"
        mock_run.return_value = mock_result

        self.updater.cache = {}

        import asyncio

        result = asyncio.run(self.updater._check_pypi("some-package"))
        assert result == "1.1.0"

    def test_check_pypi_caching(self):
        """Test PyPI version caching."""
        from datetime import datetime, timedelta

        self.updater.cache = {
            "pypi_some-package": {
                "latest_version": "1.0.5",
                "checked_at": (datetime.now() - timedelta(hours=1)).isoformat(),
            }
        }

        result = asyncio.run(self.updater._check_pypi("some-package"))
        assert result == "1.0.5"

    @patch("subprocess.run")
    def test_check_model_updates(self, mock_run):
        """Test model updates checking."""
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"tagName": "v4.0.0"}])
        mock_run.return_value = mock_result

        self.updater.models["DeepSeek V3"] = ModelInfo(
            name="DeepSeek V3",
            provider="DeepSeek",
            current_version="v3.0",
        )
        self.updater.cache = {}

        updates = asyncio.run(self.updater.check_model_updates())
        assert isinstance(updates, list)

    def test_save_cache(self, tmp_path):
        """Test cache saving."""
        with patch("tools.scripts.update_ai_tool_matrix.CACHE_PATH", tmp_path / "cache.json"):
            self.updater.cache = {"test": {"value": 123}}
            self.updater._save_cache()

        assert (tmp_path / "cache.json").exists()


# ---------------------------------------------------------------------------
# Extended coverage tests
# ---------------------------------------------------------------------------


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


class TestCheckGithubReleasesExtended:
    """Test GitHub releases checking in detail."""

    def test_unknown_provider_returns_none(self):
        """Test unknown provider returns None."""
        updater = ToolMatrixUpdater()
        updater.cache = {}
        result = asyncio.run(updater._check_github_releases("model", "unknown_provider"))
        assert result is None

    def test_expired_cache_triggers_check(self):
        """Test expired cache triggers new check."""
        updater = ToolMatrixUpdater()
        updater.cache = {
            "github_deepseek-ai/DeepSeek-V3": {
                "latest_version": "v3.0",
                "checked_at": (datetime.now() - timedelta(hours=48)).isoformat(),
            }
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"tagName": "v3.1"}])
        with patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(updater._check_github_releases("DeepSeek V3", "deepseek"))
            assert result == "v3.1"

    def test_gh_cli_fails(self):
        """Test when gh CLI fails."""
        updater = ToolMatrixUpdater()
        updater.cache = {}
        mock_result = MagicMock()
        mock_result.returncode = 1
        with patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(updater._check_github_releases("DeepSeek V3", "deepseek"))
            assert result is None


class TestCheckPyPIExtended:
    """Test PyPI checking in detail."""

    def test_pip_fails_returns_none(self):
        """Test when pip command fails."""
        updater = ToolMatrixUpdater()
        updater.cache = {}
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        with patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(updater._check_pypi("nonexistent"))
            assert result is None

    def test_pip_no_versions_in_output(self):
        """Test when pip output has no versions."""
        updater = ToolMatrixUpdater()
        updater.cache = {}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Some other output"
        with patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(updater._check_pypi("mypackage"))
            assert result is None

    def test_expired_cache_triggers_pip_check(self):
        """Test expired cache triggers new check."""
        updater = ToolMatrixUpdater()
        updater.cache = {
            "pypi_mypackage": {
                "latest_version": "1.0",
                "checked_at": (datetime.now() - timedelta(hours=48)).isoformat(),
            }
        }
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Available versions: 2.0.0"
        with patch("subprocess.run", return_value=mock_result):
            result = asyncio.run(updater._check_pypi("mypackage"))
            assert result == "2.0.0"


class TestCheckModelUpdatesExtended:
    """Test model updates checking in detail."""

    def test_qwen_checks_github(self):
        """Test Qwen models check GitHub."""
        updater = ToolMatrixUpdater()
        updater.models["Qwen2.5-Coder"] = ModelInfo(
            name="Qwen2.5-Coder",
            provider="qwen",
            current_version="latest",
        )
        updater.cache = {}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = json.dumps([{"tagName": "v2.5.1"}])
        with patch("subprocess.run", return_value=mock_result):
            updates = asyncio.run(updater.check_model_updates())
            assert isinstance(updates, list)

    def test_pypi_tool_updates(self):
        """Test PyPI tool updates."""
        updater = ToolMatrixUpdater()
        updater.tools["mytool"] = ToolInfo(
            name="mytool",
            category="utility",
            current_version="1.0",
            source_type=SourceType.PYPI,
        )
        updater.cache = {}
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Available versions: 1.0, 2.0"
        with patch("subprocess.run", return_value=mock_result):
            updates = asyncio.run(updater.check_model_updates())
            assert len(updates) == 1
            assert "mytool" in updates[0]


class TestMainExtended:
    """Test CLI entry points."""

    def test_main_check_flag(self):
        """Test --check flag."""
        with patch("sys.argv", ["update_ai_tool_matrix.py", "--check"]):
            with patch.object(ToolMatrixUpdater, "load_matrix"):
                with patch.object(ToolMatrixUpdater, "check_model_updates", return_value=[]):
                    with patch.object(ToolMatrixUpdater, "_check_cli_versions"):
                        with patch.object(
                            ToolMatrixUpdater,
                            "generate_report",
                            return_value="Report",
                        ):
                            result = asyncio.run(main())
                            assert result == 0

    def test_main_update_flag(self):
        """Test --update flag."""
        with patch("sys.argv", ["update_ai_tool_matrix.py", "--update"]):
            with patch.object(ToolMatrixUpdater, "load_matrix"):
                with patch.object(ToolMatrixUpdater, "check_model_updates", return_value=[]):
                    with patch.object(ToolMatrixUpdater, "_check_cli_versions"):
                        with patch.object(ToolMatrixUpdater, "update_matrix", return_value=False):
                            result = asyncio.run(main())
                            assert result == 0

    def test_main_report_to_file(self, tmp_path):
        """Test --report with --output."""
        out_file = tmp_path / "report.md"
        with patch(
            "sys.argv",
            ["update_ai_tool_matrix.py", "--report", "--output", str(out_file)],
        ):
            with patch.object(ToolMatrixUpdater, "load_matrix"):
                with patch.object(ToolMatrixUpdater, "check_model_updates", return_value=[]):
                    with patch.object(ToolMatrixUpdater, "_check_cli_versions"):
                        with patch.object(
                            ToolMatrixUpdater,
                            "generate_report",
                            return_value="Report content",
                        ):
                            result = asyncio.run(main())
                            assert result == 0
                            assert out_file.read_text() == "Report content"

    def test_main_update_with_changes(self):
        """Test --update when changes are made."""
        with patch("sys.argv", ["update_ai_tool_matrix.py", "--update"]):
            with patch.object(ToolMatrixUpdater, "load_matrix"):
                with patch.object(ToolMatrixUpdater, "check_model_updates", return_value=[]):
                    with patch.object(ToolMatrixUpdater, "_check_cli_versions"):
                        with patch.object(ToolMatrixUpdater, "update_matrix", return_value=True):
                            result = asyncio.run(main())
                            assert result == 0


class TestSaveCacheExtended:
    """Test cache saving."""

    def test_save_cache_writes_file(self, tmp_path):
        """Test cache is written to file."""
        with patch("tools.scripts.update_ai_tool_matrix.CACHE_PATH", tmp_path / "cache.json"):
            updater = ToolMatrixUpdater()
            updater.cache = {"test": {"value": 42}}
            updater._save_cache()
        assert (tmp_path / "cache.json").exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

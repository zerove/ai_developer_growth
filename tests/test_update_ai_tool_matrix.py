#!/usr/bin/env python3
"""Tests for update_ai_tool_matrix.py"""

import asyncio
import json
import tempfile
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.update_ai_tool_matrix import (
    ModelInfo,
    SourceType,
    ToolInfo,
    ToolMatrixUpdater,
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
        self.updater.tools["Cursor"] = ToolInfo(
            name="Cursor", category="ide", current_version="1.0.0"
        )
        self.updater.models["GPT-5"] = ModelInfo(
            name="GPT-5", provider="OpenAI", current_version="latest"
        )

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
        self.updater.tools["Cursor"] = ToolInfo(
            name="Cursor", category="ide", current_version="1.0.0"
        )
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

        self.updater.tools["jcode"] = ToolInfo(
            name="jcode", category="utility", current_version="latest"
        )
        self.updater._check_cli_versions()
        assert self.updater.tools["jcode"].current_version == "1.2.3"

    @patch("subprocess.run")
    def test_check_cli_versions_file_not_found(self, mock_run):
        """Test CLI version checking when command not found."""
        mock_run.side_effect = FileNotFoundError("not found")

        self.updater.tools["jcode"] = ToolInfo(
            name="jcode", category="utility", current_version="latest"
        )
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
        result = asyncio.run(
            self.updater._check_github_releases("DeepSeek V3", "deepseek")
        )
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

        result = asyncio.run(
            self.updater._check_github_releases("DeepSeek V3", "deepseek")
        )
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

    def test_save_cache(self):
        """Test cache saving."""
        self.updater.cache = {"test": {"value": 123}}
        self.updater._save_cache()

        from tools.scripts.update_ai_tool_matrix import CACHE_PATH
        assert CACHE_PATH.exists()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

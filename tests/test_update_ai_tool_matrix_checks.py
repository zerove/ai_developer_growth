# 拆分自 tests/test_update_ai_tool_matrix.py

"""Tests for update_ai_tool_matrix.py"""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from tools.scripts.update_ai_tool_matrix import (
    ModelInfo,
    SourceType,
    ToolInfo,
    ToolMatrixUpdater,
    main,
)


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

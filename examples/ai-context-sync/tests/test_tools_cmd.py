"""Tests for CLI tool commands: scaffold, init, override, onboard, install_hook, report."""

import os
import sys
from unittest.mock import MagicMock, mock_open, patch

from typer.testing import CliRunner

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.cli import app

runner = CliRunner()

# ---------------------------------------------------------------------------
# scaffold
# ---------------------------------------------------------------------------


class TestScaffold:
    """Tests for the scaffold command."""

    @patch("src.cli.commands.tools.shutil")
    @patch("src.cli.commands.tools.os")
    @patch("src.cli.commands.tools.init")
    @patch("builtins.open", mock_open())
    def test_scaffold_empty_dir(self, mock_init, mock_os, mock_shutil):
        """Scaffold succeeds when directory only has .git."""
        mock_os.listdir.return_value = [".git"]
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = False
        mock_os.path.join.side_effect = os.path.join

        result = runner.invoke(app, ["scaffold", "my-template"])

        assert result.exit_code == 0
        assert "Successfully scaffolded" in result.stdout
        mock_init.assert_called_once()

    @patch("src.cli.commands.tools.os")
    def test_scaffold_non_empty_dir(self, mock_os):
        """Scaffold aborts when directory is not empty."""
        mock_os.listdir.return_value = [".git", "README.md", "src"]

        result = runner.invoke(app, ["scaffold", "my-template"])

        assert result.exit_code == 1
        assert "Directory is not empty" in result.stdout

    @patch("src.cli.commands.tools.os")
    def test_scaffold_template_not_found(self, mock_os):
        """Scaffold aborts when template does not exist."""
        mock_os.listdir.return_value = [".git"]
        mock_os.path.exists.return_value = False
        mock_os.path.join.side_effect = os.path.join

        result = runner.invoke(app, ["scaffold", "nonexistent"])

        assert result.exit_code == 1
        assert "not found" in result.stdout

    @patch("src.cli.commands.tools.shutil")
    @patch("src.cli.commands.tools.os")
    @patch("src.cli.commands.tools.init")
    @patch("builtins.open", mock_open())
    def test_scaffold_copies_files(self, mock_init, mock_os, mock_shutil):
        """Scaffold copies individual files from template."""
        mock_os.listdir.side_effect = lambda p: [".git"] if p == "." else ["file1.txt", "file2.py"]
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = False
        mock_os.path.join.side_effect = os.path.join

        result = runner.invoke(app, ["scaffold", "basic"])

        assert result.exit_code == 0
        assert mock_shutil.copy2.call_count == 2

    @patch("src.cli.commands.tools.shutil")
    @patch("src.cli.commands.tools.os")
    @patch("src.cli.commands.tools.init")
    @patch("builtins.open", mock_open())
    def test_scaffold_copies_directories(self, mock_init, mock_os, mock_shutil):
        """Scaffold copies subdirectories via copytree."""
        mock_os.listdir.side_effect = lambda p: [".git"] if p == "." else ["src_dir"]
        mock_os.path.exists.return_value = True
        mock_os.path.isdir.return_value = True
        mock_os.path.join.side_effect = os.path.join

        result = runner.invoke(app, ["scaffold", "full-stack"])

        assert result.exit_code == 0
        mock_shutil.copytree.assert_called_once()

    @patch("src.cli.commands.tools.shutil")
    @patch("src.cli.commands.tools.os")
    @patch("src.cli.commands.tools.init")
    @patch("builtins.open", mock_open())
    def test_scaffold_writes_context_md(self, mock_init, mock_os, mock_shutil):
        """Scaffold appends to CONTEXT.md after copying."""
        mock_os.listdir.side_effect = lambda p: [".git"] if p == "." else []
        mock_os.path.exists.return_value = True
        mock_os.path.join.side_effect = os.path.join

        with patch("builtins.open", mock_open()) as m_open:
            _result = runner.invoke(app, ["scaffold", "minimal"])
            m_open.assert_any_call("CONTEXT.md", "a")


# ---------------------------------------------------------------------------
# init
# ---------------------------------------------------------------------------


class TestInit:
    """Tests for the init command."""

    @patch("src.cli.commands.tools.os.path.exists", return_value=False)
    def test_init_creates_new_config(self, mock_exists):
        """Init creates .ai-sync.json when it doesn't exist."""

        # Provide a simple object whose __dict__ can be recursed by d_to_dict
        # without infinite recursion (plain dataclass-like, not MagicMock)
        class SimpleConfig:
            def __init__(self):
                self.llm = None
                self.settings = None
                self.config_path = ".ai-sync.json"

        with patch("src.config.AppConfig", return_value=SimpleConfig()):
            with patch("builtins.open", mock_open()) as m_open:
                result = runner.invoke(app, ["init"])
                assert result.exit_code == 0
                m_open.assert_called_once_with(".ai-sync.json", "w")

    @patch("src.cli.commands.tools.os.path.exists", return_value=True)
    def test_init_skips_existing_config(self, mock_exists):
        """Init skips creation when config already exists."""
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0


# ---------------------------------------------------------------------------
# override
# ---------------------------------------------------------------------------


class TestOverride:
    """Tests for the override command."""

    def test_override_first_time(self):
        """Override adds a new rule_id to overridden list."""
        mock_config = MagicMock()
        mock_config.settings.overridden_violations = []

        with patch("src.config.AppConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            result = runner.invoke(app, ["override", "ADR-001"])

            assert result.exit_code == 0
            assert "has been overridden" in result.stdout
            assert "ADR-001" in mock_config.settings.overridden_violations
            mock_config.save.assert_called_once()

    def test_override_already_overridden(self):
        """Override reports already overridden when rule_id exists."""
        mock_config = MagicMock()
        mock_config.settings.overridden_violations = ["ADR-001"]

        with patch("src.config.AppConfig") as MockConfig:
            MockConfig.load.return_value = mock_config
            result = runner.invoke(app, ["override", "ADR-001"])

            assert result.exit_code == 0
            assert "already overridden" in result.stdout
            mock_config.save.assert_not_called()


# ---------------------------------------------------------------------------
# onboard
# ---------------------------------------------------------------------------


class TestOnboard:
    """Tests for the onboard command."""

    @patch("src.cli.commands.tools.AIContextSync")
    @patch("src.onboarding.OnboardingSession", create=True)
    def test_onboard_starts_session(self, mock_session_cls, mock_sync_cls):
        """Onboard creates AIContextSync, OnboardingSession, and starts."""
        mock_sync = MagicMock()
        mock_sync_cls.return_value = mock_sync
        mock_session = MagicMock()
        mock_session_cls.return_value = mock_session

        result = runner.invoke(app, ["onboard"])

        assert result.exit_code == 0
        mock_sync_cls.assert_called_once()
        mock_session_cls.assert_called_once_with(mock_sync.llm_client)
        mock_session.start.assert_called_once()


# ---------------------------------------------------------------------------
# install_hook
# ---------------------------------------------------------------------------


class TestInstallHook:
    """Tests for the install_hook command using a real temp directory."""

    @patch("src.cli.commands.tools.subprocess.run")
    def test_install_hook_new(self, mock_run, tmp_path):
        """Install hook creates a new pre-commit hook."""
        mock_run.return_value = MagicMock(stdout=str(tmp_path / ".git\n"))
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)

        # Change cwd so the hook is written inside tmp_path
        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["install-hook"])
            assert result.exit_code == 0
            assert "pre-commit hook installed" in result.stdout
            hook = git_hooks / "pre-commit"
            assert hook.exists()
            assert "AI-Context-Sync" in hook.read_text()
        finally:
            os.chdir(original_cwd)

    @patch("src.cli.commands.tools.subprocess.run")
    def test_install_hook_already_installed(self, mock_run, tmp_path):
        """Install hook skips when AI-Context-Sync hook already exists."""
        mock_run.return_value = MagicMock(stdout=str(tmp_path / ".git\n"))
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)
        # Write an existing AI-Context-Sync hook
        hook = git_hooks / "pre-commit"
        hook.write_text("# AI-Context-Sync pre-commit hook\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["install-hook"])
            assert result.exit_code == 0
            assert "already installed" in result.stdout
        finally:
            os.chdir(original_cwd)

    @patch("src.cli.commands.tools.subprocess.run")
    def test_install_hook_backs_up_existing(self, mock_run, tmp_path):
        """Install hook backs up existing non-AI-Context-Sync hook."""
        mock_run.return_value = MagicMock(stdout=str(tmp_path / ".git\n"))
        git_hooks = tmp_path / ".git" / "hooks"
        git_hooks.mkdir(parents=True)
        # Write a different hook
        hook = git_hooks / "pre-commit"
        hook.write_text("#!/bin/bash\n# my custom hook\n")

        original_cwd = os.getcwd()
        try:
            os.chdir(tmp_path)
            result = runner.invoke(app, ["install-hook"])
            assert result.exit_code == 0
            assert "backed up" in result.stdout
            backup = git_hooks / "pre-commit.backup"
            assert backup.exists()
            assert "# my custom hook" in backup.read_text()
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------


class TestReport:
    """Tests for the report command."""

    @patch("src.report.save_report", return_value="docs/audit-report.html")
    @patch("src.report.generate_html_report", return_value="<html></html>")
    @patch("src.cli.commands.tools.AIContextSync")
    def test_report_generates_html(self, mock_sync_cls, mock_gen, mock_save):
        """Report generates HTML and saves it."""
        mock_sync = MagicMock()
        mock_violation = MagicMock()
        mock_violation.to_dict.return_value = {"severity": "Warning", "rule": "R1"}
        mock_sync.auditor.audit.return_value = [mock_violation]
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff"
        mock_sync.analyzer.get_last_commit_message.return_value = "commit msg"
        mock_sync_cls.return_value = mock_sync

        result = runner.invoke(app, ["report"])

        assert result.exit_code == 0
        assert "Audit report generated" in result.stdout
        mock_gen.assert_called_once()
        mock_save.assert_called_once()

    @patch("src.report.save_report", return_value="report.html")
    @patch("src.report.generate_html_report", return_value="<html></html>")
    @patch("src.cli.commands.tools.AIContextSync")
    def test_report_shows_violation_count(self, mock_sync_cls, mock_gen, mock_save):
        """Report shows number of violations found."""
        mock_sync = MagicMock()
        v1 = MagicMock()
        v1.to_dict.return_value = {"severity": "Critical"}
        v2 = MagicMock()
        v2.to_dict.return_value = {"severity": "Info"}
        v3 = MagicMock()
        v3.to_dict.return_value = {"severity": "Warning"}
        mock_sync.auditor.audit.return_value = [v1, v2, v3]
        mock_sync.analyzer.get_last_commit_diff.return_value = "diff"
        mock_sync.analyzer.get_last_commit_message.return_value = "msg"
        mock_sync_cls.return_value = mock_sync

        result = runner.invoke(app, ["report"])

        assert "3 violations" in result.stdout

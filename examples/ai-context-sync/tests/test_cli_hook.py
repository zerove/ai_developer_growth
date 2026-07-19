"""Tests for CLI install-hook command."""

import os
import tempfile
import subprocess
from unittest.mock import patch
from typer.testing import CliRunner

from src.cli import app

runner = CliRunner()


class TestInstallHook:
    def test_install_hook_creates_hook(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = os.path.join(tmpdir, ".git")
            hooks_dir = os.path.join(git_dir, "hooks")
            os.makedirs(hooks_dir)

            def mock_run(cmd, **kwargs):
                if cmd[0] == "git" and cmd[1] == "rev-parse":
                    result = subprocess.CompletedProcess(cmd, 0, stdout=git_dir)
                    return result
                return subprocess.CompletedProcess(cmd, 1)

            with patch("subprocess.run", side_effect=mock_run):
                result = runner.invoke(app, ["install-hook"])
                assert result.exit_code == 0
                hook_path = os.path.join(hooks_dir, "pre-commit")
                assert os.path.exists(hook_path)
                with open(hook_path, "r") as f:
                    content = f.read()
                assert "AI-Context-Sync" in content

    def test_install_hook_already_installed(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = os.path.join(tmpdir, ".git")
            hooks_dir = os.path.join(git_dir, "hooks")
            os.makedirs(hooks_dir)
            hook_path = os.path.join(hooks_dir, "pre-commit")
            with open(hook_path, "w") as f:
                f.write("# AI-Context-Sync pre-commit hook\n")

            def mock_run(cmd, **kwargs):
                if cmd[0] == "git" and cmd[1] == "rev-parse":
                    result = subprocess.CompletedProcess(cmd, 0, stdout=git_dir)
                    return result
                return subprocess.CompletedProcess(cmd, 1)

            with patch("subprocess.run", side_effect=mock_run):
                result = runner.invoke(app, ["install-hook"])
                assert result.exit_code == 0
                assert "already installed" in result.output

    def test_install_hook_backs_up_existing(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            git_dir = os.path.join(tmpdir, ".git")
            hooks_dir = os.path.join(git_dir, "hooks")
            os.makedirs(hooks_dir)
            hook_path = os.path.join(hooks_dir, "pre-commit")
            with open(hook_path, "w") as f:
                f.write("# existing hook\n")

            def mock_run(cmd, **kwargs):
                if cmd[0] == "git" and cmd[1] == "rev-parse":
                    result = subprocess.CompletedProcess(cmd, 0, stdout=git_dir)
                    return result
                return subprocess.CompletedProcess(cmd, 1)

            with patch("subprocess.run", side_effect=mock_run):
                result = runner.invoke(app, ["install-hook"])
                assert result.exit_code == 0
                assert os.path.exists(hook_path + ".backup")
                assert "backed up" in result.output

# 拆分自 tests/test_adg_cli_v2.py

"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

from tools.scripts.adg_cli import (
    cmd_check,
    cmd_detect,
    cmd_install_hooks,
    cmd_list_rules,
    load_rules_for_language,
)


class TestCmdCheck:
    def test_check_file_with_errors(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = load_rules_for_language("python")
            result = cmd_check(args)
        assert result == 1  # errors found

    def test_check_file_clean(self, tmp_path: Path) -> None:
        f = tmp_path / "good.py"
        f.write_text("x = 1\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_directory(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("x = 1\n")
        args = argparse.Namespace(path=str(tmp_path), lang="python", severity=None, json=False)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_json_output(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=True)
        with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
            mock.return_value = {"anti_patterns": []}
            result = cmd_check(args)
        assert result == 0

    def test_check_unknown_language(self, tmp_path: Path) -> None:
        f = tmp_path / "test.xyz"
        f.write_text("hello")
        args = argparse.Namespace(path=str(f), lang=None, severity=None, json=False)
        result = cmd_check(args)
        assert result == 1

    def test_check_with_framework(self, tmp_path: Path) -> None:
        f = tmp_path / "app.py"
        f.write_text("x = 1\n")
        (tmp_path / "requirements.txt").write_text("Django==4.2\n")
        args = argparse.Namespace(path=str(f), lang="python", severity=None, json=False)
        with (
            patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock_lang,
            patch("tools.scripts.adg_cli.rules.load_framework_rules") as mock_fw,
            patch("tools.scripts.adg_cli.detect.detect_language") as mock_det,
        ):
            mock_lang.return_value = {"anti_patterns": []}
            mock_fw.return_value = {"anti_patterns": []}
            mock_det.return_value = {
                "language": "python",
                "framework": "django",
                "confidence": 0.9,
            }
            result = cmd_check(args)
        assert result == 0


class TestCmdDetect:
    def test_detect_python(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        args = argparse.Namespace(path=str(tmp_path), json=False)
        result = cmd_detect(args)
        assert result == 0

    def test_detect_json_output(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        args = argparse.Namespace(path=str(tmp_path), json=True)
        result = cmd_detect(args)
        assert result == 0

    def test_detect_default_path(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=".", json=False)
        with patch("tools.scripts.adg_cli.detect.detect_language") as mock:
            mock.return_value = {
                "language": "python",
                "framework": None,
                "confidence": 0.9,
            }
            result = cmd_detect(args)
        assert result == 0


class TestCmdListRules:
    def test_list_python_rules(self) -> None:
        args = argparse.Namespace(lang="python", json=False)
        result = cmd_list_rules(args)
        assert result == 0

    def test_list_json_output(self) -> None:
        args = argparse.Namespace(lang="python", json=True)
        result = cmd_list_rules(args)
        assert result == 0

    def test_list_rust_rules(self) -> None:
        args = argparse.Namespace(lang="rust", json=False)
        result = cmd_list_rules(args)
        assert result == 0


class TestCmdInstallHooks:
    def test_install_to_git_repo(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 0
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        assert hook.exists()
        assert "ADG" in hook.read_text()

    def test_install_not_git_repo(self, tmp_path: Path) -> None:
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 1

    def test_install_hook_content(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        args = argparse.Namespace(path=str(tmp_path))
        result = cmd_install_hooks(args)
        assert result == 0
        hook = tmp_path / ".git" / "hooks" / "pre-commit"
        content = hook.read_text()
        assert "#!/bin/bash" in content
        assert "ADG" in content
        assert hook.stat().st_mode & 0o755

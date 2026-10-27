# 拆分自 tests/test_adg_cli_v2.py

"""Phase 27: Comprehensive tests for adg_cli.py (43% -> 80%)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tools.scripts.adg_cli import (
    load_rules_for_language,
    main,
)


class TestMainCLI:
    def test_no_command(self) -> None:
        with patch("sys.argv", ["adg"]):
            result = main()
        assert result == 0

    def test_check_subcommand(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "check", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_detect_subcommand(self, tmp_path: Path) -> None:
        (tmp_path / "pyproject.toml").write_text("[project]\n")
        with patch("sys.argv", ["adg", "detect", str(tmp_path)]):
            result = main()
        assert result == 0

    def test_list_rules_subcommand(self) -> None:
        with patch("sys.argv", ["adg", "list-rules", "--lang", "python"]):
            result = main()
        assert result == 0

    def test_install_hooks_subcommand(self, tmp_path: Path) -> None:
        (tmp_path / ".git" / "hooks").mkdir(parents=True)
        with patch("sys.argv", ["adg", "install-hooks", str(tmp_path)]):
            result = main()
        assert result == 0

    def test_check_json_flag(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "check", str(f), "--lang", "python", "--json"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_detect_json_flag(self, tmp_path: Path) -> None:
        (tmp_path / "Cargo.toml").write_text("[package]\n")
        with patch("sys.argv", ["adg", "detect", str(tmp_path), "--json"]):
            result = main()
        assert result == 0

    def test_check_severity_flag(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch(
            "sys.argv",
            ["adg", "check", str(f), "--lang", "python", "--severity", "error"],
        ):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 1

    def test_report_clean_code(self, tmp_path: Path) -> None:
        """Test report on clean code passes."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_report_with_errors(self, tmp_path: Path) -> None:
        """Test report on code with errors fails."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 1

    def test_report_json_output(self, tmp_path: Path) -> None:
        """Test report JSON output."""
        f = tmp_path / "test.py"
        f.write_text("x = 1\n")
        with patch("sys.argv", ["adg", "report", str(f), "--lang", "python", "--json"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = {"anti_patterns": []}
                result = main()
        assert result == 0

    def test_report_with_threshold(self, tmp_path: Path) -> None:
        """Test report with error threshold."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch(
            "sys.argv",
            ["adg", "report", str(f), "--lang", "python", "--error-threshold", "10"],
        ):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        assert result == 0  # Should pass with high threshold

    def test_report_nonexistent_path(self, tmp_path: Path) -> None:
        """Test report on nonexistent path."""
        with patch(
            "sys.argv",
            ["adg", "report", str(tmp_path / "nonexistent"), "--lang", "python"],
        ):
            result = main()
        assert result == 1

    def test_fix_python_bare_except(self, tmp_path: Path) -> None:
        """Test fix Python bare except."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "python"]):
            result = main()
        assert result == 0
        content = f.read_text()
        assert "except Exception:" in content
        assert "except:" not in content

    def test_fix_javascript_equality(self, tmp_path: Path) -> None:
        """Test fix JavaScript equality operators."""
        f = tmp_path / "app.js"
        f.write_text("if (x == null) {}\nif (y != undefined) {}\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "javascript"]):
            result = main()
        assert result == 0
        content = f.read_text()
        assert "=== null" in content
        assert "!== undefined" in content

    def test_fix_json_output(self, tmp_path: Path) -> None:
        """Test fix JSON output."""
        f = tmp_path / "test.py"
        f.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(f), "--lang", "python", "--json"]):
            result = main()
        assert result == 0

    def test_fix_nonexistent_path(self, tmp_path: Path) -> None:
        """Test fix on nonexistent path."""
        with patch(
            "sys.argv",
            ["adg", "fix", str(tmp_path / "nonexistent"), "--lang", "python"],
        ):
            result = main()
        assert result == 1

    def test_fix_directory(self, tmp_path: Path) -> None:
        """Test fix on directory."""
        f1 = tmp_path / "test1.py"
        f1.write_text("try:\n    pass\nexcept:\n    pass\n")
        f2 = tmp_path / "test2.py"
        f2.write_text("try:\n    pass\nexcept:\n    pass\n")
        with patch("sys.argv", ["adg", "fix", str(tmp_path), "--lang", "python"]):
            result = main()
        assert result == 0
        assert "except Exception:" in f1.read_text()
        assert "except Exception:" in f2.read_text()

    def test_install_hooks_pre_push(self, tmp_path: Path) -> None:
        """Test pre-push hook installation."""
        (tmp_path / ".git").mkdir()
        (tmp_path / ".git" / "hooks").mkdir()
        with patch("sys.argv", ["adg", "install-hooks", str(tmp_path), "--pre-push"]):
            result = main()
        assert result == 0
        assert (tmp_path / ".git" / "hooks" / "pre-push").exists()

    def test_project_config_custom_rules(self, tmp_path: Path, capsys) -> None:
        """Test project config with custom rules."""
        # Create project config
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "rules.yml"
        config_file.write_text(
            "anti_patterns:\n"
            "- id: no-print\n"
            "  name: No print\n"
            "  severity: warning\n"
            "  pattern: '\\bprint\\('\n"
            "  message: Use logging\n"
        )

        # Create test file
        test_file = tmp_path / "app.py"
        test_file.write_text("print('hello')\n")

        with patch("sys.argv", ["adg", "check", str(tmp_path), "--lang", "python"]):
            result = main()
        assert result == 0  # warning only, no errors
        # 内容级断言: 自定义规则必须真实触发并出现在人读输出中,
        # 不能只验证退出码 —— 规则死亡时退出码同样是 0
        out = capsys.readouterr().out
        assert "no-print" in out
        assert "Use logging" in out

    def test_project_config_skip_patterns(self, tmp_path: Path) -> None:
        """Test project config skip patterns."""
        # Create project config
        config_dir = tmp_path / ".adg"
        config_dir.mkdir()
        config_file = config_dir / "rules.yml"
        config_file.write_text("skip_patterns:\n- '*.test.py'\n")

        # Create test files
        test_file = tmp_path / "app.py"
        test_file.write_text("try:\n    pass\nexcept:\n    pass\n")
        skipped_file = tmp_path / "app.test.py"
        skipped_file.write_text("try:\n    pass\nexcept:\n    pass\n")

        with patch("sys.argv", ["adg", "check", str(tmp_path), "--lang", "python"]):
            with patch("tools.scripts.adg_cli.rules.load_rules_for_language") as mock:
                mock.return_value = load_rules_for_language("python")
                result = main()
        # Only app.py should be checked, app.test.py should be skipped
        assert result == 1  # error in app.py only

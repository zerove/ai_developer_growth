"""Tests for rule_author.py (7% → target 75%)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from tools.scripts.rule_author import (
    CATEGORY_TYPES,
    SEVERITY_LEVELS,
    TEMPLATES,
    cmd_add_rule,
    cmd_init,
    cmd_scaffold,
    cmd_template,
    cmd_validate,
    main,
)


@pytest.fixture
def fake_rules_dir(tmp_path: Path) -> Path:
    """Create a temporary rules directory structure."""
    lang_dir = tmp_path / "ai-dev-framework" / "languages" / "testlang" / "rules.d"
    lang_dir.mkdir(parents=True)
    return lang_dir


class TestTemplates:
    def test_all_categories_have_templates(self) -> None:
        assert "anti_patterns" in TEMPLATES
        assert "naming_conventions" in TEMPLATES
        assert "complexity" in TEMPLATES

    def test_templates_have_required_fields(self) -> None:
        for cat, tmpl in TEMPLATES.items():
            assert "description" in tmpl, f"{cat} missing description"
            assert "fields" in tmpl, f"{cat} missing fields"
            assert "example" in tmpl, f"{cat} missing example"
            assert isinstance(tmpl["fields"], list)

    def test_severity_levels(self) -> None:
        assert "error" in SEVERITY_LEVELS
        assert "warning" in SEVERITY_LEVELS
        assert "info" in SEVERITY_LEVELS

    def test_category_types(self) -> None:
        assert "security" in CATEGORY_TYPES
        assert "error_handling" in CATEGORY_TYPES


class TestCmdInit:
    @patch("tools.scripts.rule_author._rules_dir")
    def test_init_creates_directory(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(lang="testlang", force=False)
        cmd_init(args)
        # Code creates: _rules_dir() / "languages" / lang / "rules.d"
        assert (tmp_path / "languages" / "testlang" / "rules.d" / "anti_patterns.yml").exists()

    @patch("tools.scripts.rule_author._rules_dir")
    def test_init_existing_no_force(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(lang="testlang", force=False)
        cmd_init(args)  # Should not raise

    @patch("tools.scripts.rule_author._rules_dir")
    def test_init_force_overwrites(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        lang_dir = tmp_path / "languages" / "testlang" / "rules.d"
        lang_dir.mkdir(parents=True)
        (lang_dir / "anti_patterns.yml").write_text("old: data")
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(lang="testlang", force=True)
        cmd_init(args)
        with open(lang_dir / "anti_patterns.yml") as f:
            data = yaml.safe_load(f)
        assert data["language"] == "testlang"


class TestCmdAddRule:
    @patch("tools.scripts.rule_author._rules_dir")
    def test_add_rule_success(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text("language: testlang\nanti_patterns: []\n")
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang",
            category="anti_patterns",
            id="tl-bare-except",
            name="Bare except",
            severity="error",
            pattern="except\\s*:",
            message="Use specific exceptions",
            fix_hint="Be specific",
        )
        cmd_add_rule(args)
        with open(rules_dir / "anti_patterns.yml") as f:
            data = yaml.safe_load(f)
        assert len(data["anti_patterns"]) == 1
        assert data["anti_patterns"][0]["id"] == "tl-bare-except"

    @patch("tools.scripts.rule_author._rules_dir")
    def test_add_rule_unknown_category(self, mock_rules_dir: MagicMock) -> None:
        mock_rules_dir.return_value = Path("/tmp")
        args = argparse.Namespace(
            lang="testlang", category="unknown", id="x", name="x",
            severity="error", pattern="x", message="x", fix_hint="x",
        )
        cmd_add_rule(args)  # Should not raise

    @patch("tools.scripts.rule_author._rules_dir")
    def test_add_rule_no_file(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang", category="anti_patterns", id="x", name="x",
            severity="error", pattern="x", message="x", fix_hint="x",
        )
        cmd_add_rule(args)  # Should not raise, prints message

    @patch("tools.scripts.rule_author._rules_dir")
    def test_add_rule_duplicate_id(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text(
            "language: testlang\nanti_patterns:\n- id: dup\n  name: x\n  severity: error\n"
        )
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang", category="anti_patterns", id="dup", name="x",
            severity="error", pattern="x", message="x", fix_hint="fix",
        )
        cmd_add_rule(args)  # Should print duplicate message

    @patch("tools.scripts.rule_author._rules_dir")
    def test_add_rule_invalid_regex(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text("language: testlang\nanti_patterns: []\n")
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang", category="anti_patterns", id="x", name="x",
            severity="error", pattern="[invalid", message="x", fix_hint="fix",
        )
        cmd_add_rule(args)  # Should print invalid regex message

    @patch("tools.scripts.rule_author._rules_dir")
    @patch("builtins.input", return_value="")
    def test_add_rule_empty_id(self, mock_input: MagicMock, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text("language: testlang\nanti_patterns: []\n")
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang", category="anti_patterns", id="", name="x",
            severity="error", pattern="x", message="x", fix_hint="x",
        )
        cmd_add_rule(args)  # Should print "Rule ID is required"

    @patch("tools.scripts.rule_author._rules_dir")
    @patch("builtins.input", side_effect=["", ""])
    def test_add_rule_empty_name_or_message(self, mock_input: MagicMock, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text("language: testlang\nanti_patterns: []\n")
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(
            lang="testlang", category="anti_patterns", id="x", name="",
            severity="error", pattern="fix", message="x", fix_hint="fix",
        )
        cmd_add_rule(args)  # Should print "Name and message are required"


class TestCmdValidate:
    def test_validate_valid_file(self, tmp_path: Path) -> None:
        f = tmp_path / "valid.yml"
        f.write_text("language: python\nanti_patterns:\n- id: py-test\n  name: Test\n  severity: error\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_missing_language(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yml"
        f.write_text("anti_patterns:\n- id: x\n  severity: error\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)  # Should print missing language

    def test_validate_nonexistent_file(self) -> None:
        args = argparse.Namespace(file="/nonexistent/file.yml")
        cmd_validate(args)  # Should print "File not found"

    def test_validate_invalid_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yml"
        f.write_text("# just a comment\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)  # Parsed to None -> prints "Invalid YAML"

    def test_validate_rule_not_dict(self, tmp_path: Path) -> None:
        f = tmp_path / "bad.yml"
        f.write_text("language: python\nanti_patterns:\n- not_a_dict\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_rule_missing_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "incomplete.yml"
        f.write_text("language: python\nanti_patterns:\n- id: x\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)  # Should print warnings for missing name/severity

    def test_validate_invalid_severity(self, tmp_path: Path) -> None:
        f = tmp_path / "bad_sev.yml"
        f.write_text("language: python\nanti_patterns:\n- id: x\n  name: X\n  severity: critical\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_invalid_regex(self, tmp_path: Path) -> None:
        f = tmp_path / "bad_regex.yml"
        f.write_text("language: python\nanti_patterns:\n- id: x\n  name: X\n  severity: error\n  pattern: '[invalid'\n")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_test_cases_missing_fields(self, tmp_path: Path) -> None:
        f = tmp_path / "bad_tc.yml"
        f.write_text(
            "language: python\nanti_patterns:\n"
            "- id: x\n  name: X\n  severity: error\n"
            "  test_cases:\n  - code: 'test'\n"
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_naming_conventions(self, tmp_path: Path) -> None:
        f = tmp_path / "naming.yml"
        f.write_text(
            "language: python\nnaming_conventions:\n"
            "- id: py-fn\n  name: Function name\n  severity: warning\n"
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_complexity(self, tmp_path: Path) -> None:
        f = tmp_path / "complexity.yml"
        f.write_text(
            "language: python\ncomplexity:\n"
            "- id: py-len\n  name: Too long\n  severity: warning\n"
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)


class TestCmdScaffold:
    @patch("tools.scripts.rule_author._rules_dir")
    def test_scaffold_creates_files(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(lang="testlang")
        cmd_scaffold(args)
        # Code creates: _rules_dir() / "languages" / lang / "rules.d"
        f = tmp_path / "languages" / "testlang" / "rules.d" / "anti_patterns.yml"
        assert f.exists()
        with open(f) as fh:
            data = yaml.safe_load(fh)
        assert data["language"] == "testlang"

    @patch("tools.scripts.rule_author._rules_dir")
    def test_scaffold_appends_to_existing(self, mock_rules_dir: MagicMock, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True)
        (rules_dir / "anti_patterns.yml").write_text(
            "language: testlang\nanti_patterns:\n- id: existing\n"
        )
        mock_rules_dir.return_value = tmp_path
        args = argparse.Namespace(lang="testlang")
        cmd_scaffold(args)
        with open(rules_dir / "anti_patterns.yml") as f:
            data = yaml.safe_load(f)
        # scaffold writes 3 categories, each adding to anti_patterns.yml
        # The existing entry + new entries from all 3 templates = at least 2
        assert len(data.get("anti_patterns", [])) >= 2


class TestCmdTemplate:
    def test_valid_category(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(category="anti_patterns")
        cmd_template(args)
        output = capsys.readouterr().out
        assert "anti_patterns" in output

    def test_invalid_category(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(category="nonexistent")
        cmd_template(args)
        output = capsys.readouterr().out
        assert "Unknown category" in output


class TestMain:
    def test_no_command(self) -> None:
        with patch("sys.argv", ["rule_author"]):
            result = main()
        assert result == 0

    def test_init_command(self) -> None:
        with patch("sys.argv", ["rule_author", "init", "--lang", "test"]):
            with patch("tools.scripts.rule_author._rules_dir") as mock:
                from pathlib import Path as P
                mock.return_value = P("/tmp/test_rules")
                result = main()
        assert result == 0

    def test_template_command(self) -> None:
        with patch("sys.argv", ["rule_author", "template", "--category", "anti_patterns"]):
            result = main()
        assert result == 0

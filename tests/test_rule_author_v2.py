"""Tests for rule_author.py (0% → target 85%)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

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


class TestCmdInit:
    """Tests for cmd_init()."""

    def test_init_creates_directory(self, tmp_path: Path) -> None:
        args = argparse.Namespace(lang="testlang", force=False)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_init(args)
            assert (
                tmp_path / "languages" / "testlang" / "rules.d" / "anti_patterns.yml"
            ).exists()

    def test_init_existing_no_force(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "anti_patterns.yml").write_text("existing")
        args = argparse.Namespace(lang="testlang", force=False)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_init(args)
            assert (rules_dir / "anti_patterns.yml").read_text() == "existing"

    def test_init_existing_with_force(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / "languages" / "testlang" / "rules.d"
        rules_dir.mkdir(parents=True, exist_ok=True)
        args = argparse.Namespace(lang="testlang", force=True)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_init(args)
            assert (rules_dir / "anti_patterns.yml").exists()


class TestCmdAddRule:
    """Tests for cmd_add_rule()."""

    def _make_args(self, tmp_path: Path, **kwargs) -> argparse.Namespace:
        rules_dir = tmp_path / "languages" / "python" / "rules.d"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "anti_patterns.yml").write_text(
            "language: python\nanti_patterns: []\n"
        )
        defaults = {
            "lang": "python",
            "category": "anti_patterns",
            "id": "py-test-rule",
            "name": "Test Rule",
            "severity": "warning",
            "message": "Test message",
            "pattern": "test.*pattern",
            "fix_hint": "Fix it",
        }
        defaults.update(kwargs)
        return argparse.Namespace(**defaults)

    def test_add_rule_success(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)

    def test_add_rule_unknown_category(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, category="unknown_cat")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)

    def test_add_rule_no_file(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            # Remove the rules file
            (
                tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml"
            ).unlink()
            cmd_add_rule(args)

    def test_add_rule_no_id(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, id=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=["py-new-rule"]):
                cmd_add_rule(args)

    def test_add_rule_empty_id(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, id=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=[""]):
                cmd_add_rule(args)

    def test_add_rule_no_name(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, name=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch(
                "builtins.input", side_effect=["test-name", "warning", "msg", "", ""]
            ):
                cmd_add_rule(args)

    def test_add_rule_invalid_regex(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, pattern="[invalid")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)

    def test_add_rule_duplicate_id(self, tmp_path: Path) -> None:
        import yaml as _yaml

        rules_file = tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml"
        rules_file.parent.mkdir(parents=True, exist_ok=True)
        rules_file.write_text(
            _yaml.dump({"language": "python", "anti_patterns": [{"id": "py-dup"}]})
        )
        args = self._make_args(tmp_path, id="py-dup")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)

    def test_add_rule_no_pattern(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, pattern=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=["", ""]):
                cmd_add_rule(args)


class TestCmdValidate:
    """Tests for cmd_validate()."""

    def test_validate_valid_file(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "valid.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"id": "py-test", "severity": "error"}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_missing_file(self, tmp_path: Path) -> None:
        args = argparse.Namespace(file=str(tmp_path / "nope.yml"))
        cmd_validate(args)

    def test_validate_missing_language(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "nolang.yml"
        f.write_text(_yaml.dump({"anti_patterns": [{"id": "x", "severity": "error"}]}))
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_invalid_severity(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "badsev.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"id": "x", "severity": "critical"}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_invalid_regex(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "badregex.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [
                        {"id": "x", "severity": "error", "pattern": "[invalid"}
                    ],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_missing_test_code(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "badtc.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [
                        {
                            "id": "x",
                            "severity": "error",
                            "test_cases": [{"should_match": True}],
                        }
                    ],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_missing_test_should_match(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "badsm.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [
                        {"id": "x", "severity": "error", "test_cases": [{"code": "x"}]}
                    ],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_not_a_dict(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "notdict.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": ["just-a-string"],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_missing_id(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "noid.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"severity": "error", "name": "x"}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)

    def test_validate_empty_yaml(self, tmp_path: Path) -> None:
        f = tmp_path / "empty.yml"
        f.write_text("")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)


class TestCmdScaffold:
    """Tests for cmd_scaffold()."""

    def test_scaffold_creates_files(self, tmp_path: Path) -> None:
        args = argparse.Namespace(lang="mylang")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_scaffold(args)
            assert (
                tmp_path / "languages" / "mylang" / "rules.d" / "anti_patterns.yml"
            ).exists()

    def test_scaffold_appends_to_existing(self, tmp_path: Path) -> None:
        import yaml as _yaml

        rules_dir = tmp_path / "languages" / "mylang" / "rules.d"
        rules_dir.mkdir(parents=True, exist_ok=True)
        (rules_dir / "anti_patterns.yml").write_text(
            _yaml.dump(
                {
                    "language": "mylang",
                    "anti_patterns": [{"id": "existing"}],
                }
            )
        )
        args = argparse.Namespace(lang="mylang")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_scaffold(args)


class TestCmdTemplate:
    """Tests for cmd_template()."""

    def test_template_valid_category(self) -> None:
        for cat in TEMPLATES:
            args = argparse.Namespace(category=cat)
            cmd_template(args)

    def test_template_unknown_category(self) -> None:
        args = argparse.Namespace(category="unknown")
        cmd_template(args)


class TestMain:
    """Tests for main() CLI."""

    def test_no_command(self) -> None:
        with patch("sys.argv", ["prog"]):
            ret = main()
            assert ret == 0

    def test_init_command(self, tmp_path: Path) -> None:
        with patch("sys.argv", ["prog", "init", "--lang", "test"]):
            with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
                mock_dir.return_value = tmp_path
                ret = main()
                assert ret == 0

    def test_validate_command(self, tmp_path: Path) -> None:
        import yaml as _yaml

        f = tmp_path / "rules.yml"
        f.write_text(_yaml.dump({"language": "python"}))
        with patch("sys.argv", ["prog", "validate", "--file", str(f)]):
            ret = main()
            assert ret == 0

    def test_template_command(self) -> None:
        with patch("sys.argv", ["prog", "template", "--category", "anti_patterns"]):
            ret = main()
            assert ret == 0

    def test_scaffold_command(self, tmp_path: Path) -> None:
        with patch("sys.argv", ["prog", "scaffold", "--lang", "rust"]):
            with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
                mock_dir.return_value = tmp_path
                ret = main()
                assert ret == 0


class TestConstants:
    """Tests for module constants."""

    def test_severity_levels(self) -> None:
        assert "error" in SEVERITY_LEVELS
        assert "warning" in SEVERITY_LEVELS
        assert "info" in SEVERITY_LEVELS

    def test_category_types(self) -> None:
        assert len(CATEGORY_TYPES) >= 5

    def test_templates(self) -> None:
        assert "anti_patterns" in TEMPLATES
        assert "naming_conventions" in TEMPLATES
        assert "complexity" in TEMPLATES
        for t in TEMPLATES.values():
            assert "description" in t
            assert "fields" in t
            assert "example" in t

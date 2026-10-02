"""Tests for rule_author.py (0% → target 85%)."""

from __future__ import annotations

import argparse
import re
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
            assert (tmp_path / "languages" / "testlang" / "rules.d" / "anti_patterns.yml").exists()

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
        (rules_dir / "anti_patterns.yml").write_text("language: python\nanti_patterns: []\n")
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

    def _rule_ids(self, tmp_path: Path) -> list[str]:
        """读回规则文件里的 id 列表，用于断言真实副作用。"""
        import yaml as _yaml

        f = tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml"
        data = _yaml.safe_load(f.read_text()) or {}
        return [r.get("id") for r in data.get("anti_patterns", [])]

    def test_add_rule_success(self, tmp_path: Path, capsys) -> None:
        args = self._make_args(tmp_path)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)
        assert self._rule_ids(tmp_path) == ["py-test-rule"]
        assert "Added rule 'py-test-rule'" in capsys.readouterr().out

    def test_add_rule_unknown_category(self, tmp_path: Path, capsys) -> None:
        args = self._make_args(tmp_path, category="unknown_cat")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)
        assert "Unknown category" in capsys.readouterr().out
        assert self._rule_ids(tmp_path) == []

    def test_add_rule_no_file(self, tmp_path: Path, capsys) -> None:
        args = self._make_args(tmp_path)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            # Remove the rules file
            (tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml").unlink()
            cmd_add_rule(args)
        assert "Rule file not found" in capsys.readouterr().out

    def test_add_rule_no_id(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, id=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=["py-new-rule"]):
                cmd_add_rule(args)
        assert "py-new-rule" in self._rule_ids(tmp_path)

    def test_add_rule_empty_id(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, id=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=[""]):
                cmd_add_rule(args)
        assert self._rule_ids(tmp_path) == []

    def test_add_rule_no_name(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, name=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=["test-name", "warning", "msg", "", ""]):
                cmd_add_rule(args)
        import yaml as _yaml

        data = _yaml.safe_load((tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml").read_text())
        assert [r["name"] for r in data["anti_patterns"]] == ["test-name"]

    def test_add_rule_invalid_regex(self, tmp_path: Path) -> None:
        args = self._make_args(tmp_path, pattern="[invalid")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)
        assert self._rule_ids(tmp_path) == []

    def test_add_rule_duplicate_id(self, tmp_path: Path, capsys) -> None:
        import yaml as _yaml

        args = self._make_args(tmp_path, id="py-dup")
        # 必须在 _make_args 之后写：它会重建并覆盖规则文件，
        # 先写再调 _make_args 会把已存在的规则抹掉，场景就不成立了。
        rules_file = tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml"
        rules_file.write_text(_yaml.dump({"language": "python", "anti_patterns": [{"id": "py-dup"}]}))
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_add_rule(args)
        assert "already exists" in capsys.readouterr().out
        assert self._rule_ids(tmp_path) == ["py-dup"]

    def test_add_rule_no_pattern(self, tmp_path: Path) -> None:
        """pattern 是可选字段：为空时 _validate_pattern 直接放行，且 _build_rule 不写该键。"""
        args = self._make_args(tmp_path, pattern=None)
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            with patch("builtins.input", side_effect=["", ""]):
                cmd_add_rule(args)
        assert self._rule_ids(tmp_path) == ["py-test-rule"]
        import yaml as _yaml

        data = _yaml.safe_load((tmp_path / "languages" / "python" / "rules.d" / "anti_patterns.yml").read_text())
        assert "pattern" not in data["anti_patterns"][0]


def _errors_reported(out: str) -> bool:
    """从汇总行 `N errors, M warnings` 判断是否报出了 error。"""
    m = re.search(r"(\d+) errors?, (\d+) warnings?", out)
    assert m is not None, f"no summary line in output: {out!r}"
    return int(m.group(1)) >= 1


class TestCmdValidate:
    """Tests for cmd_validate()."""

    def test_validate_valid_file(self, tmp_path: Path, capsys) -> None:
        import yaml as _yaml

        f = tmp_path / "valid.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"id": "py-test", "name": "Test", "severity": "error"}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)
        assert "Valid" in capsys.readouterr().out

    def test_validate_missing_file(self, tmp_path: Path, capsys) -> None:
        args = argparse.Namespace(file=str(tmp_path / "nope.yml"))
        cmd_validate(args)
        assert "File not found" in capsys.readouterr().out

    def test_validate_missing_language(self, tmp_path: Path, capsys) -> None:
        import yaml as _yaml

        f = tmp_path / "nolang.yml"
        f.write_text(_yaml.dump({"anti_patterns": [{"id": "x", "severity": "error"}]}))
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)
        out = capsys.readouterr().out
        assert "Missing 'language' field" in out
        assert "1 errors" in out

    def test_validate_invalid_severity(self, tmp_path: Path, capsys) -> None:
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
        assert _errors_reported(capsys.readouterr().out)

    def test_validate_invalid_regex(self, tmp_path: Path, capsys) -> None:
        import yaml as _yaml

        f = tmp_path / "badregex.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"id": "x", "severity": "error", "pattern": "[invalid"}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)
        assert _errors_reported(capsys.readouterr().out)

    def test_validate_missing_test_code(self, tmp_path: Path, capsys) -> None:
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
        assert _errors_reported(capsys.readouterr().out)

    def test_validate_missing_test_should_match(self, tmp_path: Path, capsys) -> None:
        import yaml as _yaml

        f = tmp_path / "badsm.yml"
        f.write_text(
            _yaml.dump(
                {
                    "language": "python",
                    "anti_patterns": [{"id": "x", "severity": "error", "test_cases": [{"code": "x"}]}],
                }
            )
        )
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)
        assert _errors_reported(capsys.readouterr().out)

    def test_validate_not_a_dict(self, tmp_path: Path, capsys) -> None:
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
        assert "is not a dictionary" in capsys.readouterr().out

    def test_validate_missing_id(self, tmp_path: Path, capsys) -> None:
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
        assert _errors_reported(capsys.readouterr().out)

    def test_validate_empty_yaml(self, tmp_path: Path, capsys) -> None:
        f = tmp_path / "empty.yml"
        f.write_text("")
        args = argparse.Namespace(file=str(f))
        cmd_validate(args)
        assert "Invalid YAML" in capsys.readouterr().out


class TestCmdScaffold:
    """Tests for cmd_scaffold()."""

    def test_scaffold_creates_files(self, tmp_path: Path) -> None:
        args = argparse.Namespace(lang="mylang")
        with patch("tools.scripts.rule_author._rules_dir") as mock_dir:
            mock_dir.return_value = tmp_path
            cmd_scaffold(args)
        assert (tmp_path / "languages" / "mylang" / "rules.d" / "anti_patterns.yml").exists()

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
        data = _yaml.safe_load((rules_dir / "anti_patterns.yml").read_text())
        ids = [r.get("id") for r in data["anti_patterns"]]
        assert "existing" in ids, "scaffold 覆盖了既有规则"
        assert len(ids) > 1, "scaffold 没有追加模板规则"


class TestCmdTemplate:
    """Tests for cmd_template()."""

    def test_template_valid_category(self, capsys) -> None:
        for cat in TEMPLATES:
            args = argparse.Namespace(category=cat)
            cmd_template(args)
            out = capsys.readouterr().out
            assert out.strip(), f"category {cat} 未输出任何模板内容"

    def test_template_unknown_category(self, capsys) -> None:
        args = argparse.Namespace(category="unknown")
        cmd_template(args)
        out = capsys.readouterr().out
        assert "Unknown" in out or "unknown" in out
        assert "id:" not in out, "未知类别不应输出规则模板"


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

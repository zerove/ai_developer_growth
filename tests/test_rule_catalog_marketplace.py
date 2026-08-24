"""Tests for rule_catalog.py and rule_marketplace.py - marketplace core and CLI."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from unittest import mock

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

from rule_catalog import (
    BUILTIN_PACKS,
    export_rules,
    get_pack_info,
    get_pack_source,
    install_pack,
    matches,
    search_rules,
    validate_rules,
)
from rule_marketplace import (
    cmd_export,
    cmd_info,
    cmd_install,
    cmd_list,
    cmd_search,
    cmd_validate,
    main,
)

# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────


@pytest.fixture
def fw_dir(tmp_path: Path) -> Path:
    """Create a mock framework directory."""
    d = tmp_path / "framework"

    # Common security rules
    common = d / "common"
    common.mkdir(parents=True)
    (common / "security.yml").write_text(
        yaml.dump(
            {
                "anti_patterns": [
                    {
                        "id": "cs-sql-inject",
                        "name": "SQL injection",
                        "severity": "error",
                        "category": "security",
                        "pattern": "SELECT.*FROM",
                        "message": "Use parameterized queries",
                    }
                ]
            }
        )
    )

    # Python rules
    py_dir = d / "languages" / "python" / "rules.d"
    py_dir.mkdir(parents=True)
    (py_dir / "anti_patterns.yml").write_text(
        yaml.dump(
            {
                "anti_patterns": [
                    {
                        "id": "py-eval",
                        "name": "eval usage",
                        "severity": "error",
                        "category": "security",
                        "pattern": r"\beval\s*\(",
                        "message": "eval is dangerous",
                    }
                ],
                "naming_conventions": [
                    {
                        "id": "py-naming",
                        "name": "function naming",
                        "severity": "warning",
                        "category": "naming",
                        "message": "Use snake_case",
                    }
                ],
            }
        )
    )

    # Framework rules (React)
    react_dir = d / "frameworks" / "react" / "rules.d"
    react_dir.mkdir(parents=True)
    (react_dir / "anti_patterns.yml").write_text(
        yaml.dump(
            {
                "anti_patterns": [
                    {
                        "id": "react-setstate",
                        "name": "setState in render",
                        "severity": "error",
                        "category": "anti_patterns",
                        "pattern": "setState",
                        "message": "Don't call setState in render",
                    }
                ]
            }
        )
    )

    return d


# ──────────────────────────────────────────────────────────
# Tests for matches()
# ──────────────────────────────────────────────────────────


class TestMatches:
    def test_match_in_id(self) -> None:
        assert matches({"id": "py-eval"}, "eval") is True

    def test_match_in_message(self) -> None:
        assert matches({"message": "Use ast.literal_eval"}, "literal") is True

    def test_match_in_pattern(self) -> None:
        assert matches({"pattern": r"\beval\s*\("}, "eval") is True

    def test_match_in_fix_hint(self) -> None:
        assert matches({"fix_hint": "Use subprocess.run"}, "subprocess") is True

    def test_match_in_category(self) -> None:
        assert matches({"category": "security"}, "security") is True

    def test_match_in_tags(self) -> None:
        assert matches({"tags": ["python", "security"]}, "python") is True

    def test_no_match(self) -> None:
        assert matches({"id": "py-eval"}, "nonexistent") is False

    def test_empty_rule(self) -> None:
        assert matches({}, "anything") is False

    def test_case_insensitive(self) -> None:
        assert matches({"id": "PY-EVAL"}, "py-eval") is True


# ──────────────────────────────────────────────────────────
# Tests for search_rules()
# ──────────────────────────────────────────────────────────


class TestSearchRules:
    def test_search_common(self, fw_dir: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            results = search_rules("sql")
        assert len(results) >= 1
        assert any(r["id"] == "cs-sql-inject" for r in results)

    def test_search_language(self, fw_dir: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            results = search_rules("eval")
        assert len(results) >= 1
        assert any(r["id"] == "py-eval" for r in results)

    def test_search_framework(self, fw_dir: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            results = search_rules("setstate")
        assert len(results) >= 1
        assert any(r["id"] == "react-setstate" for r in results)

    def test_search_no_results(self, fw_dir: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            results = search_rules("zzz_nonexistent_zzz")
        assert results == []


# ──────────────────────────────────────────────────────────
# Tests for pack operations
# ──────────────────────────────────────────────────────────


class TestGetPackInfo:
    def test_existing_pack(self) -> None:
        info = get_pack_info("security")
        assert info is not None
        assert info["name"] == "Security Rules"

    def test_nonexistent_pack(self) -> None:
        assert get_pack_info("nonexistent") is None


class TestGetPackSource:
    def test_existing_pack(self) -> None:
        src = get_pack_source("security")
        assert src is not None
        assert src.name == "security.yml"

    def test_nonexistent_pack(self) -> None:
        assert get_pack_source("nonexistent") is None


class TestInstallPack:
    def test_install_file(self, fw_dir: Path, tmp_path: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            installed = install_pack("security", tmp_path)
        assert len(installed) == 1
        assert installed[0].exists()

    def test_install_dry_run(self, fw_dir: Path, tmp_path: Path) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            installed = install_pack("security", tmp_path, dry_run=True)
        assert installed == []

    def test_install_nonexistent_raises(self, tmp_path: Path) -> None:
        with pytest.raises(ValueError, match="Unknown pack"):
            install_pack("nonexistent", tmp_path)


class TestValidateRules:
    def test_valid_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "valid.yml").write_text(
            yaml.dump(
                {
                    "anti_patterns": [
                        {
                            "id": "test-rule",
                            "severity": "error",
                            "pattern": "x",
                            "message": "bad",
                        }
                    ]
                }
            )
        )
        total, errors, msgs = validate_rules(rules_dir)
        assert total == 1
        assert errors == 0

    def test_missing_id(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text(
            yaml.dump({"anti_patterns": [{"severity": "error", "pattern": "x", "message": "bad"}]})
        )
        total, errors, msgs = validate_rules(rules_dir)
        assert errors >= 1
        assert any("missing 'id'" in m for m in msgs)

    def test_empty_yaml(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "empty.yml").write_text("")
        total, errors, msgs = validate_rules(rules_dir)
        assert errors >= 1

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        total, errors, msgs = validate_rules(tmp_path / "nonexistent")
        assert total == 0
        assert errors == 0

    def test_yaml_parse_error(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "bad.yml").write_text("not: valid: yaml: [")
        total, errors, msgs = validate_rules(rules_dir)
        assert errors >= 1


class TestExportRules:
    def test_export(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "a.yml").write_text(
            yaml.dump({"anti_patterns": [{"id": "a1"}], "naming_conventions": [{"id": "n1"}]})
        )
        (rules_dir / "b.yml").write_text(yaml.dump({"complexity": [{"id": "c1"}]}))
        total, combined = export_rules(rules_dir, tmp_path / "out.yml")
        assert total == 3
        assert len(combined["anti_patterns"]) == 1
        assert len(combined["naming_conventions"]) == 1
        assert len(combined["complexity"]) == 1


# ──────────────────────────────────────────────────────────
# Tests for rule_marketplace CLI commands
# ──────────────────────────────────────────────────────────


class TestCmdList:
    def test_text_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(json=False)
        cmd_list(args)
        out = capsys.readouterr().out
        assert "Pack ID" in out
        assert "security" in out

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(json=True)
        cmd_list(args)
        out = capsys.readouterr().out
        data = yaml.safe_load(out)
        assert isinstance(data, list)
        assert len(data) == len(BUILTIN_PACKS)


class TestCmdSearch:
    def test_search(self, fw_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            args = argparse.Namespace(query="eval", json=False)
            cmd_search(args)
        out = capsys.readouterr().out
        assert "matching" in out

    def test_search_json(self, fw_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            args = argparse.Namespace(query="eval", json=True)
            cmd_search(args)
        out = capsys.readouterr().out
        data = yaml.safe_load(out)
        assert isinstance(data, list)


class TestCmdInfo:
    def test_existing_pack(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(pack="security", json=False)
        cmd_info(args)
        out = capsys.readouterr().out
        assert "Security Rules" in out

    def test_nonexistent_pack(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(pack="nonexistent", json=False)
        cmd_info(args)
        out = capsys.readouterr().out
        assert "Unknown pack" in out

    def test_json_output(self, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(pack="security", json=True)
        cmd_info(args)
        out = capsys.readouterr().out
        data = yaml.safe_load(out)
        assert "security" in data


class TestCmdInstall:
    def test_install(self, fw_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            args = argparse.Namespace(pack="security", dry_run=False, project_dir=str(tmp_path))
            cmd_install(args)
        out = capsys.readouterr().out
        assert "Installed" in out or "installed" in out

    def test_dry_run(self, fw_dir: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("rule_catalog.framework_dir", return_value=fw_dir):
            args = argparse.Namespace(pack="security", dry_run=True, project_dir=str(tmp_path))
            cmd_install(args)
        out = capsys.readouterr().out
        assert "dry-run" in out


class TestCmdValidate:
    def test_no_rules_dir(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(project_dir=str(tmp_path))
        cmd_validate(args)
        out = capsys.readouterr().out
        assert "No .ai-rules" in out or "not found" in out.lower()

    def test_valid_rules(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "ok.yml").write_text(
            yaml.dump({"anti_patterns": [{"id": "x", "severity": "error", "pattern": "y", "message": "z"}]})
        )
        args = argparse.Namespace(project_dir=str(tmp_path))
        cmd_validate(args)
        out = capsys.readouterr().out
        assert "valid" in out.lower() or "passed" in out.lower() or "All rules" in out


class TestCmdExport:
    def test_no_rules_dir(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = argparse.Namespace(project_dir=str(tmp_path), output=None, dry_run=False)
        cmd_export(args)
        out = capsys.readouterr().out
        assert "No .ai-rules" in out or "not found" in out.lower()

    def test_export_dry_run(self, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        (rules_dir / "a.yml").write_text(yaml.dump({"anti_patterns": [{"id": "x"}]}))
        args = argparse.Namespace(project_dir=str(tmp_path), output=None, dry_run=True)
        cmd_export(args)
        out = capsys.readouterr().out
        assert "dry-run" in out


# ──────────────────────────────────────────────────────────
# Tests for main CLI
# ──────────────────────────────────────────────────────────


class TestMain:
    def test_no_command(self) -> None:
        with mock.patch("sys.argv", ["rule_marketplace"]):
            assert main() == 0

    def test_list_command(self, capsys: pytest.CaptureFixture[str]) -> None:
        with mock.patch("sys.argv", ["rule_marketplace", "list"]):
            assert main() == 0
        assert "Pack ID" in capsys.readouterr().out

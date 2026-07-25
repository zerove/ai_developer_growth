"""Tests for rule_marketplace.py (0% → target 85%)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.rule_marketplace import (
    cmd_export,
    cmd_info,
    cmd_install,
    cmd_list,
    cmd_search,
    cmd_validate,
    main,
)


class TestCmdList:
    """Tests for cmd_list()."""

    def test_list_text(self) -> None:
        args = argparse.Namespace(json=False)
        cmd_list(args)

    def test_list_json(self) -> None:
        args = argparse.Namespace(json=True)
        cmd_list(args)


class TestCmdSearch:
    """Tests for cmd_search()."""

    def test_search_with_results(self) -> None:
        with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
            mock_search.return_value = [
                {"id": "py-bare-except", "severity": "error", "message": "test", "pattern": "except"}
            ]
            args = argparse.Namespace(query="except", json=False)
            cmd_search(args)

    def test_search_no_results(self) -> None:
        with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
            mock_search.return_value = []
            args = argparse.Namespace(query="nonexistent", json=False)
            cmd_search(args)

    def test_search_json(self) -> None:
        with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
            mock_search.return_value = [{"id": "x"}]
            args = argparse.Namespace(query="x", json=True)
            cmd_search(args)

    def test_search_no_pattern(self) -> None:
        with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
            mock_search.return_value = [{"id": "x", "severity": "error", "message": "msg"}]
            args = argparse.Namespace(query="x", json=False)
            cmd_search(args)


class TestCmdInfo:
    """Tests for cmd_info()."""

    def test_info_valid_pack(self) -> None:
        args = argparse.Namespace(pack="security", json=False)
        with patch("tools.scripts.rule_marketplace.get_pack_info") as mock_info:
            mock_info.return_value = {
                "name": "Security",
                "description": "desc",
                "rule_count": 5,
                "categories": ["security"],
                "source": "common/security.yml",
            }
            with patch("tools.scripts.rule_marketplace._framework_dir") as mock_fd:
                mock_fd.return_value = Path("/tmp")
                cmd_info(args)

    def test_info_unknown_pack(self) -> None:
        with patch("tools.scripts.rule_marketplace.get_pack_info") as mock_info:
            mock_info.return_value = None
            args = argparse.Namespace(pack="nonexistent", json=False)
            cmd_info(args)

    def test_info_json(self) -> None:
        with patch("tools.scripts.rule_marketplace.get_pack_info") as mock_info:
            mock_info.return_value = {"name": "x", "description": "d", "rule_count": 1, "categories": [], "source": "f"}
            args = argparse.Namespace(pack="x", json=True)
            with patch("tools.scripts.rule_marketplace._framework_dir") as mock_fd:
                mock_fd.return_value = Path("/tmp")
                cmd_info(args)

    def test_info_source_is_file(self, tmp_path: Path) -> None:
        src = tmp_path / "security.yml"
        src.write_text("anti_patterns:\n  - id: x\n")
        with patch("tools.scripts.rule_marketplace.get_pack_info") as mock_info:
            mock_info.return_value = {
                "name": "x",
                "description": "d",
                "rule_count": 1,
                "categories": ["anti_patterns"],
                "source": str(src),
            }
            args = argparse.Namespace(pack="x", json=False)
            with patch("tools.scripts.rule_marketplace._framework_dir") as mock_fd:
                mock_fd.return_value = tmp_path
                cmd_info(args)

    def test_info_source_is_dir(self, tmp_path: Path) -> None:
        src = tmp_path / "rules.d"
        src.mkdir()
        (src / "anti.yml").write_text("anti_patterns:\n  - id: x\n")
        with patch("tools.scripts.rule_marketplace.get_pack_info") as mock_info:
            mock_info.return_value = {
                "name": "x",
                "description": "d",
                "rule_count": 1,
                "categories": ["anti_patterns"],
                "source": "rules.d",
            }
            args = argparse.Namespace(pack="x", json=False)
            with patch("tools.scripts.rule_marketplace._framework_dir") as mock_fd:
                mock_fd.return_value = tmp_path
                cmd_info(args)


class TestCmdInstall:
    """Tests for cmd_install()."""

    def test_install_success(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_marketplace.install_pack") as mock_install:
            mock_install.return_value = ["file1.yml"]
            args = argparse.Namespace(pack="security", project_dir=str(tmp_path), dry_run=False)
            cmd_install(args)

    def test_install_dry_run(self, tmp_path: Path) -> None:
        args = argparse.Namespace(pack="security", project_dir=str(tmp_path), dry_run=True)
        cmd_install(args)

    def test_install_value_error(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_marketplace.install_pack") as mock_install:
            mock_install.side_effect = ValueError("bad pack")
            args = argparse.Namespace(pack="bad", project_dir=str(tmp_path), dry_run=False)
            cmd_install(args)

    def test_install_no_files(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_marketplace.install_pack") as mock_install:
            mock_install.return_value = []
            args = argparse.Namespace(pack="empty", project_dir=str(tmp_path), dry_run=False)
            cmd_install(args)


class TestCmdValidate:
    """Tests for cmd_validate()."""

    def test_validate_no_rules_dir(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_marketplace.validate_rules") as mock_val:
            mock_val.return_value = (0, 0, [])
            args = argparse.Namespace(project_dir=str(tmp_path))
            cmd_validate(args)

    def test_validate_with_errors(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        with patch("tools.scripts.rule_marketplace.validate_rules") as mock_val:
            mock_val.return_value = (5, 2, ["err1", "err2"])
            args = argparse.Namespace(project_dir=str(tmp_path))
            cmd_validate(args)

    def test_validate_all_valid(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        with patch("tools.scripts.rule_marketplace.validate_rules") as mock_val:
            mock_val.return_value = (10, 0, [])
            args = argparse.Namespace(project_dir=str(tmp_path))
            cmd_validate(args)

    def test_validate_zero_rules(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        with patch("tools.scripts.rule_marketplace.validate_rules") as mock_val:
            mock_val.return_value = (0, 0, [])
            args = argparse.Namespace(project_dir=str(tmp_path))
            cmd_validate(args)


class TestCmdExport:
    """Tests for cmd_export()."""

    def test_export_no_rules_dir(self, tmp_path: Path) -> None:
        args = argparse.Namespace(project_dir=str(tmp_path), output=None, dry_run=False)
        cmd_export(args)

    def test_export_dry_run(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        with patch("tools.scripts.rule_marketplace.export_rules") as mock_exp:
            mock_exp.return_value = (5, {})
            args = argparse.Namespace(project_dir=str(tmp_path), output=str(tmp_path / "out.yml"), dry_run=True)
            cmd_export(args)

    def test_export_success(self, tmp_path: Path) -> None:
        rules_dir = tmp_path / ".ai-rules"
        rules_dir.mkdir()
        with patch("tools.scripts.rule_marketplace.export_rules") as mock_exp:
            mock_exp.return_value = (3, {"anti_patterns": []})
            args = argparse.Namespace(project_dir=str(tmp_path), output=str(tmp_path / "out.yml"), dry_run=False)
            cmd_export(args)


class TestMain:
    """Tests for main() CLI."""

    def test_no_command(self) -> None:
        with patch("sys.argv", ["prog"]):
            ret = main()
            assert ret == 0

    def test_list_command(self) -> None:
        with patch("sys.argv", ["prog", "list"]):
            ret = main()
            assert ret == 0

    def test_search_command(self) -> None:
        with patch("sys.argv", ["prog", "search", "sql"]):
            with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
                mock_search.return_value = []
                ret = main()
                assert ret == 0

    def test_unknown_command(self) -> None:
        with patch("sys.argv", ["prog", "unknown"]):
            with pytest.raises(SystemExit):
                main()

    def test_exception_handling(self) -> None:
        with patch("sys.argv", ["prog", "search", "test"]):
            with patch("tools.scripts.rule_marketplace.search_rules") as mock_search:
                mock_search.side_effect = RuntimeError("boom")
                with pytest.raises(SystemExit) as exc_info:
                    main()
                assert exc_info.value.code == 1

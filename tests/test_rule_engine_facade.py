"""Tests for rule_engine.py — RuleEngine facade."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from tools.scripts.rule_engine import RuleEngine, asdict


class TestAsdict:
    """Tests for asdict helper."""

    def test_with_dataclass(self) -> None:
        from dataclasses import dataclass

        @dataclass
        class Point:
            x: int
            y: int

        assert asdict(Point(1, 2)) == {"x": 1, "y": 2}

    def test_with_dict(self) -> None:
        assert asdict({"a": 1}) == {"a": 1}

    def test_with_other(self) -> None:
        result = asdict("hello")
        assert result == {"value": "hello"}


class TestRuleEngineInit:
    """Tests for RuleEngine initialization."""

    def test_rules_dir_property(self) -> None:
        engine = RuleEngine()
        with patch(
            "tools.scripts.rule_engine.RuleEngine.rules_dir", new_callable=lambda: property(lambda self: Path("/tmp"))
        ):
            d = engine.rules_dir
            assert isinstance(d, Path)


class TestValidateFile:
    """Tests for validate_file."""

    def test_validate_file(self, tmp_path: Path) -> None:
        f = tmp_path / "test.py"
        f.write_text("pass\n")
        engine = RuleEngine()
        with patch("tools.scripts.rules_engine.validators.pipeline.validate_file") as mock_vf:
            mock_result = MagicMock()
            mock_result.issues = []
            mock_result.health_score = 100
            mock_vf.return_value = mock_result
            result = engine.validate_file(f, "python")
            assert result["language"] == "python"
            assert result["file"] == str(f)


class TestValidateDirectory:
    """Tests for validate_directory."""

    def test_validate_directory(self, tmp_path: Path) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rules_engine.validators.pipeline.validate_directory") as mock_vd:
            mock_result = MagicMock()
            mock_result.file = str(tmp_path / "a.py")
            mock_result.language = "python"
            mock_result.issues = []
            mock_vd.return_value = [mock_result]
            result = engine.validate_directory(tmp_path, "python")
            assert result["summary"]["total_files"] == 1


class TestSearchPacks:
    """Tests for search_packs."""

    def test_search(self) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_catalog.search_rules") as mock_search:
            mock_search.return_value = [{"id": "security"}]
            result = engine.search_packs("security")
            assert len(result) == 1


class TestGetPackInfo:
    """Tests for get_pack_info."""

    def test_get_info(self) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_catalog.get_pack_info") as mock_info:
            mock_info.return_value = {"name": "Security"}
            result = engine.get_pack_info("security")
            assert result["name"] == "Security"


class TestInstallPack:
    """Tests for install_pack."""

    def test_install(self, tmp_path: Path) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_catalog.install_pack") as mock_install:
            mock_install.return_value = [tmp_path / "rules.yml"]
            result = engine.install_pack("security", tmp_path)
            assert len(result) == 1


class TestListPacks:
    """Tests for list_packs."""

    def test_list(self) -> None:
        engine = RuleEngine()
        packs = engine.list_packs()
        assert len(packs) > 0
        assert "id" in packs[0]


class TestTracking:
    """Tests for record_results and get_tracking_report."""

    def test_record_results(self) -> None:
        engine = RuleEngine()
        with (
            patch("tools.scripts.rule_tracker._records_file") as mock_f,
            patch("tools.scripts.rule_tracker._count_by_severity") as mock_sev,
            patch("tools.scripts.rule_tracker._count_by_rule") as mock_rule,
        ):
            mock_f.return_value = Path("/tmp/test.jsonl")
            mock_sev.return_value = {"error": 1}
            mock_rule.return_value = {"py-x": 1}
            results = {"results": [{"issues": [{"severity": "error", "rule_id": "py-x"}]}], "health_score": 80}
            engine.record_results(results, project="test")

    def test_get_tracking_report_empty(self) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = []
            result = engine.get_tracking_report()
            assert result["records"] == 0

    def test_get_tracking_report_with_data(self) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = [{"summary": {"total_issues": 5, "by_rule": {"py-x": 3, "py-y": 2}}}]
            result = engine.get_tracking_report(days=7)
            assert result["total_issues"] == 5
            assert result["by_rule"]["py-x"] == 3


class TestGetAllRules:
    """Tests for get_all_rules."""

    def test_get_all(self) -> None:
        engine = RuleEngine()
        with patch("tools.scripts.rule_visualize.get_all_rules") as mock:
            mock.return_value = {"python": {"total": 10}}
            result = engine.get_all_rules()
            assert "python" in result

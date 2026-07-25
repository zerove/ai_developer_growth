"""Tests for rule_tracker.py (0% → target 85%)."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

from tools.scripts.rule_tracker import (
    _count_by_rule,
    _count_by_severity,
    _load_records,
    cmd_export,
    cmd_prune,
    cmd_record,
    cmd_report,
    main,
)


class TestCountHelpers:
    """Tests for _count_by_severity and _count_by_rule."""

    def test_count_by_severity_empty(self) -> None:
        assert _count_by_severity([]) == {}

    def test_count_by_severity(self) -> None:
        results = [
            {"issues": [{"severity": "error"}, {"severity": "warning"}]},
            {"issues": [{"severity": "error"}]},
        ]
        counts = _count_by_severity(results)
        assert counts["error"] == 2
        assert counts["warning"] == 1

    def test_count_by_severity_missing_field(self) -> None:
        results = [{"issues": [{"rule_id": "x"}]}]
        counts = _count_by_severity(results)
        assert counts.get("unknown", 0) == 1

    def test_count_by_rule_empty(self) -> None:
        assert _count_by_rule([]) == {}

    def test_count_by_rule(self) -> None:
        results = [
            {"issues": [{"rule_id": "py-bare-except"}, {"rule_id": "py-bare-except"}]},
            {"issues": [{"rule_id": "py-eval"}]},
        ]
        counts = _count_by_rule(results)
        assert counts["py-bare-except"] == 2
        assert counts["py-eval"] == 1

    def test_count_by_rule_missing_field(self) -> None:
        results = [{"issues": [{"severity": "error"}]}]
        counts = _count_by_rule(results)
        assert counts.get("unknown", 0) == 1


class TestLoadRecords:
    """Tests for _load_records()."""

    def test_no_records_file(self, tmp_path: Path) -> None:
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = tmp_path / "nope.jsonl"
            assert _load_records() == []

    def test_load_records(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        record = {"timestamp": "2026-01-01T00:00:00+00:00", "summary": {"total_issues": 5}}
        records_file.write_text(json.dumps(record) + "\n")
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            records = _load_records()
            assert len(records) == 1

    def test_load_records_with_days_filter(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        old = datetime.now(timezone.utc) - timedelta(days=60)
        new = datetime.now(timezone.utc)
        records_file.write_text(
            json.dumps({"timestamp": old.isoformat(), "summary": {"total_issues": 1}})
            + "\n"
            + json.dumps({"timestamp": new.isoformat(), "summary": {"total_issues": 2}})
            + "\n"
        )
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            records = _load_records(days=30)
            assert len(records) == 1

    def test_load_records_malformed_line(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        records_file.write_text("not json\n")
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            assert _load_records() == []

    def test_load_records_missing_timestamp_still_loads(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        records_file.write_text(json.dumps({"no_timestamp": True}) + "\n")
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            records = _load_records()
            assert len(records) == 1  # loaded but no timestamp filtering


class TestCmdRecord:
    """Tests for cmd_record()."""

    def test_record_from_file(self, tmp_path: Path) -> None:
        data_file = tmp_path / "results.json"
        data_file.write_text(
            json.dumps({"results": [{"issues": [{"severity": "error", "rule_id": "x"}]}], "health_score": 80})
        )
        args = argparse.Namespace(file=str(data_file), project="test-project")
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = tmp_path / "records.jsonl"
            cmd_record(args)
            assert (tmp_path / "records.jsonl").exists()


class TestCmdReport:
    """Tests for cmd_report()."""

    def test_no_records(self) -> None:
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = []
            args = argparse.Namespace(days=None, json=False)
            cmd_report(args)

    def test_report_with_records(self, tmp_path: Path) -> None:
        records = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "project": "test",
                "summary": {
                    "total_issues": 10,
                    "by_rule": {"py-bare-except": 5, "py-eval": 3},
                    "by_severity": {"error": 7, "warning": 3},
                },
            }
        ]
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = records
            args = argparse.Namespace(days=None, json=False)
            cmd_report(args)

    def test_report_json_output(self) -> None:
        records = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "project": "test",
                "summary": {
                    "total_issues": 5,
                    "by_rule": {"py-x": 5},
                    "by_severity": {"error": 5},
                },
            }
        ]
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = records
            args = argparse.Namespace(days=30, json=True)
            cmd_report(args)

    def test_report_with_days(self) -> None:
        records = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "project": "test",
                "summary": {"total_issues": 1, "by_rule": {}, "by_severity": {}},
            }
        ]
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = records
            args = argparse.Namespace(days=7, json=False)
            cmd_report(args)


class TestCmdExport:
    """Tests for cmd_export()."""

    def test_export_no_records(self) -> None:
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = []
            args = argparse.Namespace(days=None)
            cmd_export(args)

    def test_export_with_records(self) -> None:
        records = [
            {
                "timestamp": "2026-01-01T00:00:00+00:00",
                "project": "test",
                "summary": {"total_files": 1, "total_issues": 3},
                "health_score": 80,
            }
        ]
        with patch("tools.scripts.rule_tracker._load_records") as mock_load:
            mock_load.return_value = records
            args = argparse.Namespace(days=None)
            cmd_export(args)


class TestCmdPrune:
    """Tests for cmd_prune()."""

    def test_prune_no_pruning_needed(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        records_file.write_text('{"x":1}\n')
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            with patch("tools.scripts.rule_tracker._load_records") as mock_load:
                mock_load.return_value = [{"x": 1}]
                args = argparse.Namespace(keep=100)
                cmd_prune(args)

    def test_prune_removes_old(self, tmp_path: Path) -> None:
        records_file = tmp_path / "records.jsonl"
        with patch("tools.scripts.rule_tracker._records_file") as mock_f:
            mock_f.return_value = records_file
            records = [{"i": i} for i in range(10)]
            with patch("tools.scripts.rule_tracker._load_records") as mock_load:
                mock_load.return_value = records
                args = argparse.Namespace(keep=3)
                cmd_prune(args)


class TestMain:
    """Tests for main() CLI."""

    def test_no_command(self) -> None:
        with patch("sys.argv", ["prog"]):
            ret = main()
            assert ret == 0

    def test_report_command(self) -> None:
        with patch("sys.argv", ["prog", "report"]):
            with patch("tools.scripts.rule_tracker._load_records") as mock_load:
                mock_load.return_value = []
                ret = main()
                assert ret == 0

    def test_export_command(self) -> None:
        with patch("sys.argv", ["prog", "export"]):
            with patch("tools.scripts.rule_tracker._load_records") as mock_load:
                mock_load.return_value = []
                ret = main()
                assert ret == 0

    def test_prune_command(self) -> None:
        with patch("sys.argv", ["prog", "prune", "--keep", "5"]):
            with patch("tools.scripts.rule_tracker._load_records") as mock_load:
                mock_load.return_value = []
                ret = main()
                assert ret == 0

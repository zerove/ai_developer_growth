"""Tests for rule_tracker.py - rule effectiveness tracking."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

# Use argparse.Namespace for creating test args
import argparse  # noqa: E402

from rule_tracker import (
    _count_by_rule,
    _count_by_severity,
    _load_records,
    cmd_export,
    cmd_prune,
    cmd_record,
    cmd_report,
    main,
)

# ──────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────


@pytest.fixture
def tracking_dir(tmp_path: Path) -> Path:
    """Create a temp data directory and patch _data_dir."""
    d = tmp_path / ".ai-rules-tracking"
    d.mkdir()
    with mock.patch("rule_tracker._data_dir", return_value=d):
        yield d


@pytest.fixture
def sample_results() -> dict:
    """Sample validation results."""
    return {
        "results": [
            {
                "file": "test.py",
                "issues": [
                    {
                        "rule_id": "py-eval",
                        "severity": "error",
                        "message": "Use ast.literal_eval",
                    },
                    {
                        "rule_id": "py-print",
                        "severity": "warning",
                        "message": "Use logging",
                    },
                    {
                        "rule_id": "py-eval",
                        "severity": "error",
                        "message": "Use ast.literal_eval",
                    },
                ],
            },
            {
                "file": "test.ts",
                "issues": [
                    {
                        "rule_id": "ts-any",
                        "severity": "warning",
                        "message": "Avoid any",
                    },
                ],
            },
        ],
        "health_score": 85,
    }


# ──────────────────────────────────────────────────────────
# Unit tests for helper functions
# ──────────────────────────────────────────────────────────


class TestCountBySeverity:
    def test_empty(self) -> None:
        assert _count_by_severity([]) == {}

    def test_counts(self) -> None:
        results = [
            {
                "issues": [
                    {"severity": "error"},
                    {"severity": "warning"},
                    {"severity": "error"},
                ]
            },
            {"issues": [{"severity": "info"}]},
        ]
        assert _count_by_severity(results) == {"error": 2, "warning": 1, "info": 1}

    def test_missing_severity(self) -> None:
        results = [{"issues": [{}]}]
        assert _count_by_severity(results) == {"unknown": 1}

    def test_no_issues(self) -> None:
        results = [{"file": "a.py"}]
        assert _count_by_severity(results) == {}


class TestCountByRule:
    def test_empty(self) -> None:
        assert _count_by_rule([]) == {}

    def test_counts(self) -> None:
        results = [
            {
                "issues": [
                    {"rule_id": "py-eval"},
                    {"rule_id": "py-eval"},
                    {"rule_id": "ts-any"},
                ]
            },
        ]
        assert _count_by_rule(results) == {"py-eval": 2, "ts-any": 1}

    def test_missing_rule_id(self) -> None:
        results = [{"issues": [{"message": "bad"}]}]
        assert _count_by_rule(results) == {"unknown": 1}


# ──────────────────────────────────────────────────────────
# Tests for _load_records
# ──────────────────────────────────────────────────────────


class TestLoadRecords:
    def test_no_file(self, tmp_path: Path) -> None:
        with mock.patch(
            "rule_tracker._records_file", return_value=tmp_path / "nonexistent.jsonl"
        ):
            assert _load_records() == []

    def test_load_all(self, tracking_dir: Path) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(
            json.dumps(
                {
                    "timestamp": "2026-07-23T00:00:00+00:00",
                    "summary": {"total_issues": 5},
                }
            )
            + "\n"
            + json.dumps(
                {
                    "timestamp": "2026-07-22T00:00:00+00:00",
                    "summary": {"total_issues": 3},
                }
            )
            + "\n"
        )
        records = _load_records()
        assert len(records) == 2

    def test_load_with_days_filter(self, tracking_dir: Path) -> None:
        now = datetime.now(timezone.utc)
        recent = now.isoformat()
        old = "2020-01-01T00:00:00+00:00"
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(
            json.dumps({"timestamp": recent, "summary": {"total_issues": 5}})
            + "\n"
            + json.dumps({"timestamp": old, "summary": {"total_issues": 3}})
            + "\n"
        )
        records = _load_records(days=7)
        assert len(records) == 1
        assert records[0]["summary"]["total_issues"] == 5

    def test_skips_invalid_json(self, tracking_dir: Path) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(
            "not json\n"
            + json.dumps({"timestamp": "2026-07-23T00:00:00+00:00", "summary": {}})
            + "\n"
        )
        records = _load_records()
        assert len(records) == 1

    def test_skips_missing_timestamp_with_days(self, tracking_dir: Path) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(json.dumps({"summary": {}}) + "\n")
        # With days filter, KeyError on timestamp causes skip
        records = _load_records(days=30)
        assert len(records) == 0

    def test_loads_missing_timestamp_without_days(self, tracking_dir: Path) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(json.dumps({"summary": {}}) + "\n")
        # Without days filter, record is loaded even without timestamp
        records = _load_records()
        assert len(records) == 1

    def test_empty_lines(self, tracking_dir: Path) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text("\n\n\n")
        assert _load_records() == []


# ──────────────────────────────────────────────────────────
# Tests for cmd_record
# ──────────────────────────────────────────────────────────


class TestCmdRecord:
    def test_record_from_file(self, tracking_dir: Path, sample_results: dict) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))

        args = argparse.Namespace(file=str(results_file), project="test-project")
        cmd_record(args)

        records = _load_records()
        assert len(records) == 1
        rec = records[0]
        assert rec["project"] == "test-project"
        assert rec["summary"]["total_files"] == 2
        assert rec["summary"]["total_issues"] == 4
        assert rec["health_score"] == 85

    def test_record_no_project(self, tracking_dir: Path, sample_results: dict) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))

        args = argparse.Namespace(file=str(results_file), project=None)
        cmd_record(args)

        records = _load_records()
        assert records[0]["project"] == "unknown"

    def test_record_empty_results(self, tracking_dir: Path) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps({}))

        args = argparse.Namespace(file=str(results_file), project="empty")
        cmd_record(args)

        records = _load_records()
        assert records[0]["summary"]["total_files"] == 0
        assert records[0]["summary"]["total_issues"] == 0


# ──────────────────────────────────────────────────────────
# Tests for cmd_report
# ──────────────────────────────────────────────────────────


class TestCmdReport:
    def test_report_no_records(
        self, tracking_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = argparse.Namespace(days=None, json=False)
        cmd_report(args)
        assert "No records found" in capsys.readouterr().out

    def test_report_json(
        self,
        tracking_dir: Path,
        sample_results: dict,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Record first
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))
        cmd_record(argparse.Namespace(file=str(results_file), project="test"))
        capsys.readouterr()  # clear capsys from cmd_record output

        args = argparse.Namespace(days=None, json=True)
        cmd_report(args)
        output = json.loads(capsys.readouterr().out)
        assert output["total_issues"] == 4
        assert "py-eval" in output["by_rule"]

    def test_report_text(
        self,
        tracking_dir: Path,
        sample_results: dict,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))
        cmd_record(argparse.Namespace(file=str(results_file), project="test"))

        args = argparse.Namespace(days=None, json=False)
        cmd_report(args)
        output = capsys.readouterr().out
        assert "Rule Effectiveness Report" in output
        assert "py-eval" in output


# ──────────────────────────────────────────────────────────
# Tests for cmd_export
# ──────────────────────────────────────────────────────────


class TestCmdExport:
    def test_export_no_records(
        self, tracking_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = argparse.Namespace(days=None)
        cmd_export(args)
        assert "No records found" in capsys.readouterr().out

    def test_export_csv(
        self,
        tracking_dir: Path,
        sample_results: dict,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))
        cmd_record(argparse.Namespace(file=str(results_file), project="test"))

        args = argparse.Namespace(days=None)
        cmd_export(args)
        output = capsys.readouterr().out
        assert "timestamp,project" in output
        assert "test" in output


# ──────────────────────────────────────────────────────────
# Tests for cmd_prune
# ──────────────────────────────────────────────────────────


class TestCmdPrune:
    def test_prune_nothing(
        self, tracking_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        records_file = tracking_dir / "records.jsonl"
        records_file.write_text(
            json.dumps({"timestamp": "2026-07-23T00:00:00+00:00", "summary": {}}) + "\n"
        )

        args = argparse.Namespace(keep=100)
        cmd_prune(args)
        assert "nothing to prune" in capsys.readouterr().out

    def test_prune_records(
        self, tracking_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        records_file = tracking_dir / "records.jsonl"
        lines = [
            json.dumps(
                {"timestamp": f"2026-07-{i:02d}T00:00:00+00:00", "summary": {"i": i}}
            )
            for i in range(1, 11)
        ]
        records_file.write_text("\n".join(lines) + "\n")

        args = argparse.Namespace(keep=3)
        cmd_prune(args)
        assert "Pruned to 3" in capsys.readouterr().out

        records = _load_records()
        assert len(records) == 3


# ──────────────────────────────────────────────────────────
# Tests for main CLI
# ──────────────────────────────────────────────────────────


class TestMain:
    def test_no_command(self) -> None:
        with mock.patch("sys.argv", ["rule_tracker"]):
            assert main() == 0

    def test_record_command(self, tracking_dir: Path, sample_results: dict) -> None:
        results_file = tracking_dir / "results.json"
        results_file.write_text(json.dumps(sample_results))
        with mock.patch(
            "sys.argv",
            [
                "rule_tracker",
                "record",
                "--file",
                str(results_file),
                "--project",
                "cli-test",
            ],
        ):
            assert main() == 0
            records = _load_records()
            assert len(records) == 1

"""Tests for Phase 3 modules: hallucination detector and quality trends."""

from __future__ import annotations

from pathlib import Path

import pytest


class TestHallucinationDetector:
    """Test hallucination pattern detection."""

    def test_import(self):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations, HallucinationReport

        assert detect_hallucinations is not None

    def test_empty_file(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text("")
        report = detect_hallucinations_in_file(f)
        assert report.total_findings == 0
        assert report.files_scanned == 1

    def test_detects_eval(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text('result = eval(user_input)\n')
        report = detect_hallucinations_in_file(f)
        assert report.total_findings > 0
        assert any(f.pattern_id == "unsafe-eval" for f in report.findings)

    def test_detects_os_listdir_recursive(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text('files = os.listdir(path, recursive=True)\n')
        report = detect_hallucinations_in_file(f)
        assert any(f.pattern_id == "hallucinated-api-os-listdir-recursive" for f in report.findings)

    def test_detects_yaml_unsafe_load(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text('data = yaml.load(content)\n')
        report = detect_hallucinations_in_file(f)
        assert any(f.pattern_id == "unsafe-yaml-load" for f in report.findings)

    def test_skips_comments(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text("# result = eval(user_input)\n")
        report = detect_hallucinations_in_file(f)
        assert report.total_findings == 0

    def test_skips_strings(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text('msg = "use eval() carefully"\n')
        report = detect_hallucinations_in_file(f)
        # eval inside string should be skipped
        assert not any(f.pattern_id == "unsafe-eval" for f in report.findings)

    def test_detects_redundant_bool_compare(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text("if x == True:\n    pass\n")
        report = detect_hallucinations_in_file(f)
        assert any(f.pattern_id == "logic-redundant-bool-compare" for f in report.findings)

    def test_detects_silenced_error(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        f = tmp_path / "test.py"
        f.write_text("except ValueError: pass\n")
        report = detect_hallucinations_in_file(f)
        assert any(f.pattern_id == "logic-silenced-error" for f in report.findings)

    def test_directory_scan(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations

        (tmp_path / "a.py").write_text("eval('bad')\n")
        (tmp_path / "b.py").write_text("exec('bad')\n")
        report = detect_hallucinations(tmp_path)
        assert report.files_scanned >= 2
        assert report.total_findings >= 2

    def test_format_report(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import (
            detect_hallucinations_in_file,
            format_hallucination_report,
        )

        f = tmp_path / "test.py"
        f.write_text("eval('test')\n")
        report = detect_hallucinations_in_file(f)
        text = format_hallucination_report(report)
        assert "Hallucination" in text
        assert "unsafe-eval" in text

    def test_format_clean_report(self):
        from tools.scripts.rules_engine.hallucination_detector import (
            HallucinationReport,
            format_hallucination_report,
        )

        report = HallucinationReport(files_scanned=0, findings=[])
        text = format_hallucination_report(report)
        assert "No hallucination patterns" in text

    def test_nonexistent_file(self, tmp_path):
        from tools.scripts.rules_engine.hallucination_detector import detect_hallucinations_in_file

        report = detect_hallucinations_in_file(tmp_path / "nonexistent.py")
        assert report.files_scanned == 0
        assert report.total_findings == 0


class TestQualityTrends:
    """Test quality trend tracking."""

    def test_import(self):
        from tools.scripts.rules_engine.quality_trends import QualityTracker, QualitySnapshot

        assert QualityTracker is not None

    def test_take_snapshot(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        (tmp_path / "a.py").write_text('def foo():\n    """Doc."""\n    return 1\n')
        snapshot = tracker.take_snapshot(tmp_path)
        assert snapshot.total_files >= 1
        assert snapshot.timestamp > 0

    def test_persistence(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        data_dir = tmp_path / "quality"
        tracker1 = QualityTracker(data_dir=data_dir)
        (tmp_path / "a.py").write_text("x = 1\n")
        tracker1.take_snapshot(tmp_path)

        # Reload from disk
        tracker2 = QualityTracker(data_dir=data_dir)
        assert len(tracker2.snapshots) == 1

    def test_trend_report(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        (tmp_path / "a.py").write_text("x = 1\n")
        tracker.take_snapshot(tmp_path)
        tracker.take_snapshot(tmp_path)

        report = tracker.generate_trend_report()
        assert report.snapshot_count == 2
        assert report.latest is not None

    def test_format_report(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        (tmp_path / "a.py").write_text("x = 1\n")
        tracker.take_snapshot(tmp_path)
        tracker.take_snapshot(tmp_path)

        report = tracker.generate_trend_report()
        text = tracker.format_trend_report(report)
        assert "Quality Trend" in text

    def test_format_report_no_snapshots(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        report = tracker.generate_trend_report()
        text = tracker.format_trend_report(report)
        assert "at least 2 snapshots" in text

    def test_clear(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        (tmp_path / "a.py").write_text("x = 1\n")
        tracker.take_snapshot(tmp_path)
        assert len(tracker.snapshots) == 1
        tracker.clear()
        assert len(tracker.snapshots) == 0

    def test_snapshot_to_dict(self, tmp_path):
        from tools.scripts.rules_engine.quality_trends import QualityTracker

        tracker = QualityTracker(data_dir=tmp_path / "quality")
        (tmp_path / "a.py").write_text("x = 1\n")
        snapshot = tracker.take_snapshot(tmp_path)
        d = snapshot.to_dict()
        assert "timestamp" in d
        assert "total_files" in d


class TestHooksRunnerHallucination:
    """Test hallucination-scan command in hooks_runner."""

    def test_build_parser(self):
        from tools.scripts.hooks_runner import _build_parser

        parser = _build_parser()
        args = parser.parse_args(["hallucination-scan", "--path", "/tmp"])
        assert args.command == "hallucination-scan"

    def test_dispatch(self):
        from tools.scripts.hooks_runner import _build_parser, _dispatch

        parser = _build_parser()
        args = parser.parse_args(["hallucination-scan", "--path", "/nonexistent"])
        result = _dispatch(args)
        assert result == 0  # No files = no high findings

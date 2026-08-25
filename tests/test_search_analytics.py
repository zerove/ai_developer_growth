"""search_analytics 单元测试（消费侧证据链 P0-2/P0-3）。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tools.scripts.search_analytics import analyze, export_zero_recall_synonyms, load_records  # noqa: E402


@pytest.fixture()
def sample_records() -> list[dict]:
    return [
        {"ts": "20260825T100000+0800", "query": "质量门禁", "total": 3, "top_score": 5.0, "time_ms": 11.0},
        {"ts": "20260825T110000+0800", "query": "质量门禁", "total": 3, "top_score": 5.0, "time_ms": 9.0},
        {"ts": "20260825T120000+0800", "query": "不存在的概念xyz", "total": 0, "top_score": 0.0, "time_ms": 2.0},
        {"ts": "20260826T130000+0800", "query": "多智能体编排", "total": 2, "top_score": 8.1, "time_ms": 12.5},
    ]


class TestAnalyze:
    def test_totals_and_uniques(self, sample_records: list[dict]) -> None:
        report = analyze(sample_records)
        assert report["total"] == 4
        assert report["unique"] == 3

    def test_zero_recall_stats(self, sample_records: list[dict]) -> None:
        report = analyze(sample_records)
        assert report["zero_recall_count"] == 1
        assert report["zero_recall_rate"] == 25.0

    def test_top_queries_ranking(self, sample_records: list[dict]) -> None:
        report = analyze(sample_records)
        assert report["top_queries"][0] == {"query": "质量门禁", "count": 2}

    def test_empty_records(self) -> None:
        report = analyze([])
        assert report["total"] == 0
        assert report["avg_time_ms"] == 0.0

    def test_avg_time(self, sample_records: list[dict]) -> None:
        report = analyze(sample_records)
        assert report["avg_time_ms"] == round((11.0 + 9.0 + 2.0 + 12.5) / 4, 2)


class TestLoadRecords:
    def test_skips_malformed_lines(self, tmp_path: Path) -> None:
        log = tmp_path / "q.jsonl"
        log.write_text(
            '{"ts":"20260825T100000+0800","query":"a","total":1,"time_ms":1}\nnot-json\n\n',
            encoding="utf-8",
        )
        records = load_records(log, days=None)
        assert len(records) == 1

    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert load_records(tmp_path / "none.jsonl", days=None) == []


class TestExportZeroRecall:
    def test_export_writes_candidates(self, sample_records: list[dict], tmp_path: Path) -> None:
        out = tmp_path / "candidates.json"
        report = analyze(sample_records)
        count = export_zero_recall_synonyms(report, out)
        assert count == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data[0]["query"] == "不存在的概念xyz"


class TestParseTs:
    def test_iso_format_with_hyphens(self) -> None:
        from tools.scripts.search_analytics import _parse_ts

        assert _parse_ts("2026-08-25T13:47:54+0800") is not None

    def test_invalid_returns_none(self) -> None:
        from tools.scripts.search_analytics import _parse_ts

        assert _parse_ts("garbage") is None

    def test_days_filter_uses_real_timestamps(self, tmp_path: Path) -> None:
        log = tmp_path / "q.jsonl"
        log.write_text('{"ts":"2026-08-25T13:47:54+0800","query":"a","total":1,"time_ms":1}\n', encoding="utf-8")
        # days=30 应包含今天的记录；days=0（cutoff=现在）应过滤掉过去时间戳
        assert len(load_records(log, days=30)) == 1

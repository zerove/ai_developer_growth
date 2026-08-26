"""search_analytics 第二轮: 缺口分支与 main 全路径。57%→90%+

补 load_records 天数过滤(无效时间戳保留)/render/zero_only/export_zero/main。
"""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tools.scripts.search_analytics import (
    _parse_ts,
    analyze,
    export_zero_recall_synonyms,
    load_records,
    main,
    render,
)


def write_log(tmp_path: Path, lines: list[dict[str, object]]) -> Path:
    log = tmp_path / "queries.jsonl"
    log.write_text("\n".join(json.dumps(line, ensure_ascii=False) for line in lines) + "\n", encoding="utf-8")
    return log


class TestParseTs:
    def test_compact_format(self) -> None:
        ts = _parse_ts("20260826T120000+0000")
        assert ts is not None and isinstance(ts, float)

    def test_naive_iso(self) -> None:
        assert _parse_ts("2026-08-26T12:00:00") is not None


class TestLoadRecords:
    def test_days_filter_keeps_invalid_ts_records(self, tmp_path: Path) -> None:
        # 无效时间戳的记录不过滤(保守保留), 过旧的有效记录剔除
        old = datetime.now(timezone.utc).timestamp() - 100 * 86400
        old_str = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(old))
        log = write_log(
            tmp_path,
            [
                {"query": "ancient", "ts": old_str},
                {"query": "fresh", "ts": ""},
            ],
        )
        records = load_records(log, days=7)
        assert [str(r["query"]) for r in records] == ["fresh"]

    def test_no_filter_keeps_all(self, tmp_path: Path) -> None:
        log = write_log(tmp_path, [{"query": "a"}, {"query": "b"}])
        assert len(load_records(log, days=None)) == 2


class TestAnalyzeEdge:
    def test_non_numeric_time_ignored(self) -> None:
        report = analyze([{"query": "x", "time_ms": "fast"}])
        assert report["avg_time_ms"] == 0.0

    def test_top_n_limiting(self) -> None:
        records = [{"query": f"q{i}"} for i in range(20)]
        report = analyze(records, top_n=5)
        assert len(report["top_queries"]) == 5  # type: ignore[arg-type]


class TestRender:
    def test_full_render_with_sections(self) -> None:
        report = {
            "total": 10,
            "unique": 8,
            "avg_time_ms": 3.2,
            "zero_recall_count": 2,
            "zero_recall_rate": 20.0,
            "top_queries": [{"query": "api", "count": 4}],
            "zero_queries": [{"query": "ghost", "count": 2}],
        }
        text = render(report, days=7)
        assert "最近 7 天" in text
        assert "TOP 查询" in text and "api" in text
        assert "零召回查询" in text and "ghost" in text

    def test_render_all_range_and_empty_sections(self) -> None:
        text = render(analyze([]), days=None)
        assert "全部" in text and "零召回: 0 次 (0.0%)" in text


class TestExportAndMain:
    def test_export_creates_parent_dirs(self, tmp_path: Path) -> None:
        out = tmp_path / "deep" / "synonyms.json"
        report = {"zero_queries": [{"query": "q", "count": 1}]}
        assert export_zero_recall_synonyms(report, out) == 1
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data[0]["suggested_action"].startswith("加入")

    def test_main_zero_only_quiet(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = write_log(tmp_path, [{"query": "hit", "total": 3}])
        monkeypatch.setattr("sys.argv", ["search_analytics.py", "--log", str(log), "--zero-only"])
        code = main()
        out = capsys.readouterr().out
        assert code == 0 and "无零召回记录" in out

    def test_main_with_export(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = write_log(tmp_path, [{"query": "void query", "total": 0}])
        export = tmp_path / "zero.json"
        monkeypatch.setattr(
            "sys.argv",
            ["search_analytics.py", "--log", str(log), "--export-zero", str(export)],
        )
        code = main()
        out = capsys.readouterr().out
        assert code == 0 and "已导出 1 条" in out and export.exists()

    def test_main_days_option(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        log = write_log(tmp_path, [{"query": "recent", "total": 1}])
        monkeypatch.setattr("sys.argv", ["search_analytics.py", "--log", str(log), "--days", "7"])
        code = main()
        assert code == 0 and "最近 7 天" in capsys.readouterr().out

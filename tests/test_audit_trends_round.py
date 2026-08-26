"""audit_trends 攻坚: 链校验/统计聚合/异常检测/main 双输出。48%→90%+"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from tools.scripts.audit_attestation import AuditAttestationLedger
from tools.scripts.audit_trends import (
    _load_entries,
    analyze,
    main,
    verify_chain,
)


def make_entry(etype: str = "EXEC", hours_ago: float = 0, prev_hash: str | None = None) -> dict:
    return {
        "event_type": etype,
        "details": {},
        "prev_hash": prev_hash or "0" * 64,
        "timestamp": (datetime.now(timezone.utc) - timedelta(hours=hours_ago)).isoformat(),
        "current_hash": "a" * 64,
    }


class TestVerifyChain:
    def test_valid_genesis_chain(self) -> None:
        entries = [make_entry(prev_hash="0" * 64)]
        ok, desc = verify_chain(entries)
        assert ok and "1 条记录" in desc

    def test_chained_entries(self, tmp_path: Path) -> None:
        # 用真实账本生成两条链式记录
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.record_trace("A", {})
        ledger.record_trace("B", {})
        entries = _load_entries(ledger.ledger_file)
        ok, desc = verify_chain(entries)
        assert ok and "2 条记录" in desc

    def test_broken_chain(self) -> None:
        bad = make_entry(prev_hash="f" * 64)
        ok, desc = verify_chain([bad])
        assert not ok and "链断裂" in desc and "第 1 条" in desc

    def test_empty_chain_ok(self) -> None:
        ok, desc = verify_chain([])
        assert ok


class TestLoadEntries:
    def test_missing_file(self, tmp_path: Path) -> None:
        assert _load_entries(tmp_path / "nope.jsonl") == []

    def test_skips_blank_and_corrupt_lines(self, tmp_path: Path) -> None:
        f = tmp_path / "ledger.jsonl"
        f.write_text('{"a": 1}\n\n{ broken\n{"b": 2}\n', encoding="utf-8")
        assert len(_load_entries(f)) == 2


class TestAnalyze:
    def test_counts_and_daily_aggregation(self) -> None:
        now = datetime.now(timezone.utc)
        entries = [
            {"event_type": "A", "timestamp": now.isoformat()},
            {"event_type": "A", "timestamp": (now - timedelta(days=3)).isoformat()},
            {"event_type": "B", "timestamp": (now - timedelta(days=10)).isoformat()},
        ]
        report = analyze(entries)
        assert report["total"] == 3
        assert report["by_type"] == {"A": 2, "B": 1}
        assert len(report["daily"]) == 3
        assert report["last_24h"] == {"A": 1}

    def test_undated_entries_counted(self) -> None:
        report = analyze([{"event_type": "OLD"}, {"event_type": "X", "timestamp": "bad-date"}])
        assert report["undated_entries"] == 2
        assert report["last_24h"] == {}

    def test_alert_new_type_above_threshold(self) -> None:
        entries = [make_entry("BURST") for _ in range(6)]  # 24h 内 6 次 >= 5 且历史为 0
        report = analyze(entries)
        assert any("新出现的事件类型" in a for a in report["alerts"])

    def test_alert_spike_vs_history(self) -> None:
        # 历史每天 1 次共 30 天, 最近 24h 突发 10 次 → >3x
        entries = [make_entry("SPIKE", hours_ago=24 * (i + 1)) for i in range(30)]
        entries += [make_entry("SPIKE") for _ in range(10)]
        report = analyze(entries)
        assert any("历史日均" in a for a in report["alerts"])

    def test_small_sample_below_min_no_alert(self) -> None:
        entries = [make_entry("QUIET") for _ in range(4)]  # < ALERT_MIN_COUNT
        assert analyze(entries)["alerts"] == []

    def test_no_false_alert_when_normal(self) -> None:
        entries = [make_entry("NORM", hours_ago=24 * (i + 1)) for i in range(20)]
        entries.append(make_entry("NORM"))  # 24h 内仅 1 次 < 下限
        assert analyze(entries)["alerts"] == []


class TestMain:
    def _root_with_ledger(self, tmp_path: Path, tamper: bool = False) -> Path:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.record_trace("EXEC", {"s": 1})
        if tamper:
            lines = ledger.ledger_file.read_text(encoding="utf-8").splitlines()
            entry = json.loads(lines[0])
            entry["details"]["s"] = 999
            ledger.ledger_file.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        return tmp_path

    def test_main_json_output_ok(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = self._root_with_ledger(tmp_path)
        monkeypatch.setattr("sys.argv", ["audit_trends.py", "--json", "--root", str(root)])
        code = main()
        out = json.loads(capsys.readouterr().out)
        assert code == 0 and out["chain_ok"] is True and out["total"] == 1

    def test_main_text_output_no_alerts(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root = self._root_with_ledger(tmp_path)
        monkeypatch.setattr("sys.argv", ["audit_trends.py", "--root", str(root)])
        code = main()
        out = capsys.readouterr().out
        assert code == 0 and "无异常波动" in out and "总条目" in out

    def test_main_exit_1_on_broken_chain(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        root = self._root_with_ledger(tmp_path, tamper=True)
        # 篡改 details 后哈希不再匹配 current_hash? verify_chain 只查 prev 链,
        # 篡改单条不改链字段仍连续。直接构造断链更可靠:
        f = root / ".quality-trends" / "audit_ledger.jsonl"
        entry = make_entry(prev_hash="dead" * 16)
        f.write_text(json.dumps(entry) + "\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["audit_trends.py", "--root", str(root)])
        assert main() == 1

    def test_main_empty_ledger(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["audit_trends.py", "--root", str(tmp_path)])
        code = main()
        assert code == 0 and "无异常波动" in capsys.readouterr().out

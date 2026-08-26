"""cov_tool 单元测试: diff / module / gate / snapshot"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts.cov_tool import (
    _file_to_module,
    _gather_module_table,
    _module_summary,
    _read_coverage_json,
    cmd_diff,
    cmd_gate,
    cmd_module,
    cmd_snapshot,
)


def _make_cov(percs: dict[str, float]) -> dict:
    """Build a minimal coverage JSON dict from {file_path: percent}."""
    return {
        "totals": {"percent_covered": sum(percs.values()) / max(1, len(percs))},
        "files": {
            f: {"summary": {"num_statements": 100, "missing_lines": int(100 * (1 - p / 100)), "percent_covered": p}}
            for f, p in percs.items()
        },
    }


class TestReadCoverage:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        assert _read_coverage_json(tmp_path / "nope.json") == {}

    def test_invalid_json_returns_empty(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.json"
        p.write_text("{not json", encoding="utf-8")
        assert _read_coverage_json(p) == {}

    def test_valid_json_parsed(self, tmp_path: Path) -> None:
        p = tmp_path / "ok.json"
        p.write_text(json.dumps({"a": 1}), encoding="utf-8")
        assert _read_coverage_json(p) == {"a": 1}


class TestFileToModule:
    def test_tools_scripts_path(self) -> None:
        assert _file_to_module("tools/scripts/foo.py") == "tools.scripts.foo"

    def test_nested(self) -> None:
        assert _file_to_module("tools/scripts/adg_cli/check.py") == "tools.scripts.adg_cli.check"


class TestModuleSummary:
    def test_module_present(self) -> None:
        cov = _make_cov({"tools/scripts/foo.py": 85.0})
        s = _module_summary(cov, "tools.scripts.foo")
        assert s["percent"] == 85.0
        assert s["statements"] == 100

    def test_module_absent_returns_empty(self) -> None:
        cov = _make_cov({"tools/scripts/foo.py": 85.0})
        assert _module_summary(cov, "tools.scripts.absent") == {}


class TestGatherTable:
    def test_multiple_files(self) -> None:
        cov = _make_cov({"tools/scripts/a.py": 80.0, "tools/scripts/b.py": 100.0})
        t = _gather_module_table(cov)
        assert t["tools.scripts.a"]["percent"] == 80.0
        assert t["tools.scripts.b"]["percent"] == 100.0


class TestCmdModule:
    def test_known_module(self, tmp_path: Path, capsys) -> None:
        cov = _make_cov({"tools/scripts/x.py": 50.0})
        cov_path = tmp_path / "c.json"
        cov_path.write_text(json.dumps(cov), encoding="utf-8")
        code = cmd_module(make_ns(coverage=str(cov_path), module="tools.scripts.x"))
        assert code == 0
        out = capsys.readouterr().out
        assert "50.0%" in out
        assert "tools.scripts.x" in out

    def test_unknown_module_returns_one(self, tmp_path: Path, capsys) -> None:
        cov = _make_cov({"tools/scripts/x.py": 50.0})
        cov_path = tmp_path / "c.json"
        cov_path.write_text(json.dumps(cov), encoding="utf-8")
        code = cmd_module(make_ns(coverage=str(cov_path), module="tools.scripts.absent"))
        assert code == 1
        assert "not in coverage data" in capsys.readouterr().out


class TestCmdDiff:
    def test_diff_orders_by_drop(self, tmp_path: Path, capsys) -> None:
        a = _make_cov({"tools/scripts/up.py": 100.0, "tools/scripts/dn.py": 90.0})
        b = _make_cov({"tools/scripts/up.py": 95.0, "tools/scripts/dn.py": 60.0})
        old_p = tmp_path / "a.json"
        new_p = tmp_path / "b.json"
        old_p.write_text(json.dumps(a), encoding="utf-8")
        new_p.write_text(json.dumps(b), encoding="utf-8")
        code = cmd_diff(make_ns(old=str(old_p), new=str(new_p)))
        assert code == 0
        out = capsys.readouterr().out
        # 跌幅最大者(DN: -30pp)应在表中能找到且排在 UP(-5pp)之前
        lines = out.splitlines()
        data_lines = [ln for ln in lines if "tools.scripts.dn" in ln or "tools.scripts.up" in ln]
        assert len(data_lines) == 2
        assert "dn" in data_lines[0]  # DN 行应排第一(跌幅最大)
        assert "up" in data_lines[1]

    def test_missing_files_returns_one(self, tmp_path: Path) -> None:
        code = cmd_diff(make_ns(old=str(tmp_path / "a.json"), new=str(tmp_path / "b.json")))
        assert code == 1


class TestCmdGate:
    def test_passes_when_equal(self, tmp_path: Path) -> None:
        cov = _make_cov({"tools/scripts/a.py": 80.0})
        p = tmp_path / "c.json"
        p.write_text(json.dumps(cov), encoding="utf-8")
        code = cmd_gate(make_ns(coverage=str(p), baseline=str(p), threshold="2.0"))
        assert code == 0

    def test_fails_when_dropped(self, tmp_path: Path) -> None:
        old = _make_cov({"tools/scripts/a.py": 90.0})
        new = _make_cov({"tools/scripts/a.py": 80.0})
        old_p = tmp_path / "old.json"
        new_p = tmp_path / "new.json"
        old_p.write_text(json.dumps(old), encoding="utf-8")
        new_p.write_text(json.dumps(new), encoding="utf-8")
        code = cmd_gate(make_ns(coverage=str(new_p), baseline=str(old_p), threshold="5.0"))
        assert code == 1

    def test_missing_files_returns_one(self, tmp_path: Path) -> None:
        code = cmd_gate(make_ns(coverage=str(tmp_path / "a.json"), baseline=str(tmp_path / "b.json"), threshold="2.0"))
        assert code == 1


class TestCmdSnapshot:
    def test_missing_coverage_returns_one(self, tmp_path: Path) -> None:
        code = cmd_snapshot(make_ns(coverage=str(tmp_path / "nope"), output=str(tmp_path / "out.json")))
        assert code == 1


def make_ns(**kwargs):
    """Build argparse.Namespace-like object."""
    from argparse import Namespace

    return Namespace(**kwargs)

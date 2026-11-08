"""update_stats 第二轮: 缺口函数与 main 分支。

补 count_docs/count_tests/collect_all/_find_drift/_record_trend/main 全分支。45%→90%+
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from tools.scripts.update_stats import (
    README_STATS_TABLE,
    _find_drift,
    _read_readme_stats,
    _record_trend,
    collect_all,
    collect_quality_gate,
    count_adrs,
    count_cases,
    count_docs,
    count_tests,
    main,
    sync_readme,
)


@pytest.fixture
def fake_root(tmp_path: Path) -> Path:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "guide.md").write_text("# g\n", encoding="utf-8")
    (tmp_path / "docs" / "adr").mkdir(exist_ok=True)
    (tmp_path / "case-studies").mkdir()
    for i in range(3):
        (tmp_path / "case-studies" / f"c{i}.md").write_text("x\n", encoding="utf-8")
    return tmp_path


class TestCounters:
    def test_count_docs_recursive(self, fake_root: Path) -> None:
        assert count_docs(fake_root) == 1  # docs/guide.md

    def test_count_cases(self, fake_root: Path) -> None:
        assert count_cases(fake_root) == 3

    def test_count_adrs_missing_dir(self, tmp_path: Path) -> None:
        assert count_adrs(tmp_path) == 0

    def test_count_tests_parses_pytest_output(self, tmp_path: Path) -> None:
        proc = MagicMock(returncode=0)
        proc.stdout = "3275 tests collected in 5.01s"
        with patch("subprocess.run", return_value=proc):
            assert count_tests(tmp_path) == 3275

    def test_count_tests_uses_configured_testpaths(self, tmp_path: Path) -> None:
        """不得硬编码 tests/：pytest.ini 的 testpaths 才是权威口径。"""
        proc = MagicMock(returncode=0)
        proc.stdout = "5612 tests collected"
        with patch("subprocess.run", return_value=proc) as run:
            assert count_tests(tmp_path) == 5612
        cmd = run.call_args.args[0]
        assert not any("tests" in str(part) for part in cmd)

    def test_count_tests_unparseable_raises(self, tmp_path: Path) -> None:
        proc = MagicMock(returncode=1)
        proc.stdout = "no tests ran"
        with patch("subprocess.run", return_value=proc):
            with pytest.raises(RuntimeError, match="无法从 pytest 输出解析"):
                count_tests(tmp_path)


class TestQualityGateCollect:
    def test_missing_hooks_runner_returns_none(self, tmp_path: Path) -> None:
        assert collect_quality_gate(tmp_path) is None

    def test_success_summary(self, tmp_path: Path) -> None:
        hooks = tmp_path / "tools" / "scripts"
        hooks.mkdir(parents=True)
        (hooks / "hooks_runner.py").write_text("# runner\n", encoding="utf-8")
        payload = json.dumps(
            {
                "summary": {
                    "total_files": 100,
                    "passed": 95,
                    "failed": 5,
                    "total_issues": 7,
                    "baseline_exempt": 2,
                }
            }
        )
        proc = MagicMock(returncode=1)
        proc.stdout = payload
        with patch("subprocess.run", return_value=proc):
            gate = collect_quality_gate(tmp_path)
        assert gate is not None
        assert gate["gate_failed"] == 5
        assert gate["gate_pass_rate"] == 95

    def test_zero_total_files_pass_rate_zero(self, tmp_path: Path) -> None:
        hooks = tmp_path / "tools" / "scripts"
        hooks.mkdir(parents=True)
        (hooks / "hooks_runner.py").touch()
        proc = MagicMock(returncode=0)
        proc.stdout = json.dumps({"summary": {"total_files": 0, "passed": 0, "failed": 0, "total_issues": 0}})
        with patch("subprocess.run", return_value=proc):
            gate = collect_quality_gate(tmp_path)
        assert gate is not None and gate["gate_pass_rate"] == 0

    def test_timeout_returns_none(self, tmp_path: Path) -> None:
        import subprocess as sp

        hooks = tmp_path / "tools" / "scripts"
        hooks.mkdir(parents=True)
        (hooks / "hooks_runner.py").touch()
        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="x", timeout=1)):
            assert collect_quality_gate(tmp_path) is None


class TestReadmeSync:
    def _readme(self, root: Path) -> Path:
        readme = root / "README.md"
        lines = ["| 指标 | 值 |", "|---|---|"]
        for label in README_STATS_TABLE.values():
            lines.append(f"| {label} | 1 |")
        readme.write_text("\n".join(lines), encoding="utf-8")
        return readme

    def test_read_stats_and_drift_detection(self, fake_root: Path) -> None:
        readme = self._readme(fake_root)
        stats = {"core_docs": 9, "cases": 9, "adrs": 9, "tests": 9}
        drift = _find_drift(readme, stats)
        assert len(drift) == 4
        assert all("vs 实际 9" in d for d in drift)

    def test_no_drift_when_matching(self, fake_root: Path) -> None:
        readme = self._readme(fake_root)
        stats = dict.fromkeys(("core_docs", "cases", "adrs", "tests"), 1)
        assert _find_drift(readme, stats) == []

    def test_sync_reports_changes(self, fake_root: Path) -> None:
        readme = self._readme(fake_root)
        changes = sync_readme(readme, {"core_docs": 5, "cases": 5, "adrs": 5, "tests": 5})
        assert len(changes) == 4
        assert all(old == 1 and new == 5 for _, old, new in changes)

    def test_read_stats_missing_readme(self, tmp_path: Path) -> None:
        assert _read_readme_stats(tmp_path / "nope.md") == {}


class TestRecordTrendAndMain:
    def test_record_trend_with_gate(self, fake_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        stats = {"core_docs": 1, "cases": 3, "adrs": 0, "tests": 10}
        gate = {"gate_failed": 0, "gate_issues": 0, "gate_baseline_exempt": 0, "gate_pass_rate": 100}
        with patch("tools.scripts.update_stats.collect_quality_gate", return_value=gate):
            _record_trend(fake_root, stats, skip_gate=False)
        history = fake_root / ".quality-trends" / "stats_history.jsonl"
        entries = [json.loads(line) for line in history.read_text(encoding="utf-8").splitlines()]
        assert len(entries) == 2 and entries[1]["gate_pass_rate"] == 100

    def test_record_trend_skipped_gate(self, fake_root: Path, capsys: pytest.CaptureFixture[str]) -> None:
        _record_trend(fake_root, {"core_docs": 1}, skip_gate=True)
        out = capsys.readouterr().out
        assert "趋势快照已记录" in out

    def test_collect_all_merges_counters(self, fake_root: Path) -> None:
        proc = MagicMock(returncode=0)
        proc.stdout = "12 tests collected"
        with patch("subprocess.run", return_value=proc):
            stats = collect_all(fake_root)
        assert stats["core_docs"] == 1 and stats["cases"] == 3 and stats["tests"] == 12

    def test_main_check_mode_exit_1_on_drift(
        self, fake_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        readme = fake_root / "README.md"
        readme.write_text("| 🧪 测试用例 | 999 |\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["update_stats.py", "--check"])
        monkeypatch.setattr("tools.scripts.update_stats.get_project_root", lambda: fake_root)
        with patch("tools.scripts.update_stats.count_tests", return_value=10):
            code = main()
        assert code == 1 and "不一致" in capsys.readouterr().out

    def test_main_check_mode_passes(
        self, fake_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        readme = fake_root / "README.md"
        readme.write_text(
            "| 📄 核心文档 | 1 |\n| 📚 实践案例 | 3 |\n| 📋 架构决策 | 1 |\n| 🧪 测试用例 | 1 |\n",
            encoding="utf-8",
        )
        # 直接让所有计数返回与 README 一致
        monkeypatch.setattr("sys.argv", ["update_stats.py", "--check"])
        monkeypatch.setattr("tools.scripts.update_stats.get_project_root", lambda: fake_root)
        with (
            patch("tools.scripts.update_stats.count_docs", return_value=1),
            patch("tools.scripts.update_stats.count_cases", return_value=3),
            patch("tools.scripts.update_stats.count_adrs", return_value=1),
            patch("tools.scripts.update_stats.count_tests", return_value=1),
        ):
            code = main()
        assert code == 0 and "一致" in capsys.readouterr().out

    def test_main_json_mode(
        self, fake_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        monkeypatch.setattr("sys.argv", ["update_stats.py", "--json"])
        monkeypatch.setattr("tools.scripts.update_stats.get_project_root", lambda: fake_root)
        proc = MagicMock(returncode=0)
        proc.stdout = "5 tests collected"
        with (
            patch("subprocess.run", return_value=proc),
            patch("tools.scripts.update_stats.collect_quality_gate", return_value=None),
        ):
            code = main()
        out = capsys.readouterr().out
        assert code == 0 and json.loads(out)["cases"] == 3

    def test_main_json_mode_skip_quality_gate(
        self, fake_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--json --skip-quality-gate 不得采集质量门禁，也不得臆造 gate_* 数值。"""
        monkeypatch.setattr("sys.argv", ["update_stats.py", "--json", "--skip-quality-gate"])
        monkeypatch.setattr("tools.scripts.update_stats.get_project_root", lambda: fake_root)
        proc = MagicMock(returncode=0)
        proc.stdout = "5 tests collected"
        with (
            patch("subprocess.run", return_value=proc),
            patch("tools.scripts.update_stats.collect_quality_gate") as gate,
        ):
            code = main()
        gate.assert_not_called()
        data = json.loads(capsys.readouterr().out)
        assert code == 0 and data["cases"] == 3
        assert "gate_failed" not in data and "gate_pass_rate" not in data

    def test_main_sync_mode_records_trend(
        self, fake_root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        readme = fake_root / "README.md"
        readme.write_text("| 🧪 测试用例 | 1 |\n", encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["update_stats.py", "--skip-quality-gate"])
        monkeypatch.setattr("tools.scripts.update_stats.get_project_root", lambda: fake_root)
        with (
            patch("tools.scripts.update_stats.count_docs", return_value=1),
            patch("tools.scripts.update_stats.count_cases", return_value=3),
            patch("tools.scripts.update_stats.count_adrs", return_value=0),
            patch("tools.scripts.update_stats.count_tests", return_value=7),
        ):
            code = main()
        assert code == 0
        out = capsys.readouterr().out
        assert "README 统计已更新" in out or "已是最新" in out
        assert (fake_root / ".quality-trends" / "stats_history.jsonl").exists()

"""变异得分统计脚本的测试 (mutmut 缓存库 → 击杀率 → 阈值判定)。"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from tools.scripts.mutation_score import (
    STATUS_KILLED,
    STATUS_SURVIVED,
    STATUS_TIMEOUT,
    format_summary,
    kill_rate,
    main,
    read_status_counts,
)


def _make_cache(path: Path, rows: list[tuple[str, int]]) -> Path:
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE Mutant (status TEXT)")
    connection.executemany("INSERT INTO Mutant (status) VALUES (?)", [(status,) for status, _ in rows])
    # 用重复插入制造计数
    for status, count in rows:
        connection.execute(
            "INSERT INTO Mutant (status) SELECT status FROM Mutant WHERE status = ? LIMIT ?",
            (status, count),
        )
    connection.commit()
    connection.close()
    return path


class TestReadStatusCounts:
    def test_missing_cache_returns_empty(self, tmp_path: Path) -> None:
        assert read_status_counts(tmp_path / "nope.cache") == {}

    def test_counts_grouped_by_status(self, tmp_path: Path) -> None:
        cache = tmp_path / ".mutmut-cache"
        connection = sqlite3.connect(str(cache))
        connection.execute("CREATE TABLE Mutant (status TEXT)")
        connection.executemany(
            "INSERT INTO Mutant (status) VALUES (?)",
            [(STATUS_KILLED,), (STATUS_KILLED,), (STATUS_SURVIVED,)],
        )
        connection.commit()
        connection.close()
        assert read_status_counts(cache) == {STATUS_KILLED: 2, STATUS_SURVIVED: 1}

    def test_unexpected_schema_returns_empty(self, tmp_path: Path) -> None:
        cache = tmp_path / ".mutmut-cache"
        connection = sqlite3.connect(str(cache))
        connection.execute("CREATE TABLE Other (x TEXT)")
        connection.commit()
        connection.close()
        assert read_status_counts(cache) == {}


class TestKillRate:
    def test_no_mutants_is_zero(self) -> None:
        assert kill_rate({}) == 0.0

    def test_all_killed(self) -> None:
        assert kill_rate({STATUS_KILLED: 10, STATUS_SURVIVED: 0}) == 1.0

    def test_partial(self) -> None:
        assert kill_rate({STATUS_KILLED: 3, STATUS_SURVIVED: 1}) == 0.75

    def test_timeout_counts_as_tested(self) -> None:
        assert kill_rate({STATUS_KILLED: 1, STATUS_TIMEOUT: 1}) == 0.5


class TestMain:
    def test_missing_cache_fails(self, tmp_path: Path) -> None:
        assert main(["--cache", str(tmp_path / "nope.cache")]) == 1

    def test_below_threshold_fails(self, tmp_path: Path) -> None:
        cache = tmp_path / ".mutmut-cache"
        connection = sqlite3.connect(str(cache))
        connection.execute("CREATE TABLE Mutant (status TEXT)")
        connection.executemany(
            "INSERT INTO Mutant (status) VALUES (?)",
            [(STATUS_KILLED,), (STATUS_SURVIVED,), (STATUS_SURVIVED,), (STATUS_SURVIVED,)],
        )
        connection.commit()
        connection.close()
        assert main(["--cache", str(cache), "--min-rate", "0.8"]) == 1

    def test_above_threshold_passes(self, tmp_path: Path) -> None:
        cache = tmp_path / ".mutmut-cache"
        connection = sqlite3.connect(str(cache))
        connection.execute("CREATE TABLE Mutant (status TEXT)")
        connection.executemany(
            "INSERT INTO Mutant (status) VALUES (?)",
            [(STATUS_KILLED,), (STATUS_KILLED,), (STATUS_KILLED,), (STATUS_SURVIVED,)],
        )
        connection.commit()
        connection.close()
        assert main(["--cache", str(cache), "--min-rate", "0.5"]) == 0

    def test_summary_appended_to_report(self, tmp_path: Path) -> None:
        cache = tmp_path / ".mutmut-cache"
        connection = sqlite3.connect(str(cache))
        connection.execute("CREATE TABLE Mutant (status TEXT)")
        connection.execute("INSERT INTO Mutant (status) VALUES (?)", (STATUS_KILLED,))
        connection.commit()
        connection.close()
        report = tmp_path / "mutation-report.txt"
        report.write_text("Survived: none\n", encoding="utf-8")
        main(["--cache", str(cache), "--min-rate", "0.1", "--report", str(report)])
        text = report.read_text(encoding="utf-8")
        assert "Survived: none" in text
        assert "变异测试得分" in text

    def test_summary_contains_counts(self) -> None:
        text = format_summary({STATUS_KILLED: 5, STATUS_SURVIVED: 2}, 0.7)
        assert "ok_killed" in text
        assert "70.0%" in text

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


def _make_scoped_cache(path: Path, files: dict[str, list[tuple[str, int]]]) -> Path:
    """构建带 SourceFile/Line 关联的 mutmut 缓存库。

    Args:
        path: 缓存库路径
        files: 源文件名 → [(status, count), ...]

    Returns:
        缓存库路径
    """
    connection = sqlite3.connect(str(path))
    connection.execute(
        'CREATE TABLE "SourceFile" ('
        '"id" INTEGER PRIMARY KEY AUTOINCREMENT, "filename" TEXT NOT NULL, "hash" TEXT NOT NULL)'
    )
    connection.execute(
        'CREATE TABLE "Line" ('
        '"id" INTEGER PRIMARY KEY AUTOINCREMENT, '
        '"sourcefile" INTEGER NOT NULL REFERENCES "SourceFile" ("id") ON DELETE CASCADE, '
        '"line" TEXT NOT NULL, "line_number" INTEGER NOT NULL)'
    )
    connection.execute(
        'CREATE TABLE "Mutant" ('
        '"id" INTEGER PRIMARY KEY AUTOINCREMENT, '
        '"line" INTEGER NOT NULL REFERENCES "Line" ("id") ON DELETE CASCADE, '
        '"index" INTEGER NOT NULL, "tested_against_hash" TEXT NOT NULL, "status" TEXT NOT NULL)'
    )
    for filename, rows in files.items():
        cursor = connection.execute("INSERT INTO SourceFile (filename, hash) VALUES (?, ?)", (filename, "h"))
        sourcefile_id = int(cursor.lastrowid)
        for status, count in rows:
            for _ in range(count):
                line_cursor = connection.execute(
                    "INSERT INTO Line (sourcefile, line, line_number) VALUES (?, ?, ?)", (sourcefile_id, "x = 1", 1)
                )
                connection.execute(
                    "INSERT INTO Mutant (line, \"index\", tested_against_hash, status) VALUES (?, 0, '', ?)",
                    (line_cursor.lastrowid, status),
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


class TestReadStatusCountsPaths:
    """--paths 按源文件过滤计分 (多目标共用缓存时按目标门禁)。"""

    def test_filter_by_source_file(self, tmp_path: Path) -> None:
        cache = _make_scoped_cache(
            tmp_path / "cache",
            {
                "tools/scripts/_sc_pypi.py": [(STATUS_KILLED, 2)],
                "tools/scripts/hooks/supply_runner.py": [(STATUS_SURVIVED, 3)],
            },
        )
        assert read_status_counts(cache, ("tools/scripts/_sc_pypi.py",)) == {STATUS_KILLED: 2}
        assert read_status_counts(cache, ("tools/scripts/hooks/supply_runner.py",)) == {STATUS_SURVIVED: 3}
        assert read_status_counts(cache) == {STATUS_KILLED: 2, STATUS_SURVIVED: 3}

    def test_unknown_path_returns_empty(self, tmp_path: Path) -> None:
        cache = _make_scoped_cache(tmp_path / "cache", {"a.py": [(STATUS_KILLED, 1)]})
        assert read_status_counts(cache, ("b.py",)) == {}


class TestMainPathScope:
    """main 的 --paths 语义: 范围内无已测变异体必须失败。"""

    def test_empty_scope_fails(self, tmp_path: Path) -> None:
        cache = _make_scoped_cache(tmp_path / "cache", {"a.py": [(STATUS_KILLED, 4)]})
        assert main(["--cache", str(cache), "--paths", "b.py"]) == 1

    def test_scoped_rate_passes(self, tmp_path: Path) -> None:
        cache = _make_scoped_cache(
            tmp_path / "cache",
            {"a.py": [(STATUS_SURVIVED, 1)], "b.py": [(STATUS_KILLED, 3)]},
        )
        assert main(["--cache", str(cache), "--paths", "b.py", "--min-rate", "0.6"]) == 0

    def test_scoped_rate_fails(self, tmp_path: Path) -> None:
        cache = _make_scoped_cache(tmp_path / "cache", {"b.py": [(STATUS_SURVIVED, 3), (STATUS_KILLED, 2)]})
        assert main(["--cache", str(cache), "--paths", "b.py", "--min-rate", "0.6"]) == 1

    def test_summary_includes_scope(self) -> None:
        text = format_summary({STATUS_KILLED: 3}, 1.0, ("b.py",))
        assert "范围: b.py" in text


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

"""Tests for store.py: 统一 SQLite 存储层（检查历史、增量缓存、趋势快照）。"""

from __future__ import annotations

import pytest

from tools.scripts.rules_engine.store import (
    CheckStore,
    close_connection,
    get_connection,
    init_db,
)


@pytest.fixture
def db_path(tmp_path):
    """Provide a temporary database path."""
    return str(tmp_path / "test_store.db")


@pytest.fixture
def store(db_path):
    """Provide a CheckStore instance, closed after test."""
    s = CheckStore(db_path)
    yield s
    s.close()
    close_connection(db_path)


class TestInitDb:
    """Test unified database initialization."""

    def test_creates_all_tables(self, db_path):
        conn = init_db(db_path)
        tables = {t[0] for t in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert {
            "quality_runs",
            "file_results",
            "rule_violations",
            "check_cache",
            "trend_snapshots",
        } <= tables
        conn.close()

    def test_connection_caching(self, db_path):
        conn1 = get_connection(db_path)
        conn2 = get_connection(db_path)
        assert conn1 is conn2
        close_connection(db_path)


class TestCheckStoreRuns:
    """Test run recording and history."""

    def test_record_run_with_file_results(self, store: CheckStore):
        report = {
            "summary": {
                "total_files": 1,
                "errors": 1,
                "warnings": 2,
                "info": 0,
                "passed": 0,
                "failed": 1,
            },
            "results": [
                {
                    "file": "a.py",
                    "language": "python",
                    "passed": False,
                    "errors": 1,
                    "warnings": 2,
                    "issues": [
                        {
                            "rule_id": "no-bare-except",
                            "severity": "error",
                            "category": "anti-pattern",
                        },
                        {
                            "rule_id": "long-line",
                            "severity": "warning",
                            "category": "style",
                        },
                    ],
                }
            ],
        }
        run_id = store.record_run(report)
        assert run_id > 0

        latest = store.get_latest_run()
        assert latest is not None
        assert latest["summary"]["errors"] == 1

        files = store.get_latest_file_results()
        assert len(files) == 1
        assert files[0]["file"] == "a.py"
        assert files[0]["errors"] == 1

        violations = store.conn.execute("SELECT * FROM rule_violations WHERE run_id = ?", (run_id,)).fetchall()
        assert len(violations) == 2

    def test_run_history(self, store: CheckStore):
        for i in range(3):
            report = {
                "summary": {
                    "total_files": 1,
                    "errors": i,
                    "warnings": 0,
                    "info": 0,
                    "passed": 1,
                    "failed": 0,
                }
            }
            store.record_run(report)

        history = store.get_run_history(limit=2)
        assert len(history) == 2
        assert history[0]["errors"] == 2  # 最新的在前


class TestCheckCache:
    """Test incremental check cache."""

    def test_cache_miss_then_hit(self, store: CheckStore):
        assert store.get_cached_result("a.py", mtime=100.0, size=10) is None

        store.set_cached_result(
            "a.py",
            mtime=100.0,
            size=10,
            result={
                "language": "python",
                "passed": False,
                "errors": 1,
                "warnings": 0,
                "info": 0,
                "issues": [{"rule_id": "no-bare-except", "severity": "error"}],
            },
        )

        cached = store.get_cached_result("a.py", mtime=100.0, size=10)
        assert cached is not None
        assert cached["errors"] == 1
        assert cached["issues"][0]["rule_id"] == "no-bare-except"

        # mtime 变化 → 未命中
        assert store.get_cached_result("a.py", mtime=101.0, size=10) is None

    def test_set_cached_result_updates(self, store: CheckStore):
        store.set_cached_result(
            "b.py",
            mtime=1.0,
            size=1,
            result={
                "language": "python",
                "passed": True,
                "errors": 0,
                "warnings": 0,
                "info": 0,
                "issues": [],
            },
        )
        store.set_cached_result(
            "b.py",
            mtime=1.0,
            size=1,
            result={
                "language": "python",
                "passed": False,
                "errors": 5,
                "warnings": 0,
                "info": 0,
                "issues": [],
            },
        )
        cached = store.get_cached_result("b.py", mtime=1.0, size=1)
        assert cached is not None
        assert cached["errors"] == 5

    def test_cache_stats_and_prune(self, store: CheckStore):
        for i in range(5):
            store.set_cached_result(
                f"f{i}.py",
                mtime=float(i),
                size=i,
                result={
                    "language": "py",
                    "passed": True,
                    "errors": 0,
                    "warnings": 0,
                    "info": 0,
                    "issues": [],
                },
            )
        stats = store.cache_hit_rate()
        assert stats["cached_files"] == 5

        removed = store.prune_cache(keep=2)
        assert removed == 3
        assert len(store.get_cached_files()) == 2


class TestSnapshots:
    """Test trend snapshot storage."""

    def test_add_and_get(self, store: CheckStore):
        snap = {
            "timestamp": 100.0,
            "total_files": 10,
            "total_issues": 3,
            "errors": 1,
            "warnings": 2,
            "info": 0,
            "categories": {"anti-pattern": 3},
            "rule_counts": {"no-bare-except": 1},
            "languages": {"python": 10},
            "semantic_issues": 0,
            "hallucination_findings": 0,
        }
        sid = store.add_snapshot(snap)
        assert sid > 0

        snaps = store.get_snapshots()
        assert len(snaps) == 1
        assert snaps[0]["categories"] == {"anti-pattern": 3}

    def test_clear(self, store: CheckStore):
        store.add_snapshot(
            {
                "timestamp": 1.0,
                "total_files": 1,
                "total_issues": 0,
                "errors": 0,
                "warnings": 0,
                "info": 0,
            }
        )
        store.clear_snapshots()
        assert store.get_snapshots() == []


class TestModuleLevelRecordRun:
    """Test module-level record_run (dashboard 兼容 API)."""

    def test_record_run_compat(self, db_path):
        conn = init_db(db_path)
        from tools.scripts.rules_engine.store import record_run

        run_id = record_run(
            conn,
            {
                "summary": {
                    "total_files": 1,
                    "errors": 0,
                    "warnings": 0,
                    "info": 0,
                    "passed": 1,
                    "failed": 0,
                }
            },
        )
        assert run_id > 0
        conn.close()

    def test_record_run_writes_file_results(self, db_path):
        conn = init_db(db_path)
        from tools.scripts.rules_engine.store import record_run

        report = {
            "summary": {
                "total_files": 1,
                "errors": 1,
                "warnings": 0,
                "info": 0,
                "passed": 0,
                "failed": 1,
            },
            "results": [
                {
                    "file": "x.py",
                    "language": "python",
                    "passed": False,
                    "errors": 1,
                    "warnings": 0,
                    "info": 0,
                    "issues": [{"rule_id": "r1", "severity": "error", "category": "c"}],
                }
            ],
        }
        run_id = record_run(conn, report)
        rows = conn.execute("SELECT * FROM file_results WHERE run_id = ?", (run_id,)).fetchall()
        assert len(rows) == 1
        assert rows[0][2] == "x.py"
        conn.close()


class TestParallelCacheIntegration:
    """check_directory 并行分支的增量缓存集成（回归: 并行 worker 曾完全不写缓存）。"""

    def test_parallel_run_populates_cache(self, tmp_path):
        """jobs=4 全量检查后，缓存应覆盖所有被检文件（而非恒为空）。"""
        import sqlite3

        from tools.scripts.rules_engine.checker import check_directory

        src = tmp_path / "src"
        src.mkdir()
        for i in range(8):
            (src / f"mod{i}.py").write_text(f"x{i}: int = {i}\n")

        db = str(tmp_path / "cache.db")
        results = check_directory(src, jobs=4, use_cache=True, db_path=db)
        assert len(results) == 8

        conn = sqlite3.connect(db)
        n = conn.execute("SELECT COUNT(*) FROM check_cache").fetchone()[0]
        conn.close()
        assert n == 8, f"并行分支应写满 8 条缓存, 实际 {n}"

    def test_parallel_rerun_hits_cache(self, tmp_path):
        """二跑仅 mtime 变化的文件被重查（通过 updated_at 时间戳验证）。"""
        import os
        import sqlite3
        import time as time_mod

        from tools.scripts.rules_engine.checker import check_directory

        src = tmp_path / "src"
        src.mkdir()
        target = src / "target.py"
        target.write_text("a: int = 1\n")
        for i in range(6):
            (src / f"other{i}.py").write_text(f"b{i}: int = {i}\n")

        db = str(tmp_path / "cache.db")
        check_directory(src, jobs=4, use_cache=True, db_path=db)

        def updated_map() -> dict:
            conn = sqlite3.connect(db)
            out = {r[0]: r[1] for r in conn.execute("SELECT file_path, updated_at FROM check_cache")}
            conn.close()
            return out

        before = updated_map()
        time_mod.sleep(1.1)  # 越过秒级时间戳精度
        os.utime(target)  # 仅改 mtime → 缓存键失效

        check_directory(src, jobs=4, use_cache=True, db_path=db)
        after = updated_map()

        changed = [k for k in after if before.get(k) != after[k]]
        assert len(changed) == 1 and changed[0].endswith("target.py"), f"应只重查 target.py, 实际变更: {changed}"

"""统一 SQLite 存储层：检查历史、增量缓存、趋势快照。

集中管理所有质量检查的持久化：
- check_runs: 每次检查运行的摘要（替代 dashboard.quality_runs）
- file_results: 每个文件的检查结果明细
- check_cache: 文件级增量缓存（mtime + size 未变则复用）
- trend_snapshots: 质量趋势快照（替代 quality_trends JSON 文件）

用法:
    from tools.scripts.rules_engine.store import CheckStore

    store = CheckStore(db_path)
    store.record_run(report)
    cached = store.get_cached_results("path/to/file.py", mtime, size)
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 1


def _now_iso() -> str:
    """当前时间 ISO 格式（SQLite 排序友好）。"""
    return datetime.now().isoformat()


def _create_quality_tables(conn: sqlite3.Connection) -> None:
    """创建质量运行/文件结果/规则违规表（与 dashboard 兼容）。"""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS quality_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            total_files INTEGER,
            total_errors INTEGER,
            total_warnings INTEGER,
            total_info INTEGER,
            passed_files INTEGER,
            failed_files INTEGER,
            report_json TEXT
        )
        """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS file_results (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            file_path TEXT,
            language TEXT,
            errors INTEGER,
            warnings INTEGER,
            info INTEGER,
            passed BOOLEAN,
            issues_json TEXT,
            FOREIGN KEY (run_id) REFERENCES quality_runs(id)
        )
        """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS rule_violations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id INTEGER,
            rule_id TEXT,
            severity TEXT,
            count INTEGER,
            FOREIGN KEY (run_id) REFERENCES quality_runs(id)
        )
        """)


def _create_cache_tables(conn: sqlite3.Connection) -> None:
    """创建增量缓存与趋势快照表（任务7 新增）。"""
    # 增量检查缓存: (file_path, mtime, size) 唯一 → 上次结果
    conn.execute("""
        CREATE TABLE IF NOT EXISTS check_cache (
            file_path TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            language TEXT,
            passed BOOLEAN,
            errors INTEGER,
            warnings INTEGER,
            info INTEGER,
            issues_json TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (file_path, mtime, size)
        )
        """)
    # 趋势快照（替代 quality_trends 的 JSON 文件）
    conn.execute("""
        CREATE TABLE IF NOT EXISTS trend_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp REAL NOT NULL,
            total_files INTEGER,
            total_issues INTEGER,
            errors INTEGER,
            warnings INTEGER,
            info INTEGER,
            categories_json TEXT,
            rule_counts_json TEXT,
            languages_json TEXT,
            semantic_issues INTEGER,
            hallucination_findings INTEGER
        )
        """)


def _default_db_path() -> str:
    """统一存储默认路径：优先 [tool.adg].trend_db 配置。"""
    try:
        from tools.scripts.app_config import get_path

        return str(get_path("trend_db", Path("adg_quality.db")))
    except Exception:
        return "adg_quality.db"


def init_db(db_path: str = "") -> sqlite3.Connection:
    """初始化统一存储数据库，返回连接。

    Schema 与 dashboard 的 quality_runs 兼容（保留原表），并新增
    check_cache / trend_snapshots 表用于增量检查与趋势存储。
    """
    conn = sqlite3.connect(db_path or _default_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _create_quality_tables(conn)
    _create_cache_tables(conn)
    conn.execute("PRAGMA user_version = " + str(SCHEMA_VERSION))
    conn.commit()
    return conn


class CheckStore:
    """统一检查存储：运行记录、文件结果、增量缓存、趋势快照。"""

    def __init__(self, db_path: str | Path | None = None) -> None:
        resolved = db_path if db_path is not None else _default_db_path()
        self.db_path = str(resolved)
        self.conn = get_connection(self.db_path)

    def close(self) -> None:
        """关闭数据库连接。"""
        try:
            self.conn.close()
        except sqlite3.Error:
            pass

    # ── 检查运行 ──────────────────────────────────────────────

    def record_run(self, report: dict[str, Any], file_results: list[dict[str, Any]] | None = None) -> int:
        """记录一次检查运行，返回 run_id。

        Args:
            report: 含 summary 的检查报告。
            file_results: 可选的逐文件结果，写入 file_results 表。
        """
        return _record_run(self.conn, report, file_results)

    def get_latest_run(self) -> dict[str, Any] | None:
        """获取最近一次运行摘要。"""
        row = self.conn.execute("SELECT report_json FROM quality_runs ORDER BY id DESC LIMIT 1").fetchone()
        if row and row[0]:
            return cast(dict[str, Any], json.loads(row[0]))
        return None

    def get_run_history(self, limit: int = 30) -> list[dict[str, Any]]:
        """获取运行历史（不含完整报告）。"""
        rows = self.conn.execute(
            """SELECT id, timestamp, total_files, total_errors, total_warnings,
                      total_info, passed_files, failed_files
               FROM quality_runs ORDER BY id DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "id": r[0],
                "timestamp": r[1],
                "total_files": r[2],
                "errors": r[3],
                "warnings": r[4],
                "info": r[5],
                "passed": r[6],
                "failed": r[7],
            }
            for r in rows
        ]

    def get_latest_file_results(self) -> list[dict[str, Any]]:
        """获取最近一次运行的逐文件结果。"""
        latest_id = self.conn.execute("SELECT MAX(id) FROM quality_runs").fetchone()[0]
        if not latest_id:
            return []
        rows = self.conn.execute(
            """SELECT file_path, language, errors, warnings, info, passed, issues_json
               FROM file_results WHERE run_id = ?""",
            (latest_id,),
        ).fetchall()
        return [
            {
                "file": r[0],
                "language": r[1],
                "errors": r[2],
                "warnings": r[3],
                "info": r[4],
                "passed": bool(r[5]),
                "issues": json.loads(r[6]) if r[6] else [],
            }
            for r in rows
        ]

    # ── 增量缓存 ──────────────────────────────────────────────

    def get_cached_result(self, file_path: str, mtime: float, size: int) -> dict[str, Any] | None:
        """按 mtime+size 取缓存。命中返回 {passed, errors, warnings, info, issues}，未命中返回 None。"""
        row = self.conn.execute(
            """SELECT language, passed, errors, warnings, info, issues_json
               FROM check_cache WHERE file_path = ? AND mtime = ? AND size = ?""",
            (file_path, mtime, size),
        ).fetchone()
        if not row:
            return None
        return {
            "language": row[0],
            "passed": bool(row[1]),
            "errors": row[2],
            "warnings": row[3],
            "info": row[4],
            "issues": json.loads(row[5]) if row[5] else [],
        }

    def set_cached_result(
        self,
        file_path: str,
        mtime: float,
        size: int,
        result: dict[str, Any],
    ) -> None:
        """写入/更新某文件的缓存结果。"""
        issues = result.get("issues", [])
        self.conn.execute(
            """INSERT OR REPLACE INTO check_cache
               (file_path, mtime, size, language, passed, errors, warnings, info, issues_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_path,
                mtime,
                size,
                result.get("language", "unknown"),
                1 if result.get("passed", False) else 0,
                result.get("errors", 0),
                result.get("warnings", 0),
                result.get("info", 0),
                json.dumps(issues, ensure_ascii=False),
                _now_iso(),
            ),
        )
        self.conn.commit()

    def get_cached_files(self) -> list[dict[str, Any]]:
        """列出所有缓存条目（文件路径、mtime、size、错误数）。"""
        rows = self.conn.execute(
            """SELECT file_path, mtime, size, errors, warnings, info FROM check_cache"""
        ).fetchall()
        return [
            {
                "file_path": r[0],
                "mtime": r[1],
                "size": r[2],
                "errors": r[3],
                "warnings": r[4],
                "info": r[5],
            }
            for r in rows
        ]

    def cache_hit_rate(self) -> dict[str, int]:
        """返回缓存统计：缓存文件数、缓存问题总数。"""
        total = self.conn.execute("SELECT COUNT(*) FROM check_cache").fetchone()[0]
        total_issues = self.conn.execute(
            "SELECT COALESCE(SUM(errors + warnings + info), 0) FROM check_cache"
        ).fetchone()[0]
        return {"cached_files": total, "cached_issues": total_issues}

    def prune_cache(self, keep: int = 500) -> int:
        """裁剪缓存，保留最近 keep 条（按时间戳），返回删除条数。"""
        cursor = self.conn.execute(
            """DELETE FROM check_cache WHERE rowid IN (
                  SELECT rowid FROM check_cache ORDER BY updated_at DESC LIMIT -1 OFFSET ?
              )""",
            (keep,),
        )
        self.conn.commit()
        return cursor.rowcount

    # ── 趋势快照 ──────────────────────────────────────────────

    def add_snapshot(self, snapshot: dict[str, Any]) -> int:
        """写入一条趋势快照，返回 id。"""
        cursor = self.conn.execute(
            """INSERT INTO trend_snapshots
               (timestamp, total_files, total_issues, errors, warnings, info,
                categories_json, rule_counts_json, languages_json,
                semantic_issues, hallucination_findings)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                snapshot.get("timestamp", 0.0),
                snapshot.get("total_files", 0),
                snapshot.get("total_issues", 0),
                snapshot.get("errors", 0),
                snapshot.get("warnings", 0),
                snapshot.get("info", 0),
                json.dumps(snapshot.get("categories", {}), ensure_ascii=False),
                json.dumps(snapshot.get("rule_counts", {}), ensure_ascii=False),
                json.dumps(snapshot.get("languages", {}), ensure_ascii=False),
                snapshot.get("semantic_issues", 0),
                snapshot.get("hallucination_findings", 0),
            ),
        )
        self.conn.commit()
        return cursor.lastrowid or 0

    def get_snapshots(self, limit: int = 100) -> list[dict[str, Any]]:
        """按时间倒序返回快照。"""
        rows = self.conn.execute(
            """SELECT timestamp, total_files, total_issues, errors, warnings, info,
                      categories_json, rule_counts_json, languages_json,
                      semantic_issues, hallucination_findings
               FROM trend_snapshots ORDER BY timestamp DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [
            {
                "timestamp": r[0],
                "total_files": r[1],
                "total_issues": r[2],
                "errors": r[3],
                "warnings": r[4],
                "info": r[5],
                "categories": json.loads(r[6]) if r[6] else {},
                "rule_counts": json.loads(r[7]) if r[7] else {},
                "languages": json.loads(r[8]) if r[8] else {},
                "semantic_issues": r[9],
                "hallucination_findings": r[10],
            }
            for r in rows
        ]

    def clear_snapshots(self) -> None:
        """清空全部趋势快照。"""
        self.conn.execute("DELETE FROM trend_snapshots")
        self.conn.commit()


_connections: dict[str, sqlite3.Connection] = {}


def get_connection(db_path: str | Path | None = None) -> sqlite3.Connection:
    """获取（并缓存）统一数据库连接。

    同一路径返回同一连接，避免重复打开；线程安全由调用方保证
    （check_same_thread=False 供 FastAPI 使用）。
    """
    key = str(db_path) if db_path is not None else _default_db_path()
    if key not in _connections:
        _connections[key] = init_db(key)
    return _connections[key]


def close_connection(db_path: str | Path | None = None) -> None:
    """关闭并移除缓存的连接。"""
    key = str(db_path) if db_path is not None else _default_db_path()
    conn = _connections.pop(key, None)
    if conn is not None:
        try:
            conn.close()
        except sqlite3.Error:
            pass


def _record_run(
    conn: sqlite3.Connection,
    report: dict[str, Any],
    file_results: list[dict[str, Any]] | None = None,
) -> int:
    """在给定连接上记录一次检查运行（供 CheckStore 与模块级 record_run 复用）。"""
    summary = report.get("summary", {})
    cursor = conn.execute(
        """INSERT INTO quality_runs
           (timestamp, total_files, total_errors, total_warnings, total_info,
            passed_files, failed_files, report_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            _now_iso(),
            summary.get("total_files", 0),
            summary.get("errors", 0),
            summary.get("warnings", 0),
            summary.get("info", 0),
            summary.get("passed", 0),
            summary.get("failed", 0),
            json.dumps(report, ensure_ascii=False),
        ),
    )
    run_id = cursor.lastrowid or 0
    _insert_file_results(conn, run_id, file_results or report.get("results", []))
    _insert_rule_violations(conn, run_id, report.get("results", []))
    conn.commit()
    return run_id


def _insert_file_results(conn: sqlite3.Connection, run_id: int, file_results: list[dict[str, Any]]) -> None:
    """写入逐文件结果。"""
    if not file_results:
        return
    conn.executemany(
        """INSERT INTO file_results
           (run_id, file_path, language, errors, warnings, info, passed, issues_json)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        [
            (
                run_id,
                r.get("file", ""),
                r.get("language", "unknown"),
                r.get("errors", 0),
                r.get("warnings", 0),
                r.get("info", 0),
                1 if r.get("passed", False) else 0,
                json.dumps(r.get("issues", []), ensure_ascii=False),
            )
            for r in file_results
        ],
    )


def _insert_rule_violations(conn: sqlite3.Connection, run_id: int, results: list[dict[str, Any]]) -> None:
    """聚合规则违规计数。"""
    counts: dict[tuple[str, str], int] = {}
    for result in results:
        for issue in result.get("issues", []):
            key = (issue.get("rule_id", "unknown"), issue.get("severity", "info"))
            counts[key] = counts.get(key, 0) + 1
    if not counts:
        return
    conn.executemany(
        """INSERT INTO rule_violations (run_id, rule_id, severity, count)
           VALUES (?, ?, ?, ?)""",
        [(run_id, rule_id, severity, count) for (rule_id, severity), count in counts.items()],
    )


def record_run(conn: sqlite3.Connection, report: dict[str, Any]) -> int:
    """记录一次质量检查运行（兼容 dashboard 的模块级 API）。

    与 CheckStore.record_run 等价，供已有调用方（dashboard / 脚本）使用。
    """
    return _record_run(conn, report)

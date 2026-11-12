"""统一 SQLite 存储层：检查历史、增量缓存、趋势快照。

集中管理所有质量检查的持久化：
- check_runs: 每次检查运行的摘要（替代 dashboard.quality_runs）
- file_results: 每个文件的检查结果明细
- check_cache: 文件级增量缓存（mtime + size + rules_hash 未变则复用）
- trend_snapshots: 质量趋势快照（替代 quality_trends JSON 文件）

用法:
    from tools.scripts.rules_engine.store import CheckStore

    store = CheckStore(db_path)
    store.record_run(report)
    cached = store.get_cached_results("path/to/file.py", mtime, size)
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast

SCHEMA_VERSION = 2


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
    """创建增量缓存与趋势快照表（任务7 新增；v2 增加 rules_hash 列）。"""
    # 增量检查缓存: (file_path, mtime, size, rules_hash) 唯一 → 上次结果。
    # rules_hash 使规则内容/引擎版本变化时旧缓存自然失效（键不匹配即未命中），
    # 无需迁移清理，陈旧条目由 prune_cache 按时间裁剪。
    conn.execute("""
        CREATE TABLE IF NOT EXISTS check_cache (
            file_path TEXT NOT NULL,
            mtime REAL NOT NULL,
            size INTEGER NOT NULL,
            rules_hash TEXT NOT NULL DEFAULT '',
            language TEXT,
            passed BOOLEAN,
            errors INTEGER,
            warnings INTEGER,
            info INTEGER,
            issues_json TEXT,
            updated_at TEXT NOT NULL,
            PRIMARY KEY (file_path, mtime, size, rules_hash)
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


def compute_rules_signature() -> str:
    """计算规则集签名（sha256 短摘要），用于增量缓存的失效维度。

    输入: 规则目录全部 YAML 内容 + 引擎 schema 版本。任一规则文件变化、
    增删规则文件或引擎升级，签名都会改变 → 旧缓存键不匹配自然失效。
    成本实测 ~7ms（41 个文件 / 289KB），相对单次检查可忽略。
    失败时返回空串（退化为不含规则维度的旧行为，不阻断检查）。
    """
    try:
        from tools.scripts._common import rules_dir

        root = Path(rules_dir())
        h = hashlib.sha256()
        h.update(str(SCHEMA_VERSION).encode())
        for f in sorted(root.rglob("*.yml")):
            h.update(str(f.relative_to(root)).encode())
            h.update(f.read_bytes())
        return h.hexdigest()[:16]
    except Exception:  # noqa: BLE001 - 签名失败不应阻断检查
        return ""


def _default_db_path() -> str:
    """统一存储默认路径：优先 [tool.adg].trend_db 配置。"""
    try:
        from tools.scripts.app_config import get_path

        return str(get_path("trend_db", Path("adg_quality.db")))
    except Exception:
        return "adg_quality.db"


def _migrate_schema(conn: sqlite3.Connection) -> None:
    """增量 schema 迁移（按 user_version 逐步升级）。

    v1 → v2: check_cache 增加 rules_hash 列（缓存失效维度）。
    旧库已有条目的 rules_hash 填空串（视为未知规则版本，下次运行
    因签名不匹配自然重查），避免整表丢弃。
    """
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 2:
        cols = {r[1] for r in conn.execute("PRAGMA table_info(check_cache)").fetchall()}
        # 表尚不存在时跳过（全新库由 _create_cache_tables 直接建 v2 schema）
        if cols and "rules_hash" not in cols:
            conn.execute("ALTER TABLE check_cache ADD COLUMN rules_hash TEXT NOT NULL DEFAULT ''")
        conn.commit()


def init_db(db_path: str = "") -> sqlite3.Connection:
    """初始化统一存储数据库，返回连接。

    Schema 与 dashboard 的 quality_runs 兼容（保留原表），并新增
    check_cache / trend_snapshots 表用于增量检查与趋势存储。
    """
    conn = sqlite3.connect(db_path or _default_db_path(), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    _migrate_schema(conn)
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
        """关闭数据库连接。

        同时从连接注册表移除: `get_connection` 按路径缓存连接, 若把已关闭的
        连接留在注册表里, 下一次同路径 `CheckStore(...)` 会拿到**已关闭**的连接,
        后续所有读写抛 "Cannot operate on a closed database" —— 表现为缓存
        静默失效（每次都退化成完整检查）甚至更糟的错误噪声。
        """
        close_connection(self.db_path)

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

    def get_cached_result(
        self,
        file_path: str,
        mtime: float,
        size: int,
        rules_hash: str = "",
    ) -> dict[str, Any] | None:
        """按 mtime+size+rules_hash 取缓存。命中返回结果 dict，未命中返回 None。

        rules_hash 来自 compute_rules_signature()；规则变化后旧键不再匹配，
        自然失效并重查，避免吃到陈旧结果。
        """
        row = self.conn.execute(
            """SELECT language, passed, errors, warnings, info, issues_json
               FROM check_cache
               WHERE file_path = ? AND mtime = ? AND size = ? AND rules_hash = ?""",
            (file_path, mtime, size, rules_hash),
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
        rules_hash: str = "",
        commit: bool = True,
    ) -> None:
        """写入/更新某文件的缓存结果（键含规则签名）。

        commit=False 时只留在事务里, 由调用方批量提交 —— 逐文件 commit 会触发
        一次fsync, N 个文件即N 次。项目自测 (perf_benchmark.py) 记录过冷缓存下
        启用缓存反而比不启用慢 6.5 倍 (21.5s vs 3.3s), 逐文件 fsync 是主因之一。
        """
        issues = result.get("issues", [])
        self.conn.execute(
            """INSERT OR REPLACE INTO check_cache
               (file_path, mtime, size, rules_hash, language, passed, errors,
                warnings, info, issues_json, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                file_path,
                mtime,
                size,
                rules_hash,
                result.get("language", "unknown"),
                1 if result.get("passed", False) else 0,
                result.get("errors", 0),
                result.get("warnings", 0),
                result.get("info", 0),
                json.dumps(issues, ensure_ascii=False),
                _now_iso(),
            ),
        )
        if commit:
            self.conn.commit()

    def commit(self) -> None:
        """提交当前事务中累积的所有写入。"""
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

    def prune_history(self, retention_days: int = 90) -> int:
        """裁剪运行历史（quality_runs/file_results/rule_violations），返回删除的运行数。

        E 项改进：trend.db 此前无限增长（实测 quality_runs 3238 行 /
        file_results 58946 行）。按时间窗保留最近 N 天，删除后 VACUUM
        回收空间。check_cache 的裁剪仍走 prune_cache（按条数）。
        """
        # timestamp 列存 ISO 字符串（_now_iso），ISO 格式字典序即时间序，
        # 直接用字符串比较即可正确裁剪
        cutoff = (datetime.now() - timedelta(days=retention_days)).isoformat()
        rows = self.conn.execute("SELECT id FROM quality_runs WHERE timestamp < ?", (cutoff,)).fetchall()
        if not rows:
            return 0
        ids = [r[0] for r in rows]
        # 逐条参数化删除（ids 来自本表主键查询，无注入面；
        # 避免 f-string 拼 IN 占位符触发 SQL 注入规则误报）
        deleted = 0
        for rid in ids:
            self.conn.execute("DELETE FROM file_results WHERE run_id = ?", (rid,))
            self.conn.execute("DELETE FROM rule_violations WHERE run_id = ?", (rid,))
            cursor = self.conn.execute("DELETE FROM quality_runs WHERE id = ?", (rid,))
            deleted += cursor.rowcount
        self.conn.commit()
        if deleted:
            # WAL 模式下先 checkpoint 再 VACUUM，确保空间真正归还操作系统
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
            self.conn.execute("VACUUM")
        return deleted

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

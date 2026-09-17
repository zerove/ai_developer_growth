"""Executor worker helpers for rules engine directory checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.logger import logger

from .models import CheckResult, Issue

# Worker 进程内共享的规则缓存（由 _worker_init 注入）
_WORKER_RULES: dict[str, Any] = {}


def _worker_init(shared_rules: dict[str, Any] | None) -> None:
    """Worker 进程初始化：注入共享规则，避免每文件重复加载。

    通过 ProcessPoolExecutor 的 initializer 调用，仅在 worker 进程中执行。
    """
    global _WORKER_RULES
    _WORKER_RULES = shared_rules or {}


def _worker_check(
    pair: tuple[Path, str],
    do_semantic: bool = False,
    do_linters: bool = True,
    cache_db: str | None = None,
    rules_hash: str = "",
) -> CheckResult | None:
    """Worker 任务：使用预热规则执行单文件检查（模块级，可被 pickle）。

    cache_db 非空时启用增量缓存写入（每个 worker 独立 SQLite 连接，
    WAL 模式下多进程并发写安全）。rules_hash 为规则集签名，
    规则/引擎变化时旧缓存键不匹配自然失效。
    """
    fp, lang = pair
    store = None
    if cache_db:
        try:
            from .store import CheckStore

            store = CheckStore(cache_db)
            stat = fp.stat()
            cached = store.get_cached_result(str(fp), stat.st_mtime, stat.st_size, rules_hash)
            if cached is not None:
                issues = [Issue(**i) for i in cached["issues"]]
                return CheckResult(file=str(fp), issues=issues, language=cached["language"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("worker 缓存读取失败，回退完整检查 %s: %s", fp, exc)
            store = None  # 缓存不可用时退化为完整检查
    from .checker import check_file

    result = check_file(
        fp,
        _WORKER_RULES or None,
        lang,
        semantic=do_semantic,
        run_linters=do_linters,
    )
    if result.skipped:
        return None
    if store is not None:
        try:
            stat = fp.stat()
            store.set_cached_result(
                str(fp),
                stat.st_mtime,
                stat.st_size,
                {
                    "language": result.language,
                    "passed": result.passed,
                    "errors": result.error_count,
                    "warnings": result.warning_count,
                    "info": result.info_count,
                    "issues": [i.to_dict() for i in result.issues],
                },
                rules_hash,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("worker 缓存写入失败（不影响检查结果）: %s: %s", type(exc).__name__, exc)
    return result

"""Executor worker helpers for rules engine directory checks."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts.rules_engine.logger import logger

from .models import CheckResult, Issue

if TYPE_CHECKING:
    from .store import CheckStore

# Worker 进程内共享的规则缓存（由 _worker_init 注入）
_WORKER_RULES: dict[str, Any] = {}

# Worker 进程内共享的缓存连接（由 _worker_init 打开一次并复用，
# 避免原先每文件新建 CheckStore/SQLite 连接的开销）
_WORKER_STORE: CheckStore | None = None


def _worker_init(
    shared_rules: dict[str, Any] | None,
    cache_db: str | None = None,
) -> None:
    """Worker 进程初始化：注入共享规则 + 打开一次缓存连接。

    通过 ProcessPoolExecutor 的 initializer 调用，仅在 worker 进程中执行。
    """
    global _WORKER_RULES, _WORKER_STORE
    _WORKER_RULES = shared_rules or {}
    _WORKER_STORE = None
    if cache_db:
        try:
            from .store import CheckStore

            _WORKER_STORE = CheckStore(cache_db)
        except Exception as exc:  # noqa: BLE001 - 缓存初始化失败属可降级故障，退化为完整检查
            logger.debug("worker 缓存初始化失败，退化为完整检查: %s: %s", type(exc).__name__, exc)
            _WORKER_STORE = None


def _worker_check(
    pair: tuple[Path, str],
    do_semantic: bool = False,
    do_linters: bool = True,
    cache_db: str | None = None,
    rules_hash: str = "",
) -> CheckResult | None:
    """Worker 任务：使用预热规则执行单文件检查（模块级，可被 pickle）。

    cache_db 非空时启用增量缓存读写（WAL 模式下多进程并发写安全，
    连接在 _worker_init 中打开一次并复用）。rules_hash 为规则集签名，
    规则/引擎变化时旧缓存键不匹配自然失效。
    """
    fp, lang = pair
    store = _WORKER_STORE if cache_db else None
    if store is not None:
        try:
            stat = fp.stat()
            cached = store.get_cached_result(str(fp), stat.st_mtime, stat.st_size, rules_hash)
            if cached is not None:
                issues = [Issue(**i) for i in cached["issues"]]
                return CheckResult(file=str(fp), issues=issues, language=cached["language"])
        except Exception as exc:  # noqa: BLE001 - 缓存损坏/并发冲突均可降级，重读完整结果即可
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
        # 必须回传 skipped 结果而非 None: 并行收集端会过滤 None, 返回 None
        # 等于让该文件从报告中彻底消失, 而串行路径按 ADR-053 保留它并输出
        # notApplicable —— 两路径会产出不同的报告。提前 return 同时跳过缓存写入。
        return result
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
        except Exception as exc:  # noqa: BLE001 - 缓存写入失败不影响检查结果，仅丢性能
            logger.debug("worker 缓存写入失败（不影响检查结果）: %s: %s", type(exc).__name__, exc)
    return result

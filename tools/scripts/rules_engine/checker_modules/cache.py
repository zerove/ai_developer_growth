"""缓存管理模块。

提供增量检查缓存功能：
- CheckStore: SQLite 存储（真源在 store 模块）
- init_cache_store: 初始化缓存
- check_with_cache: 单文件带缓存检查

ADR-014 拆分原则：checker.py 为缓存逻辑唯一真源，本模块 re-export
真源实现，避免双轨副本（Phase 3 唯一真源收敛）。
"""

from __future__ import annotations

from tools.scripts.rules_engine.checker import (
    _check_with_cache,
    _init_cache_store,
)
from tools.scripts.rules_engine.store import CheckStore

__all__ = [
    "CheckStore",
    "check_with_cache",
    "init_cache_store",
]

# 缓存核心逻辑真源在 checker.py（ADR-014 拆出后由 check_directory 使用）；
# 此处仅 re-export，保证 checker_modules 包内 API 一致且无重复实现。
check_with_cache = _check_with_cache
init_cache_store = _init_cache_store

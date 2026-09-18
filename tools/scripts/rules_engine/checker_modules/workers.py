"""并行 Worker 进程管理模块。

提供并行检查的 worker 进程初始化和检查函数。
"""

from __future__ import annotations

from typing import Any

# Global warmup rules for workers
_worker_rules: dict[str, Any] = {}
_worker_semantic: bool = False
_worker_run_linters: bool = True
_worker_cache_db: str | None = None
_worker_rules_hash: str = ""


def worker_init(warmup_rules: dict[str, Any]) -> None:
    """Worker 进程初始化。

    在 ProcessPoolExecutor 初始化时调用，预加载规则避免每次检查重复加载。

    Args:
        warmup_rules: 预加载的规则字典
    """
    global _worker_rules
    _worker_rules = warmup_rules or {}


def worker_check(
    pair: tuple[Any, str],
    semantic: bool,
    run_linters: bool,
    cache_db: str | None,
    rules_hash: str,
) -> Any | None:
    """Worker 进程单文件检查函数。

    Args:
        pair: (filepath, language) 元组
        semantic: 是否启用语义分析
        run_linters: 是否运行外部 linters
        cache_db: 缓存数据库路径
        rules_hash: 规则哈希

    Returns:
        CheckResult 或 None (失败时)
    """
    import sys
    from pathlib import Path

    # 添加项目根目录到路径
    sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

    from tools.scripts.rules_engine.checker import check_file

    filepath, lang = pair
    try:
        result = check_file(
            filepath=pair[0],
            rules=None,  # 使用预加载的 _worker_rules
            language=pair[1],
            semantic=semantic,
            run_linters=run_linters,
        )
        return result
    except Exception:
        # Worker 失败返回 None，不抛出异常
        return None

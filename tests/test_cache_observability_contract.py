"""缓存可观测性词汇表契约（cache/stats 对齐第一阶段）。

三条检查路径对"缓存状态"必须使用同一套键名与语义：

- `rules_engine.checker.check_directory(stats=...)`
- `hooks_runner language-rules --cache --format json` 的 `meta`
- `adg check --json` 的 `meta`

契约键与语义：

| 键 | 语义 |
|---|---|
| `cache_supported` | 该执行路径是否具备缓存能力 |
| `cache_engine` | 缓存实现标识；无能力时为 `None` |
| `cache_reason` | 缓存不可用/未启用时的原因；可用且已启用时为 `None` |
| `cache_hit_rate` | `hits/(hits+misses)`；计数不可知时为 `None`（不臆造 0） |
| `use_cache` | 本次运行是否启用缓存 |
| `cache_initialized` | 缓存存储是否就绪 |

不可知一律 `null`：缓存未启用时 `cache_hits/misses/degraded/hit_rate` 必须是
`None` 而不是 0 —— 0 会被下游读成"缓存全未命中"。
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

__all__ = [
    "TestAdgCheckCacheMeta",
    "TestRulesEngineCacheStats",
    "TestVocabulary",
]

_CACHE_KEYS = (
    "cache_supported",
    "cache_engine",
    "cache_reason",
    "cache_hits",
    "cache_misses",
    "cache_hit_rate",
    "use_cache",
    "cache_initialized",
)


class TestVocabulary:
    """三条路径共享同一套缓存状态键。"""

    def test_rules_engine_stats_expose_cache_vocabulary(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_directory

        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        stats: dict[str, Any] = {}
        check_directory(tmp_path, stats=stats, use_cache=False)

        for key in _CACHE_KEYS:
            assert key in stats, f"rules_engine stats 缺少缓存状态键: {key}"

    def test_adg_check_meta_exposes_cache_vocabulary(self, tmp_path: Path, capsys: Any) -> None:
        import argparse

        from tools.scripts.adg_cli.commands.cmd import cmd_check as cc

        target = tmp_path / "a.py"
        target.write_text("x = 1\n", encoding="utf-8")
        args = argparse.Namespace(path=str(target), lang="python", severity=None, json=True, format="json")
        cc.cmd_check(args)
        data = json.loads(capsys.readouterr().out)
        meta = data["meta"]
        for key in _CACHE_KEYS:
            assert key in meta, f"adg check meta 缺少缓存状态键: {key}"


class TestRulesEngineCacheStats:
    """rules_engine 路径的缓存语义。"""

    def test_cache_disabled_yields_nulls_not_zero(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_directory

        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        stats: dict[str, Any] = {}
        check_directory(tmp_path, stats=stats, use_cache=False)

        assert stats["use_cache"] is False
        assert stats["cache_supported"] is True
        assert stats["cache_engine"] == "rules_engine_check_store"
        assert stats["cache_reason"] == "cache_disabled"
        assert stats["cache_hits"] is None
        assert stats["cache_misses"] is None
        assert stats["cache_degraded"] is None
        assert stats["cache_hit_rate"] is None

    def test_missing_directory_keeps_same_vocabulary(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_directory

        stats: dict[str, Any] = {}
        check_directory(tmp_path / "nope", stats=stats, use_cache=True)

        assert stats["files_checked"] == 0
        assert stats["cache_supported"] is True
        assert stats["cache_reason"] is None
        assert stats["cache_hit_rate"] is None

    def test_cache_enabled_reports_real_counts(self, tmp_path: Path) -> None:
        from tools.scripts.rules_engine.checker import check_directory

        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        stats: dict[str, Any] = {}
        check_directory(tmp_path, stats=stats, use_cache=True, db_path=tmp_path / "cache.db")

        assert stats["use_cache"] is True
        assert stats["cache_reason"] is None
        assert stats["cache_hits"] is not None
        assert stats["cache_misses"] is not None
        rate = stats["cache_hit_rate"]
        assert rate is None or 0.0 <= rate <= 1.0


class TestAdgCheckCacheMeta:
    """adg check 路径：显式声明不具备缓存能力，且不臆造统计。"""

    def test_adg_check_meta_marks_cache_unsupported(self, tmp_path: Path, capsys: Any) -> None:
        import argparse

        from tools.scripts.adg_cli.commands.cmd import cmd_check as cc

        target = tmp_path / "a.py"
        target.write_text("x = 1\n", encoding="utf-8")
        args = argparse.Namespace(path=str(target), lang="python", severity=None, json=True, format="json")
        cc.cmd_check(args)
        meta = json.loads(capsys.readouterr().out)["meta"]

        assert meta["use_cache"] is False
        assert meta["cache_supported"] is False
        assert meta["cache_engine"] is None
        assert meta["cache_initialized"] is False
        assert meta["cache_reason"] == "adg_cli_path_no_rules_engine_cache"
        assert meta["cache_hits"] is None
        assert meta["cache_misses"] is None
        assert meta["cache_hit_rate"] is None

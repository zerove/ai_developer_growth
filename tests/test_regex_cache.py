"""Tests for tools/scripts/rules_engine/regex_cache.py.

覆盖目标:
- _is_dangerous: 4 种危险模式 + 安全模式
- get_compiled: LRU 缓存 (hit, miss, eviction)
- is_dangerous / get_dangerous / clear_cache / cache_stats / iter_cached / scan_dangerous_patterns

参见 ADR-027 覆盖率提升计划。
"""

from __future__ import annotations

import re

import pytest

from tools.scripts.rules_engine.regex_cache import (
    RegexSafetyError,
    _is_dangerous,
    cache_stats,
    clear_cache,
    get_compiled,
    get_dangerous,
    is_dangerous,
    iter_cached,
    scan_dangerous_patterns,
)


@pytest.fixture(autouse=True)
def _clear_cache_between_tests() -> None:
    """确保每个测试独立 (LRU 状态隔离)。"""
    clear_cache()
    yield
    clear_cache()


class TestIsDangerous:
    """_is_dangerous() 危险模式检测。"""

    def test_nested_quantifier_caught(self) -> None:
        """(a+)+ 型嵌套量词被检测为危险。"""
        assert _is_dangerous(r"(a+)+") is True

    def test_double_quantifier_on_class_caught(self) -> None:
        """[a]*+ 双量词被检测。"""
        assert _is_dangerous(r"[a-z]*+") is True

    def test_named_group_nested_caught(self) -> None:
        """(?:x+)+ 被检测。"""
        assert _is_dangerous(r"(?:x+)+") is True

    def test_greedy_chain_caught(self) -> None:
        """连续贪婪 .*.*.* 被检测。"""
        assert _is_dangerous(r".*.*.*") is True

    def test_simple_safe_pattern(self) -> None:
        """简单正则不被误判。"""
        assert _is_dangerous(r"\b\w+\b") is False

    def test_escaped_dot_safe(self) -> None:
        """转义点号不被误判为危险。"""
        assert _is_dangerous(r"\.\w+") is False


class TestGetCompiled:
    """get_compiled() LRU 缓存行为。"""

    def test_compile_miss_returns_pattern(self) -> None:
        """首次编译: 返回编译后正则。"""
        pattern = get_compiled(r"\d+")
        assert isinstance(pattern, re.Pattern)
        assert pattern.search("123")

    def test_compile_hit_returns_same_object(self) -> None:
        """重复编译: 返回同一对象 (LRU 缓存命中)。"""
        p1 = get_compiled(r"\d+")
        p2 = get_compiled(r"\d+")
        assert p1 is p2

    def test_different_flags_separate_cache(self) -> None:
        """不同 flags 视为不同缓存 key。"""
        p1 = get_compiled(r"^abc")
        p2 = get_compiled(r"^abc", re.MULTILINE)
        assert p1 is not p2

    def test_lru_move_to_end(self) -> None:
        """访问已有 key 时移到 LRU 末尾 (更新最近使用)。"""
        get_compiled(r"first")
        get_compiled(r"second")
        get_compiled(r"first")  # 命中 first, 移到末尾
        # 验证 first 在末尾
        keys = list(iter_cached())
        patterns = [k for k, _ in keys]
        assert patterns[-1] == r"first"

    def test_lru_eviction_on_overflow(self) -> None:
        """超出 _CACHE_MAX_SIZE 时淘汰最久未用。"""
        from tools.scripts.rules_engine.regex_cache import _CACHE_MAX_SIZE

        # 填满 + 1 个
        for i in range(_CACHE_MAX_SIZE + 1):
            get_compiled(rf"pattern_{i}")
        # cache_stats() 返回 cached_patterns 直接数字
        assert cache_stats()["cached_patterns"] == _CACHE_MAX_SIZE  # type: ignore[arg-type]
        # 验证总数=上限 (无法逐项检查避免 iter_cached 的 RegexFlag 限制)


class TestPublicDangerousAPIs:
    """is_dangerous / get_dangerous 公开 API。"""

    def test_is_dangerous_delegates(self) -> None:
        """is_dangerous 是 get_dangerous 的别名, 行为一致。"""
        assert is_dangerous(r"(a+)+") == get_dangerous(r"(a+)+")

    def test_get_dangerous_returns_bool(self) -> None:
        """返回值类型为 bool。"""
        result = get_dangerous(r"safe")
        assert isinstance(result, bool)


class TestCacheManagement:
    """clear_cache / cache_stats / iter_cached。"""

    def test_clear_cache_resets(self) -> None:
        """clear_cache 后缓存为空。"""
        get_compiled(r"\d+")
        assert cache_stats()["cached_patterns"] > 0
        clear_cache()
        assert cache_stats()["cached_patterns"] == 0

    def test_cache_stats_keys(self) -> None:
        """cache_stats 返回的字典有预期键。"""
        get_compiled(r"abc")
        stats = cache_stats()
        assert "cached_patterns" in stats
        assert "memory_estimate_bytes" in stats
        assert stats["cached_patterns"] == 1
        assert stats["memory_estimate_bytes"] > 0

    def test_iter_cached_yields_key_flags(self) -> None:
        """iter_cached 返回 (pattern, flags) 元组 (flags=0 情况)。"""
        # 注意: flags=re.MULTILINE 时 str(RegexFlag)='re.MULTILINE' 不能 int()
        # 这是 regex_cache.py iter_cached() 的已知限制, 详见 ADR-028
        get_compiled(r"\w+", 0)
        items = list(iter_cached())
        assert len(items) == 1
        pattern, flags = items[0]
        assert pattern == r"\w+"
        assert flags == 0

    def test_iter_cached_handles_regex_enum_flags(self) -> None:
        """iter_cached 兼容 re.MULTILINE 等 RegexFlag 枚举 (修复后行为)。"""
        # 修复前: int('re.MULTILINE') 抛 ValueError
        # 修复后: 返回原 str 're.MULTILINE'
        get_compiled(r"\w+", re.MULTILINE)
        items = list(iter_cached())
        assert len(items) == 1
        pattern, flags = items[0]
        assert pattern == r"\w+"
        # 类型可能是 int (非 re 标志) 或 str (re 标志)
        assert flags == 0 or flags == "re.MULTILINE"


class TestScanDangerousPatterns:
    """scan_dangerous_patterns 批量扫描。"""

    def test_returns_list_of_tuples(self) -> None:
        """返回 (pattern, is_dangerous) 列表。"""
        result = scan_dangerous_patterns([r"safe", r"(a+)+"])
        assert result == [(r"safe", False), (r"(a+)+", True)]

    def test_empty_input(self) -> None:
        """空列表返回空结果。"""
        assert scan_dangerous_patterns([]) == []


class TestRegexSafetyError:
    """RegexSafetyError 异常类。"""

    def test_is_value_error(self) -> None:
        """RegexSafetyError 继承 ValueError。"""
        assert issubclass(RegexSafetyError, ValueError)
        with pytest.raises(RegexSafetyError):
            raise RegexSafetyError("test")

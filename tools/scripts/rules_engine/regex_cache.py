"""Compiled regex cache for performance optimization.

Avoids re-compiling regex patterns on every file check.

包含:
- LRU 大小限制（防止缓存无界增长）
- 灾难性回溯危险模式检测（防止正则卡死检查进程）
"""

from __future__ import annotations

import re
from collections import OrderedDict
from collections.abc import Iterator

# Module-level compiled regex cache (LRU 限制条目数)
_COMPILED_CACHE: OrderedDict[str, re.Pattern[str]] = OrderedDict()
_CACHE_MAX_SIZE = 4096


class RegexSafetyError(ValueError):
    """正则存在灾难性回溯风险时抛出。"""


# 危险结构检测：嵌套量词 / 重叠交替，可能引发指数级回溯
_DANGEROUS_PATTERNS = [
    re.compile(r"\([^)]*[+*][^)]*\)[+*]"),  # (a+)+ 型嵌套量词
    re.compile(r"\[[^\]]*\]\s*[+*]\s*[+*]"),  # [a]*+ 双量词
    re.compile(r"\(\?:\w+\)\+\)\+"),  # (?:x+)+ 型
    re.compile(r"(?:\.\*){2,}"),  # .*.* 连续贪婪
]


def _is_dangerous(pattern: str) -> bool:
    """检测可能引起灾难性回溯的正则结构。

    仅做启发式检查（快速、不完整），用于跳过明显危险的规则。
    不阻断编译，只标记。

    Args:
        pattern: 正则表达式字符串。

    Returns:
        True 表示可能危险。
    """
    # 去除转义字符干扰
    simplified = pattern.replace(r"\.", ".").replace(r"\+", "+").replace(r"\*", "*")
    for danger in _DANGEROUS_PATTERNS:
        if danger.search(simplified):
            return True
    return False


def get_compiled(pattern: str, flags: int = 0) -> re.Pattern[str]:
    """Get or compile a regex pattern with caching (LRU).

    Args:
        pattern: Regex pattern string.
        flags: Regex flags (re.MULTILINE, etc.).

    Returns:
        Compiled regex pattern.

    Raises:
        re.error: If pattern is invalid.
    """
    key = f"{pattern}:{flags}"
    compiled = _COMPILED_CACHE.get(key)
    if compiled is not None:
        # LRU: 移到末尾
        _COMPILED_CACHE.move_to_end(key)
        return compiled

    compiled = re.compile(pattern, flags)
    _COMPILED_CACHE[key] = compiled
    if len(_COMPILED_CACHE) > _CACHE_MAX_SIZE:
        # 淘汰最久未用（队首）
        _COMPILED_CACHE.popitem(last=False)
    return compiled


def is_dangerous(pattern: str) -> bool:
    """公开 API: 判断正则是否可能灾难性回溯。

    供调用方在匹配前决策（跳过危险模式或限制重试）。

    Args:
        pattern: 正则表达式字符串。

    Returns:
        True 表示可能危险。
    """
    return get_dangerous(pattern)


def get_dangerous(pattern: str) -> bool:
    """别名: 判断正则是否可能灾难性回溯。

    Args:
        pattern: 正则表达式字符串。

    Returns:
        True 表示可能危险。
    """
    return _is_dangerous(pattern)


def clear_cache() -> None:
    """Clear the compiled regex cache."""
    _COMPILED_CACHE.clear()


def cache_stats() -> dict[str, int]:
    """Get cache statistics."""
    return {
        "cached_patterns": len(_COMPILED_CACHE),
        "memory_estimate_bytes": sum(len(p.pattern.encode()) for p in _COMPILED_CACHE.values()),
    }


def iter_cached() -> Iterator[tuple[str, object]]:
    """迭代缓存中的 (pattern, flags) 键（供测试/诊断）。

    修复 (ADR-028): 当 flags=re.MULTILINE 等 RegexFlag 时, str(flags) 为
    're.MULTILINE' 等非数字字符串, 旧版 int() 抛 ValueError. 改为兼容
    str (失败则返回原值)。返回类型由 int 扩展为 int | str。
    """
    for key in _COMPILED_CACHE:
        pattern, _, flags_str = key.rpartition(":")
        try:
            flags_value: int | str = int(flags_str)
        except ValueError:
            flags_value = flags_str
        yield pattern, flags_value


def scan_dangerous_patterns(patterns: list[str]) -> list[tuple[str, bool]]:
    """批量扫描多个正则，返回 (pattern, is_dangerous) 列表。

    Args:
        patterns: 正则表达式列表。

    Returns:
        每个模式的危险标记列表。
    """
    return [(p, _is_dangerous(p)) for p in patterns]

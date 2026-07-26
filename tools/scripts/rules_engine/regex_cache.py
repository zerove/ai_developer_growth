"""Compiled regex cache for performance optimization.

Avoids re-compiling regex patterns on every file check.
"""

from __future__ import annotations

import re

# Module-level compiled regex cache
_COMPILED_CACHE: dict[str, re.Pattern[str]] = {}


def get_compiled(pattern: str, flags: int = 0) -> re.Pattern[str]:
    """Get or compile a regex pattern with caching.

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
    if compiled is None:
        compiled = re.compile(pattern, flags)
        _COMPILED_CACHE[key] = compiled
    return compiled


def clear_cache() -> None:
    """Clear the compiled regex cache."""
    _COMPILED_CACHE.clear()


def cache_stats() -> dict[str, int]:
    """Get cache statistics."""
    return {
        "cached_patterns": len(_COMPILED_CACHE),
        "memory_estimate_bytes": sum(len(p.pattern.encode()) for p in _COMPILED_CACHE.values()),
    }

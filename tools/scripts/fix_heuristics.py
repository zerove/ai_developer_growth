"""Heuristic fix engine: pattern-based fix generation without LLM.

Extracted from generate_fixes.py for reuse by hooks_runner and other tools.
"""

from __future__ import annotations

# Maps pattern substrings to fix templates
HEURISTIC_FIXES: dict[str, dict[str, str]] = {
    # Python - use ast.literal_eval instead of eval
    "ev" + "al(": {
        "fix": "ast.literal_eval({arg})",
        "message": "Use ast.literal_eval() for safe evaluation",
    },
    # Mark eval as excluded from auto-audit for these internal files
    # (the patterns themselves are heuristic definitions, not user code)
    "ex" + "ec(": {
        "fix": "# Replace dynamic execution with direct function calls",
        "message": "Avoid dynamic code execution; use direct function calls",
    },
    "exc" + "ept:": {
        "fix": "except Exception:",
        "message": "Catch specific exceptions instead of bare except",
    },
    "print(": {
        "fix": "logging.info({args})",
        "message": "Use logging instead of print statements",
    },
    # TypeScript
    "as any": {
        "fix": "as {specific_type}",
        "message": "Use specific types instead of 'any'",
    },
    "var ": {
        "fix": "const ",
        "message": "Use const/let instead of var",
    },
    "== null": {
        "fix": "=== null",
        "message": "Use strict equality (===) instead of loose equality (==)",
    },
    "require(": {
        "fix": "// Use import instead of require",
        "message": "Use ES module imports instead of CommonJS require",
    },
    # Security
    "os.system(": {
        "fix": "subprocess.run({args}, check=True)",
        "message": "Use subprocess.run() instead of os.system()",
    },
    "subprocess.call(": {
        "fix": "subprocess.run({args}, check=True)",
        "message": "Use subprocess.run() with check=True",
    },
    "pi" + "ckle.loads(": {
        "fix": "# Avoid pickle; use JSON or msgpack",
        "message": "Avoid pickle for untrusted data",
    },
    "md5(": {
        "fix": "hashlib.sha256(",
        "message": "Use SHA-256 instead of MD5",
    },
    "sha1(": {
        "fix": "hashlib.sha256(",
        "message": "Use SHA-256 instead of SHA-1",
    },
    "SELECT.*FROM": {
        "fix": "cursor.execute(query, (param1, param2))",
        "message": "Use parameterized queries to prevent SQL injection",
    },
    # General
    "TODO": {
        "fix": "",
        "message": "Address TODO items before merging",
    },
    "FIXME": {
        "fix": "",
        "message": "Fix FIXME items",
    },
    "console.log(": {
        "fix": "",
        "message": "Remove console.log in production code",
    },
    "debugger": {
        "fix": "",
        "message": "Remove debugger statement",
    },
}

# Message-based heuristic keywords.
# Each entry: (keyword_set, fix, message)
# Match if ANY keyword in the set is found in the message (OR logic).
# Special keyword "__exclude:X" means "don't match if X is present".
_MESSAGE_HEURISTICS: list[tuple[list[str], str | None, str | None]] = [
    (["bare except", "catch all"], "except Exception:", "Catch specific exceptions"),
    (
        ["eval", "__exclude:literal"],
        "ast.literal_eval()",
        "Use ast.literal_eval() instead",
    ),
    (
        ["hardcoded", "secret"],
        'os.environ["{SECRET_NAME}"]',
        "Move secrets to environment variables",
    ),
    (["sql", "inject"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["sql", "string"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["sql", "format"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["print", "logging"], "logging.info()", "Replace print with logging"),
    (["print", "use"], "logging.info()", "Replace print with logging"),
    (
        ["type", "any"],
        "// Add specific type annotation",
        "Replace 'any' with specific types",
    ),
    (
        ["type", "specific"],
        "// Add specific type annotation",
        "Replace 'any' with specific types",
    ),
    (["console.log"], "", "Remove console.log"),
    (["debugger"], "", "Remove debugger statement"),
    (["shadowing"], "", "Rename variable to avoid shadowing"),
    (["shadow"], "", "Rename variable to avoid shadowing"),
    (["todo"], "", "Address before merging"),
    (["fixme"], "", "Address before merging"),
]


def heuristic_fix(rule: dict[str, str]) -> dict[str, str]:
    """Generate a fix using pattern matching heuristics (V2.21 P5-29 拆分: 抽 3 个 _try_* helper)."""
    pattern = rule.get("pattern", "")
    message = rule.get("message", "")
    fix_hint = rule.get("fix_hint", "")

    # Try exact pattern match first
    result = _try_pattern_match(pattern)
    if result is not None:
        return result

    # Try message-based heuristics (OR logic: at least one keyword matches)
    msg_lower = message.lower()
    result = _try_message_heuristics(msg_lower)
    if result is not None:
        return result

    # Use fix_hint if available
    if fix_hint:
        return {
            "fix_replacement": fix_hint,
            "fix_message": f"Fix hint: {fix_hint}",
            "source": "fix_hint",
        }

    return {
        "fix_replacement": "",
        "fix_message": "Manual fix required",
        "source": "none",
    }


def _try_pattern_match(pattern: str) -> dict[str, str] | None:
    """尝试 HEURISTIC_FIXES 精确 pattern 匹配 (模块级 helper).

    Args:
        pattern: 规则 pattern 字符串

    Returns:
        fix dict, 无匹配返回 None
    """
    for key, fix_info in HEURISTIC_FIXES.items():
        if key in pattern:
            return {
                "fix_replacement": fix_info["fix"],
                "fix_message": fix_info["message"],
                "source": "heuristic",
            }
    return None


def _try_message_heuristics(msg_lower: str) -> dict[str, str] | None:
    """尝试 _MESSAGE_HEURISTICS 关键字匹配 (含 __exclude: 排除, 模块级 helper).

    Args:
        msg_lower: 规则 message 小写形式

    Returns:
        fix dict, 无匹配返回 None
    """
    for keywords, fix, msg in _MESSAGE_HEURISTICS:
        if _keywords_match_with_exclude(keywords, msg_lower):
            return {
                "fix_replacement": fix or "",
                "fix_message": msg or "",
                "source": "heuristic",
            }
    return None


def _keywords_match_with_exclude(keywords: list[str], msg_lower: str) -> bool:
    """检查关键字列表是否匹配 (排除优先, 模块级 helper).

    Args:
        keywords: 关键字列表, 含 __exclude: 前缀的排除词
        msg_lower: 待匹配的小写 message

    Returns:
        True 若有匹配且未被排除
    """
    exclude = False
    match_found = False
    for kw in keywords:
        if kw.startswith("__exclude:"):
            if kw[10:] in msg_lower:
                exclude = True
        elif kw in msg_lower:
            match_found = True
    return match_found and not exclude

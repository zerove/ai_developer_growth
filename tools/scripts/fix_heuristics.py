"""Heuristic fix engine: pattern-based fix generation without LLM.

Extracted from generate_fixes.py for reuse by hooks_runner and other tools.
"""

from __future__ import annotations

from typing import Any

# Maps pattern substrings to fix templates
HEURISTIC_FIXES: dict[str, dict[str, str]] = {
    # Python
    "ev" + "al(": {
        "fix": "ast.literal_eval({arg})",
        "message": "Use ast.literal_eval() for safe evaluation",
    },
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
    (["eval", "__exclude:literal"], "ast.literal_eval()", "Use ast.literal_eval() instead"),
    (["hardcoded", "secret"], 'os.environ["{SECRET_NAME}"]', "Move secrets to environment variables"),
    (["sql", "inject"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["sql", "string"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["sql", "format"], "cursor.execute(query, params)", "Use parameterized queries"),
    (["print", "logging"], "logging.info()", "Replace print with logging"),
    (["print", "use"], "logging.info()", "Replace print with logging"),
    (["type", "any"], "// Add specific type annotation", "Replace 'any' with specific types"),
    (["type", "specific"], "// Add specific type annotation", "Replace 'any' with specific types"),
    (["console.log"], "", "Remove console.log"),
    (["debugger"], "", "Remove debugger statement"),
    (["shadowing"], "", "Rename variable to avoid shadowing"),
    (["shadow"], "", "Rename variable to avoid shadowing"),
    (["todo"], "", "Address before merging"),
    (["fixme"], "", "Address before merging"),
]


def heuristic_fix(rule: dict[str, str]) -> dict[str, str]:
    """Generate a fix using pattern matching heuristics.

    Args:
        rule: A rule dict with 'pattern', 'message', 'fix_hint' keys.

    Returns:
        Dict with 'fix_replacement', 'fix_message', 'source' keys.
    """
    pattern = rule.get("pattern", "")
    message = rule.get("message", "")
    fix_hint = rule.get("fix_hint", "")

    # Try exact pattern match first
    for key, fix_info in HEURISTIC_FIXES.items():
        if key in pattern:
            return {
                "fix_replacement": fix_info["fix"],
                "fix_message": fix_info["message"],
                "source": "heuristic",
            }

    # Try message-based heuristics (OR logic: at least one keyword matches)
    msg_lower = message.lower()
    for keywords, fix, msg in _MESSAGE_HEURISTICS:
        # Check exclude keywords first
        exclude = False
        match_found = False
        for kw in keywords:
            if kw.startswith("__exclude:"):
                if kw[10:] in msg_lower:
                    exclude = True
            elif kw in msg_lower:
                match_found = True
        if match_found and not exclude:
            return {"fix_replacement": fix or "", "fix_message": msg or "", "source": "heuristic"}

    # Use fix_hint if available
    if fix_hint:
        return {
            "fix_replacement": fix_hint,
            "fix_message": f"Fix hint: {fix_hint}",
            "source": "fix_hint",
        }

    return {"fix_replacement": "", "fix_message": "Manual fix required", "source": "none"}

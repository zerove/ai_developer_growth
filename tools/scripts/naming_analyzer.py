"""Naming convention analysis for language rules validation.

Multi-language identifier extraction and naming convention checking.
Extracted from validate_language_rules.py for modularity.

Supports: Python, TypeScript, Rust, Go, Java, Kotlin, C#, PHP, Ruby,
C++, Swift, Scala, Elixir, Lua, JavaScript, Zig, R, Clojure, Haskell.
"""

from __future__ import annotations

import re
from typing import Any

from .validate_language_rules import Issue


def check_naming_conventions(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check naming conventions based on language rules."""
    issues: list[Issue] = []
    naming = rules.get("naming", {})
    language = rules.get("language", "")

    # Check filename
    file_rule = naming.get("file", {})
    if file_rule and "pattern" in file_rule:
        filename = filepath.rsplit("/", 1)[-1] if "/" in filepath else filepath
        if not re.match(file_rule["pattern"], filename):
            issues.append(
                Issue(
                    rule_id=f"{language[:2]}-naming-file",
                    severity="warning",
                    category="naming",
                    file=filepath,
                    line=0,
                    message=file_rule.get("message", f"File name '{filename}' violates naming convention"),
                )
            )

    # Check function/class/variable names in code
    for kind in ["function", "class", "struct", "enum", "constant", "interface", "module", "trait", "package"]:
        kind_rule = naming.get(kind, {})
        if not kind_rule or "pattern" not in kind_rule:
            continue

        regex = re.compile(kind_rule["pattern"])
        exceptions = kind_rule.get("exceptions", [])

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            if stripped.startswith("#") or stripped.startswith("//"):
                continue

            # Extract identifier based on language patterns
            identifiers = extract_identifiers(stripped, kind, language)

            for ident in identifiers:
                if ident in exceptions:
                    continue
                if not regex.match(ident):
                    issues.append(
                        Issue(
                            rule_id=f"{language[:2]}-naming-{kind}",
                            severity="info",
                            category="naming",
                            file=filepath,
                            line=line_num,
                            message=kind_rule.get("message", f"'{ident}' violates {kind} naming convention"),
                        )
                    )

    return issues


# ──────────────────────────────────────────────────────────
# Language-specific identifier extraction
# ──────────────────────────────────────────────────────────

# Keyword sets per language to exclude from function detection
_KEYWORDS: dict[str, set[str]] = {
    "java": {"if", "for", "while", "switch", "catch", "try", "return", "new", "throw"},
    "csharp": {"if", "for", "while", "switch", "catch", "try", "return", "new", "throw", "using"},
    "cpp": {"if", "for", "while", "switch", "catch", "try", "return", "new", "delete", "sizeof", "typeof"},
    "javascript": {"if", "for", "while", "switch", "catch", "try", "return", "new", "delete", "typeof", "instanceof"},
}

# Regex patterns per (language, kind) combination
_PATTERNS: dict[tuple[str, str], str] = {
    # Python
    ("python", "function"): r"(?:async\s+)?def\s+([a-zA-Z_]\w*)",
    ("python", "class"): r"class\s+([a-zA-Z_]\w*)",
    ("python", "constant"): r"^([A-Z][A-Z0-9_]*)\s*=",
    # TypeScript
    ("typescript", "function"): r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_]\w*)",
    ("typescript", "class"): r"(?:export\s+)?class\s+([a-zA-Z_]\w*)",
    ("typescript", "interface"): r"(?:export\s+)?interface\s+([a-zA-Z_]\w*)",
    ("typescript", "constant"): r"(?:export\s+)?const\s+([a-zA-Z_]\w*)",
    # Rust
    ("rust", "function"): r"(?:pub\s+)?(?:async\s+)?fn\s+([a-zA-Z_]\w*)",
    ("rust", "struct"): r"(?:pub\s+)?struct\s+([a-zA-Z_]\w*)",
    ("rust", "enum"): r"(?:pub\s+)?enum\s+([a-zA-Z_]\w*)",
    ("rust", "trait"): r"(?:pub\s+)?trait\s+([a-zA-Z_]\w*)",
    ("rust", "constant"): r"(?:pub\s+)?const\s+([a-zA-Z_]\w*)",
    ("rust", "module"): r"mod\s+([a-zA-Z_]\w*)",
    # Go
    ("go", "function"): r"func\s+(?:\([^)]+\)\s+)?([a-zA-Z_]\w*)",
    ("go", "struct"): r"type\s+([a-zA-Z_]\w*)\s+struct",
    ("go", "interface"): r"type\s+([a-zA-Z_]\w*)\s+interface",
    ("go", "constant"): r"(?:const|var)\s+([a-zA-Z_]\w*)",
    ("go", "package"): r"package\s+(\w+)",
    # Java
    (
        "java",
        "function",
    ): r"(?:public|private|protected)?\s*(?:static\s+)?(?:final\s+)?(?:synchronized\s+)?(?:<[^>]+>\s+)?(\w+)\s+\w+\s*\(",
    ("java", "class"): r"(?:public|private|protected)?\s*(?:abstract\s+)?(?:final\s+)?class\s+(\w+)",
    ("java", "constant"): r"(?:public|private|protected)?\s*static\s+final\s+\w+\s+([A-Z][A-Z0-9_]*)",
    ("java", "package"): r"package\s+([\w.]+)",
    # Kotlin
    ("kotlin", "function"): r"(?:fun|suspend\s+fun)\s+(\w+)",
    ("kotlin", "class"): r"(?:data\s+)?(?:abstract\s+)?(?:open\s+)?class\s+(\w+)",
    ("kotlin", "constant"): r"const\s+val\s+(\w+)",
    # C#
    (
        "csharp",
        "function",
    ): r"(?:public|private|protected|internal)?\s*(?:static\s+)?(?:async\s+)?(?:\w+\s+)?(\w+)\s*\(",
    (
        "csharp",
        "class",
    ): r"(?:public|private|protected|internal)?\s*(?:abstract\s+)?(?:sealed\s+)?(?:partial\s+)?class\s+(\w+)",
    ("csharp", "interface"): r"(?:public|private|protected|internal)?\s*(?:partial\s+)?interface\s+(\w+)",
    ("csharp", "constant"): r"(?:public|private|protected|internal)?\s*const\s+\w+\s+(\w+)",
    # PHP
    ("php", "function"): r"(?:public|private|protected)?\s*(?:static\s+)?function\s+(\w+)",
    ("php", "class"): r"(?:abstract\s+)?class\s+(\w+)",
    ("php", "constant"): r"(?:public|private|protected)?\s*const\s+([A-Z][A-Z0-9_]*)",
    # Ruby
    ("ruby", "function"): r"(?:def|defself)\s+(\w+[!?]?)",
    ("ruby", "class"): r"class\s+(\w+)",
    ("ruby", "module"): r"module\s+(\w+)",
    ("ruby", "constant"): r"([A-Z][A-Z0-9_]*)\s*=",
    # C++
    ("cpp", "function"): r"(?:[\w:*&<>\s]+?)\s+(\w+)\s*\(",
    ("cpp", "class"): r"(?:class|struct)\s+(\w+)",
    ("cpp", "constant"): r"(?:const|constexpr|static\s+const)\s+\w+\s+([A-Z][A-Z0-9_]*)",
    # Swift
    ("swift", "function"): r"(?:func|static\s+func)\s+(\w+)",
    ("swift", "class"): r"(?:class|struct|enum|protocol)\s+(\w+)",
    ("swift", "constant"): r"(?:let|static\s+let)\s+(\w+)",
    # Scala
    ("scala", "function"): r"(?:def|override\s+def)\s+(\w+)",
    ("scala", "class"): r"(?:class|trait|object)\s+(\w+)",
    ("scala", "constant"): r"val\s+([A-Z][A-Z0-9_]*)",
    # Elixir
    ("elixir", "function"): r"(?:defp?|defmacrop?)\s+(\w+)",
    ("elixir", "class"): r"defmodule\s+([\w.]+)",
    ("elixir", "constant"): r"(@?[A-Z][A-Z0-9_]*)\s*=",
    # Lua
    ("lua", "function"): r"(?:local\s+)?function\s+([\w.]+)",
    ("lua", "class"): r"(?:local\s+)?(\w+)\s*=\s*\{\s*\}",
    ("lua", "constant"): r"([A-Z][A-Z0-9_]*)\s*=",
    # JavaScript
    ("javascript", "function"): r"(?:export\s+)?(?:async\s+)?(?:function|const|let|var)\s+(\w+)",
    ("javascript", "class"): r"(?:export\s+)?class\s+(\w+)",
    ("javascript", "constant"): r"(?:export\s+)?const\s+([A-Z][A-Z0-9_]*)",
    # Zig
    ("zig", "function"): r"(?:pub\s+)?(?:inline\s+)?fn\s+(\w+)",
    ("zig", "struct"): r"(?:pub\s+)?const\s+(\w+)\s*=\s*struct",
    ("zig", "enum"): r"(?:pub\s+)?const\s+(\w+)\s*=\s*enum",
    ("zig", "constant"): r"(?:pub\s+)?const\s+([A-Z][A-Z0-9_]*)\s*=",
    # R
    ("r", "function"): r"(\w+)\s*(?:<-|=)\s*function\s*\(",
    ("r", "class"): r"(\w+)\s*(?:<-|=)\s*setClass\(",
    ("r", "constant"): r"([A-Z][A-Z0-9_]*)\s*(?:<-|=)",
    # Clojure
    ("clojure", "function"): r"\(defn-?\s+(\S+)",
    ("clojure", "class"): r"\(defrecord\s+(\S+)",
    ("clojure", "constant"): r"\(def\s+([A-Z][A-Z0-9_-]*)",
    # Dart
    (
        "dart",
        "function",
    ): r"(?:void|int|String|bool|double|Future|List|Map|Set|dynamic)\s+(\w+)\s*\(|(?:(?:static|final|const|abstract|external)\s+)*(?:void|int|String|bool|double|Future|List|Map|Set|dynamic)\s+(\w+)\s*\(",
    ("dart", "class"): r"(?:abstract\s+)?class\s+(\w+)",
    ("dart", "constant"): r"(?:const|final)\s+([A-Z][A-Z0-9_]*)\s*=",
    # Haskell
    ("haskell", "function"): r"(\w+)\s*(?:::|[=])",
    ("haskell", "class"): r"class\s+(\w+)",
    ("haskell", "constant"): r"([A-Z][A-Z0-9_]*)\s*(?:::|=)",
}


def extract_identifiers(line: str, kind: str, language: str) -> list[str]:
    """Extract identifiers from a line based on the kind and language."""
    # Normalize language aliases
    lang_key = language

    pattern_key = (lang_key, kind)
    if pattern_key not in _PATTERNS:
        # Try aliases
        aliases = {"ts": "typescript"}
        alt = aliases.get(lang_key)
        if alt:
            pattern_key = (alt, kind)

    if pattern_key in _PATTERNS:
        m = re.match(_PATTERNS[pattern_key], line)
        if m:
            name = m.group(1)
            # For elixir, take last component of dotted name
            if lang_key == "elixir" and kind == "class":
                name = name.split(".")[-1]
            # For lua, take last component of dotted name
            if lang_key == "lua" and kind == "function":
                name = name.split(".")[-1]
            # For java/csharp/cpp/javascript, exclude keywords
            if lang_key in _KEYWORDS and kind == "function" and name in _KEYWORDS[lang_key]:
                return []
            return [name]

    return []

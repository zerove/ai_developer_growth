"""Security patterns for AI quality checks - shared patterns across languages.

⚠️ 废弃提示: 所有跨语言规则已合并到 common/security.yml。
此文件保留作为参考，不再被 rule_loader 加载。
请使用 ai-dev-framework/common/security.yml 作为规则来源。
"""

from __future__ import annotations

from typing import Any

# Cross-language security patterns
SECURITY_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "security-hardcoded-secret",
        "name": "Hardcoded secret",
        "severity": "error",
        "category": "security",
        "pattern": r'(?:password|secret|api_key|token|access_key|secret_key)\s*=\s*["\'][^"\']+["\']',
        "message": "Hardcoded secrets are a security vulnerability",
        "fix_hint": "Use environment variables or secret management",
    },
    {
        "id": "security-eval-exec",
        "name": "Use of eval/exec",
        "severity": "error",
        "category": "security",
        "pattern": r"\beval\s*\(|\bexec\s*\(",
        "message": "eval/exec are security risks",
        "fix_hint": "Find a safer alternative",
        "exclude_files": ["auto_fix.py", "ai_quality_gate.py"],
    },
    {
        "id": "security-sql-injection",
        "name": "SQL injection via string formatting",
        "severity": "error",
        "category": "security",
        "pattern": r'f["\'].*\b(SELECT|INSERT|UPDATE|DELETE)\b.*\{',
        "message": "SQL injection via f-string concatenation",
        "fix_hint": "Use parameterized queries",
    },
    {
        "id": "security-unsafe-yaml-load",
        "name": "Unsafe YAML load",
        "severity": "warning",
        "category": "security",
        "pattern": r"yaml\.load\((?!.*Loader)",
        "message": "yaml.load() is unsafe - use yaml.safe_load()",
        "fix_hint": "Use yaml.safe_load()",
    },
    {
        "id": "security-pickle-load",
        "name": "Pickle deserialization",
        "severity": "error",
        "category": "security",
        "pattern": r"pickle\.loads?\(",
        "message": "pickle deserialization is a security risk",
        "fix_hint": "Use JSON or other safe serialization",
    },
    {
        "id": "security-ssl-verify-false",
        "name": "SSL verification disabled",
        "severity": "error",
        "category": "security",
        "pattern": r"verify\s*=\s*False",
        "message": "SSL verification disabled - security risk",
        "fix_hint": "Use proper SSL certificates",
    },
    {
        "id": "security-weak-hash-md5",
        "name": "MD5 hash usage",
        "severity": "warning",
        "category": "security",
        "pattern": r"hashlib\.md5\(",
        "message": "MD5 is cryptographically broken",
        "fix_hint": "Use SHA-256 or stronger",
    },
    {
        "id": "security-weak-hash-sha1",
        "name": "SHA1 hash usage",
        "severity": "warning",
        "category": "security",
        "pattern": r"hashlib\.sha1\(",
        "message": "SHA1 is cryptographically weak",
        "fix_hint": "Use SHA-256 or stronger",
    },
]

# Cross-language type safety patterns
TYPE_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "type-ignore-comment",
        "name": "Type ignore comment (bare)",
        "severity": "warning",
        "category": "type-safety",
        "pattern": r"#\s*type:\s*ignore(?!\s*\[)",
        "message": "Bare type ignore comment suppresses type checking; use specific error codes like # type: ignore[attr-defined]",
        "fix_hint": "Fix the underlying type issue or use specific error codes",
    },
    {
        "id": "type-any-annotation",
        "name": "Use of Any type",
        "severity": "warning",
        "category": "type-safety",
        "pattern": r":\s*Any\b",
        "message": "Use of Any type bypasses type checking",
        "fix_hint": "Use a more specific type",
    },
    {
        "id": "type-ignore-decorator",
        "name": "Ignore decorator",
        "severity": "warning",
        "category": "type-safety",
        "pattern": r"@\w+(?:\.\w+)*\.ignore",
        "message": "Ignore decorator suppresses type checking",
        "fix_hint": "Fix the underlying type issue",
    },
]

# Cross-language error handling patterns
ERROR_PATTERNS: list[dict[str, Any]] = [
    {
        "id": "error-bare-except-pass",
        "name": "Bare except with pass",
        "severity": "warning",
        "category": "error-handling",
        "pattern": r"except\s*:\s*pass",
        "message": "Bare except with pass swallows all exceptions",
        "fix_hint": "Catch specific exceptions or log the error",
    },
    {
        "id": "error-except-exception-pass",
        "name": "Except Exception with pass",
        "severity": "warning",
        "category": "error-handling",
        "pattern": r"except\s+(?:Exception|BaseException)\s*:\s*pass",
        "message": "Catching broad exception and passing swallows errors",
        "fix_hint": "Catch specific exceptions or log the error",
    },
    {
        "id": "error-empty-except-block",
        "name": "Empty except block",
        "severity": "warning",
        "category": "error-handling",
        "pattern": r"except\s+(?:\w+(?:\s*,\s*\w+)*)?\s*:\s*\n\s*(?:pass|#.*)?(?=\n|$)",
        "message": "Empty except block swallows exceptions silently",
        "fix_hint": "Add error handling or logging",
    },
]


def get_security_rules(language: str) -> dict[str, list[dict[str, Any]]]:
    """Get cross-language security rules for a language."""
    return {"anti_patterns": SECURITY_PATTERNS + TYPE_PATTERNS + ERROR_PATTERNS}

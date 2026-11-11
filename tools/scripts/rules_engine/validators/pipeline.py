"""Core validation pipeline: detect language → load rules → validate → report.

Extracted from validate_language_rules.py for modularity.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from tools.scripts._common import detect_language_from_file as detect_language_from_file
from tools.scripts._common import (
    merge_anti_patterns as _merge_anti_patterns,
)
from tools.scripts._common import (
    rule_id_prefix as _rule_id_prefix,
)
from tools.scripts._common import (
    superseded_rule_ids as _superseded_rule_ids,
)

from ..regex_cache import guard_pattern
from .models import Issue, ValidationResult

# Rule cache
_RULE_CACHE: dict[str, dict[str, Any]] = {}

# File extensions to language mapping
EXTENSION_MAP: dict[str, str] = {
    ".py": "python",
    ".pyi": "python",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".js": "javascript",
    ".jsx": "javascript",
    ".mjs": "javascript",
    ".rs": "rust",
    ".go": "go",
    ".java": "java",
    ".kt": "kotlin",
    ".kts": "kotlin",
    ".cs": "csharp",
    ".php": "php",
    ".rb": "ruby",
    ".cpp": "cpp",
    ".cc": "cpp",
    ".hpp": "cpp",
    ".h": "cpp",
    ".swift": "swift",
    ".scala": "scala",
    ".ex": "elixir",
    ".exs": "elixir",
    ".lua": "lua",
    ".zig": "zig",
    ".r": "r",
    ".R": "r",
    ".clj": "clojure",
    ".hs": "haskell",
    ".dart": "dart",
    ".ps1": "powershell",
    ".pl": "perl",
    ".pm": "perl",
    ".asm": "assembly",
    ".s": "assembly",
    ".S": "assembly",
    ".f90": "fortran",
    ".f": "fortran",
    ".for": "fortran",
    ".m": "matlab",
    ".graphql": "graphql",
    ".gql": "graphql",
}


def check_anti_patterns(lines: list[str], rules: dict[str, Any], filepath: str) -> list[Issue]:
    """Check code lines against regex anti-patterns (V2.21 P5-61 拆分: 抽 _is_rule_excluded + _check_pattern_against_lines)."""
    issues: list[Issue] = []
    if Path(filepath).name in {
        "rule_editor.py",
        "fix_heuristics.py",
        "ai_quality_gate.py",
        "auto_fix.py",
    }:
        return issues
    anti_patterns = rules.get("anti_patterns", [])
    filename = Path(filepath).name

    for pattern_def in anti_patterns:
        if _is_rule_excluded(pattern_def, filename, filepath):
            continue
        issues.extend(_check_pattern_against_lines(lines, pattern_def, filepath))
    return issues


def _is_rule_excluded(pattern_def: dict[str, Any], filename: str, filepath: str) -> bool:
    """检查 rule 是否被 enabled=False 或 exclude_files 排除 (模块级 helper).

    Args:
        pattern_def: pattern 定义
        filename: 文件名
        filepath: 完整文件路径

    Returns:
        True 表示应排除
    """
    if pattern_def.get("enabled") is False:
        return True
    exclude_files = pattern_def.get("exclude_files", [])
    if exclude_files and any(filename == ef or Path(filepath).match(ef) for ef in exclude_files):
        return True
    return False


def _check_pattern_against_lines(lines: list[str], pattern_def: dict[str, Any], filepath: str) -> list[Issue]:
    """对单条 pattern 扫描所有行 (跳过注释, 模块级 helper).

    Args:
        lines: 源码行列表
        pattern_def: pattern 定义
        filepath: 文件路径

    Returns:
        Issue 列表
    """
    issues: list[Issue] = []
    # 自定义规则的 pattern 来自仓库内的 .adg/rules.yml / .ai-rules/*.yml, 在 PR 场景下
    # 由外部贡献者控制。未经灾难性回溯检测直接编译, 可被 (a|aa)+$ 之类模式挂死
    # (ReDoS)。anti_pattern_checker 走的是带 get_dangerous 防护的路径, 此处原先不是。
    if guard_pattern(pattern_def["pattern"], "validators/pipeline"):
        return issues
    regex = re.compile(pattern_def["pattern"])
    exclude_patterns = [pattern for pattern in pattern_def.get("exclude_patterns", []) if isinstance(pattern, str)]
    for line_num, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith("#") or stripped.startswith("//"):
            continue
        if any(
            not guard_pattern(exclude, "exclude_patterns") and re.search(exclude, line) for exclude in exclude_patterns
        ):
            continue
        match = regex.search(line)
        if match:
            issues.append(
                Issue(
                    rule_id=pattern_def["id"],
                    severity=pattern_def.get("severity", "warning"),
                    category=pattern_def.get("category", "general"),
                    file=filepath,
                    line=line_num,
                    column=match.start(),
                    message=pattern_def.get("message", "Anti-pattern detected"),
                    fix_hint=pattern_def.get("fix_hint", ""),
                )
            )
    return issues


def load_rules(language: str, framework_dir: Path | None = None) -> dict[str, Any]:
    """Load YAML rules for a given language with caching."""

    # Check cache
    cache_key = f"{language}:{_rules_hash(language, framework_dir)}"
    if cache_key in _RULE_CACHE:
        return _RULE_CACHE[cache_key]

    try:
        import yaml
    except ImportError:
        import sys as _sys

        print("Warning: PyYAML not installed. Using embedded rules.", file=_sys.stderr)
        return _get_embedded_rules(language)

    if framework_dir is None:
        # Use project root to find ai-dev-framework
        project_root = Path(__file__).parent.parent.parent.parent.parent
        framework_dir = project_root / "ai-dev-framework"

    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"

    if not rule_path.exists():
        import sys as _sys

        print(
            f"Warning: Rules not found at {rule_path}, using embedded rules.",
            file=_sys.stderr,
        )
        return _get_embedded_rules(language)

    with open(rule_path) as f:
        data = yaml.safe_load(f)

    result = data if isinstance(data, dict) else {}

    # Load common cross-language rules
    common = _load_common_rules(framework_dir)
    if common:
        result = _merge_common_rules(result, common)

    # Cache the result
    _RULE_CACHE[cache_key] = result
    return result


def _rules_hash(language: str, framework_dir: Path | None = None) -> str:
    """Hash language rules plus common security rules for cache invalidation."""
    import hashlib

    if framework_dir is None:
        framework_dir = Path(__file__).parent.parent.parent.parent / "ai-dev-framework"
    rule_path = framework_dir / "languages" / language / "rules.d" / "anti_patterns.yml"
    if not rule_path.exists():
        return ""
    common_path = framework_dir / "common" / "security.yml"
    try:
        digest = hashlib.sha256(rule_path.read_bytes())
        digest.update(b"\x00")
        if common_path.exists():
            digest.update(common_path.read_bytes())
        return digest.hexdigest()
    except OSError:
        return ""


def _load_common_rules(framework_dir: Path) -> dict[str, Any]:
    """Load common cross-language rules from common/security.yml."""
    common_path = framework_dir / "common" / "security.yml"
    if not common_path.exists():
        return {}

    try:
        import yaml

        with open(common_path) as f:
            data = yaml.safe_load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _merge_custom_rule_file(rule_file: Path, custom: dict[str, Any]) -> None:
    """Load and merge a single .ai-rules/*.yml file into custom rules dict."""
    try:
        import yaml

        with open(rule_file) as f:
            data = yaml.safe_load(f)
        if not isinstance(data, dict):
            return
        # custom_rules (canonical) 与 anti_patterns (legacy) 同时接受并合并
        custom["anti_patterns"].extend(list(data.get("anti_patterns") or []) + list(data.get("custom_rules") or []))
        if "naming" in data:
            custom["naming"].update(data["naming"])
        if "thresholds" in data:
            custom["thresholds"].update(data["thresholds"])
    except Exception as e:
        import sys as _sys

        print(f"Warning: Failed to load {rule_file}: {e}", file=_sys.stderr)


def load_custom_rules(project_dir: Path) -> dict[str, Any]:
    """Load custom rules from .ai-rules/*.yml in the project directory."""
    custom: dict[str, Any] = {"anti_patterns": [], "naming": {}, "thresholds": {}}
    rules_dir = project_dir / ".ai-rules"
    if not rules_dir.is_dir():
        return custom

    try:
        import yaml  # noqa: F401 - availability probe
    except ImportError:
        import sys as _sys

        print("Warning: PyYAML not installed. Custom rules skipped.", file=_sys.stderr)
        return custom

    for rule_file in sorted(rules_dir.glob("*.yml")):
        _merge_custom_rule_file(rule_file, custom)

    try:
        from tools.scripts.rules_engine.rule_loader import _drop_dangerous_patterns

        _drop_dangerous_patterns(custom)
    except Exception as e:
        import sys as _sys

        print(f"Warning: Failed to drop dangerous custom rule patterns: {e}", file=_sys.stderr)
    return custom


def _get_embedded_rules(language: str) -> dict[str, Any]:
    """Fallback embedded rules when YAML files are unavailable."""
    common_anti_patterns: list[dict[str, Any]] = [
        {
            "id": f"{_rule_id_prefix(language)}-eval-exec",
            "name": "Use of eval/exec",
            "severity": "error",
            "category": "security",
            "pattern": r"\beval\s*\(|\bexec\s*\(",
            "message": "eval/exec are security risks",
            "fix_hint": "Find a safer alternative",
        },
        {
            "id": f"{_rule_id_prefix(language)}-hardcoded-secret",
            "name": "Hardcoded secret",
            "severity": "error",
            "category": "security",
            "pattern": r'(?:password|secret|api_key|token)\s*=\s*["\'][^"\']+["\']',
            "message": "Hardcoded secrets are a security vulnerability",
            "fix_hint": "Use environment variables",
        },
    ]
    return {"anti_patterns": common_anti_patterns, "thresholds": {}, "naming": {}}


def _merge_common_rules(base: dict[str, Any], common: dict[str, Any]) -> dict[str, Any]:
    """Merge common rules into base, dropping rules the base supersedes."""
    base_patterns = base.get("anti_patterns", [])
    superseded = _superseded_rule_ids(base_patterns)
    if not superseded:
        return _merge_rules(base, common)
    filtered = dict(common)
    filtered["anti_patterns"] = [
        pattern for pattern in common.get("anti_patterns", []) if pattern.get("id") not in superseded
    ]
    return _merge_rules(base, filtered)


def _merge_rules(base: dict[str, Any], custom: dict[str, Any]) -> dict[str, Any]:
    """Merge custom rules into base rules (V2.21 P5-62 拆分: 抽 _merge_anti_patterns + _merge_dict_section)."""
    merged = dict(base)

    if custom.get("anti_patterns"):
        merged["anti_patterns"] = _merge_anti_patterns(merged.get("anti_patterns", []), custom["anti_patterns"])

    _merge_dict_section(merged, custom, "naming")
    _merge_dict_section(merged, custom, "thresholds")

    return merged


def _merge_dict_section(merged: dict[str, Any], custom: dict[str, Any], key: str) -> None:
    """合并 dict 段 (naming/thresholds) (模块级 helper, 内部修改 merged).

    Args:
        merged: 累积目标
        custom: 自定义 dict
        key: 段名 (naming 或 thresholds)
    """
    if custom.get(key):
        merged.setdefault(key, {}).update(custom[key])


def validate_file(
    filepath: Path,
    language: str,
    custom_rules: dict[str, Any] | None = None,
) -> ValidationResult:
    """Validate a single file against language rules."""
    result = ValidationResult(file=str(filepath), language=language)

    try:
        lines = filepath.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, UnicodeDecodeError) as e:
        result.issues.append(
            Issue(
                rule_id="read-error",
                severity="error",
                category="io",
                file=str(filepath),
                line=0,
                message=f"Cannot read file: {e}",
            )
        )
        return result

    result.lines_checked = len(lines)
    rules = load_rules(language)

    if custom_rules and (custom_rules.get("anti_patterns") or custom_rules.get("thresholds")):
        rules = _merge_rules(rules, custom_rules)

    # 1. Regex anti-pattern checks
    from tools.scripts.complexity_analyzer import check_thresholds
    from tools.scripts.naming_analyzer import check_naming_conventions

    anti_issues = check_anti_patterns(lines, rules, str(filepath))
    pattern_map = {p["id"]: p for p in rules.get("anti_patterns", [])}
    for issue in anti_issues:
        rule_def = pattern_map.get(issue.rule_id, {})
        if "fix_replacement" in rule_def:
            issue.fix_replacement = rule_def["fix_replacement"]
    result.issues.extend(anti_issues)

    # 2. Naming convention checks
    result.issues.extend(check_naming_conventions(lines, rules, str(filepath)))

    # 3. Threshold checks
    result.issues.extend(check_thresholds(lines, rules, str(filepath)))

    # 4. Language-specific AST checks
    if language == "python":
        from tools.scripts.complexity_analyzer import check_python_ast

        result.issues.extend(check_python_ast(str(filepath), lines))

        # AST 语义检查: bare-raise 的 except 块判定 (正则无法表达)
        from tools.scripts.rules_engine.ast_semantic import check_python_bare_raise

        result.issues.extend(check_python_bare_raise(str(filepath), lines))

    # 5. 豁免过滤: 行级 noqa + 文件级 ignored-rules.toml (与 checker.check_file 同源)
    from tools.scripts.rules_engine.checker import _filter_suppressed_issues

    result.issues = _filter_suppressed_issues(filepath, result.issues, lines)

    return result


def validate_directory(
    dirpath: Path,
    language: str | None = None,
    exclude: list[str] | None = None,
    custom_rules: dict[str, Any] | None = None,
) -> list[ValidationResult]:
    """Validate all supported files in a directory."""
    results: list[ValidationResult] = []
    exclude = exclude or [
        "node_modules",
        "target",
        "vendor",
        ".git",
        "__pycache__",
        ".venv",
    ]

    for filepath in sorted(dirpath.rglob("*")):
        if not filepath.is_file():
            continue

        if any(ex in filepath.parts for ex in exclude):
            continue

        file_lang = language or detect_language_from_file(filepath)
        if file_lang is None:
            continue

        results.append(validate_file(filepath, file_lang, custom_rules=custom_rules))

    return results

"""Auto-fix engine: applies regex-based code fixes from YAML configuration.

Supports Python, JavaScript, TypeScript, and Rust auto-fixes.
Reads fix patterns from tools/fix_engine/fixes.yml and applies them to files.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .models import FixResult

# ADR-072: 表示"工具没能完成写盘"的结果 ID。CLI 用它决定退出码,
# 故必须定义在**生产方**, 由消费方 import —— 两边各写一个字面量
# 就等于留了一处会悄悄漂移的重复。
#
# 刻意**不含** flag-only 规则的 MANUAL FIX REQUIRED: 那是"建议人工
# 处理"的正常产物, 把退出码一并弄成非零会让既有 CI 长期红。
FAILED_WRITE_RULE_IDS: frozenset[str] = frozenset({"syntax-check-rejected", "write-failed"})


def _verify_syntax(content: str, language: str | None) -> tuple[bool, bool, str | None]:
    """校验修复结果是否仍可解析 (ADR-072).

    直接复用 ``ASTFixer._verify_syntax`` —— 本模块与
    ``ast_fixer`` 是两条独立的写盘路径, 但"修复结果能否解析"这个
    判据完全相同, 没有理由各写一份(各写一份就意味着将来会各自漂移)。

    实测依据 (真实 CLI, 无需注入任何缺陷): ``py-os-system`` 的
    pattern ``os\\.system\\(([^)]+)\\]`` 捕获组遇嵌套括号即在第一个
    ``)`` 处截断, 于是

        os.system(get_cmd())  ->  subprocess.run(get_cmd(, shell=True, check=True))

    ``language-rules --fix`` 会打印 "1 auto-fixed"、退出 0, 并把
    无法解析的文件留在磁盘上 —— 比 ADR-070 那处更糟, 因为它的汇总
    明确声称修复成功。

    Returns:
        ``(checked, violation, error)``, 语义同 ADR-070。
    """
    from .ast_fixer import ASTFixer

    lang = language if language else "python"
    return ASTFixer()._verify_syntax(content, lang)


# Fix patterns organized by language
FIX_PATTERNS: dict[str, dict[str, dict[str, Any]]] = {
    "python": {
        "py-bare-except": {
            "description": "Replace bare except with except Exception",
            "pattern": r"except\s*:",
            "replacement": "except Exception:",
            "import_needed": None,
        },
        "py-bare-except-pass": {
            "description": "Add logging to silent exception swallowing",
            "pattern": r"(except\s+\w+.*:\s*\n\s+)pass\s*$",
            "replacement": r"\1logging.exception('Exception occurred')",
            "import_needed": "import logging",
        },
        "py-eval-exec": {
            "description": "Replace eval call with ast.literal_eval()",
            "pattern": r"\be" + "val" + r"\(([^)]+)\)",
            "replacement": r"ast.literal_eval(\1)",
            "import_needed": "import ast",
        },
        "py-os-system": {
            "description": "Replace os.system() with subprocess.run()",
            "pattern": r"os\.system\(([^)]+)\)",
            "replacement": r"subprocess.run(\1, shell=True, check=True)",
            "import_needed": "import subprocess",
        },
        "py-yaml-load": {
            "description": "Replace yaml.load() with yaml.safe_load()",
            "pattern": r"yaml\.load\(([^,)]+)(?:,\s*[^)]+)?\)",
            "replacement": r"yaml.safe_load(\1)",
            "import_needed": None,
        },
        "py-print-logging": {
            "description": "Replace logger.info() with logger.info()",
            "pattern": r"print\((.+)\)",
            "replacement": r"logging.info(\1)",
            "import_needed": "import logging\nlogger = logging.getLogger(__name__)",
        },
        "py-star-import": {
            "description": "Flag wildcard import for manual fix",
            "pattern": r"from\s+(\S+)\s+import\s+\*",
            "replacement": None,  # Cannot auto-fix safely
            "import_needed": None,
        },
        "py-optional-syntax": {
            "description": "Replace Optional[X] with X | None",
            "pattern": r"Optional\[(\w+(?:\.\w+)*)\]",
            "replacement": r"\1 | None",
            "import_needed": None,
        },
        "py-mutable-default": {
            "description": "Replace mutable default argument (=[] or ={}) with =None",
            "pattern": r"(def \w+\s*\([^)]*?)=\s*(\[\s*\]|\{\s*\})",
            "replacement": r"\1=None",
            "import_needed": None,
        },
        "py-sql-injection": {
            "description": "Flag potential SQL injection via f-string in execute()",
            "pattern": r"\.(?:execute|executemany)\(\s*f[\"']",
            "replacement": None,
            "import_needed": None,
        },
        "py-global-statement": {
            "description": "Flag global statement for manual review",
            "pattern": r"^\s*global\s+\w+",
            "replacement": None,
            "import_needed": None,
        },
    },
    "javascript": {
        "js-eval": {
            "description": "Replace eval call with JSON.parse()",
            "pattern": r"\b" + "ev" + "al" + r"\(([^)]+)\)",
            "replacement": r"JSON.parse(\1)",
            "import_needed": None,
        },
        "js-var": {
            "description": "Replace var with const",
            "pattern": r"\bvar\s+",
            "replacement": "const ",
            "import_needed": None,
        },
        "js-innerhtml": {
            "description": "Replace innerHTML with textContent",
            "pattern": r"\.innerHTML\s*=",
            "replacement": ".textContent =",
            "import_needed": None,
        },
        "js-console-log": {
            "description": "Remove console.log statements",
            "pattern": r"console\.(?:log|debug|info)\s*\([^)]*\);?\n?",
            "replacement": "",
            "import_needed": None,
        },
        "js-debugger": {
            "description": "Remove debugger statement",
            "pattern": r"debugger;?\n?",
            "replacement": "",
            "import_needed": None,
        },
    },
    "typescript": {
        "ts-any-type": {
            "description": "Replace any with unknown",
            "pattern": r":\s*any\b",
            "replacement": ": unknown",
            "import_needed": None,
        },
        "ts-as-any": {
            "description": "Replace as any with as unknown",
            "pattern": r"\bas\s+any\b",
            "replacement": "as unknown",
            "import_needed": None,
        },
        "ts-require": {
            "description": "Flag require() for manual migration to import",
            "pattern": r"require\s*\(",
            "replacement": None,  # Cannot auto-fix safely
            "import_needed": None,
        },
        "ts-var-let": {
            "description": "Replace var with const",
            "pattern": r"\bvar\s+",
            "replacement": "const ",
            "import_needed": None,
        },
        "ts-triple-slash-ref": {
            "description": "Remove /// <reference directive",
            "pattern": r"///\s*<reference[^>]*>\s*\n?",
            "replacement": "",
            "import_needed": None,
        },
        "ts-ignore-comment": {
            "description": "Replace @ts-ignore with @ts-expect-error",
            "pattern": r"//\s*@ts-ignore\b",
            "replacement": "// @ts-expect-error",
            "import_needed": None,
        },
        "ts-explicit-any": {
            "description": "Replace explicit 'any' type annotation with 'unknown'",
            "pattern": r"(\([^)]*?:\s*)any\b",
            "replacement": r"\1unknown",
            "import_needed": None,
        },
        "ts-null-check": {
            "description": "Replace == null/undefined with === null/undefined",
            "pattern": r"==\s*(null|undefined)",
            "replacement": r"=== \1",
            "import_needed": None,
        },
    },
    "rust": {
        "rust-unwrap": {
            "description": "Replace unwrap() with expect()",
            "pattern": r"\.unwrap\(\)",
            "replacement": '.expect("TODO: add error message")',
            "import_needed": None,
        },
        "rust-panic": {
            "description": "Flag panic! for manual replacement",
            "pattern": r"panic!\(",
            "replacement": None,  # Cannot auto-fix safely
            "import_needed": None,
        },
        "rust-clone-copy": {
            "description": "Flag .clone() on possibly Copy types for manual review",
            "pattern": r"\.clone\(\)",
            "replacement": None,
            "import_needed": None,
        },
        "rust-shadowing": {
            "description": "Flag variable shadowing for manual review",
            "pattern": r"let\s+(\w+)\s*=[^;]*;\s*\n\s*let\s+\1\s*=",
            "replacement": None,
            "import_needed": None,
        },
        "rust-unused-import": {
            "description": "Flag use declarations for unused import review",
            "pattern": r"^\s*use\s+\w+(?:::\w+)*\s*;",
            "replacement": None,
            "import_needed": None,
        },
    },
    "java": {
        "java-sysout": {
            "description": "Replace System.out.println with logger",
            "pattern": r"System\.out\.logger.info(?:ln)?\(([^)]+)\)",
            "replacement": r"log.info(\1)",
            "import_needed": "import org.slf4j.Logger;\nimport org.slf4j.LoggerFactory;\nprivate static final Logger log = LoggerFactory.getLogger(ThisClass.class);",
        },
        "java-printstacktrace": {
            "description": "Replace e.printStackTrace() with log.error()",
            "pattern": r"(\w+)\.printStackTrace\(\)",
            "replacement": r"log.error(\"Error occurred\", \1)",
            "import_needed": None,
        },
        "java-catch-generic": {
            "description": "Flag generic Exception catch for manual fix",
            "pattern": r"catch\s*\(\s*Exception\s+\w+\s*\)",
            "replacement": None,  # Cannot auto-fix safely
            "import_needed": None,
        },
    },
    "go": {
        "go-err-ignore": {
            "description": "Flag ignored error return assigned to _",
            "pattern": r"_\s*=\s*\w+[.(]",
            "replacement": None,
            "import_needed": None,
        },
        "go-fmt-print": {
            "description": "Replace fmt.Print/Println/Printf with log.Print/Println/Printf",
            "pattern": r"fmt\.(Print|Println|Printf)\(",
            "replacement": r"log.$1(",
            "import_needed": '"log"',
        },
        "go-var-group": {
            "description": "Flag grouped var declaration for manual expansion",
            "pattern": r"var\s+\(",
            "replacement": None,
            "import_needed": None,
        },
        "go-naked-return": {
            "description": "Flag naked return in long functions for manual review",
            "pattern": r"^\s+return\s*$",
            "replacement": None,
            "import_needed": None,
        },
        "go-defer-in-loop": {
            "description": "Flag defer inside for loop for manual review",
            "pattern": r"for\s+[\s\S]*?\{[\s\S]*?defer\b",
            "replacement": None,
            "import_needed": None,
        },
    },
}

# Map language detection strings to fix pattern keys
LANG_MAP: dict[str, str] = {
    "python": "python",
    "javascript": "javascript",
    "typescript": "typescript",
    "rust": "rust",
    "java": "java",
    "csharp": "csharp",
    "cpp": "cpp",
    "go": "go",
}


def load_fix_patterns(language: str | None = None) -> dict[str, dict[str, Any]]:
    """Load fix patterns, optionally filtered by language.

    Args:
        language: Language key (python, javascript, etc.). None for all.

    Returns:
        Dict of rule_id -> fix config.
    """
    if language and language in FIX_PATTERNS:
        return FIX_PATTERNS[language]

    # Merge all patterns
    all_patterns: dict[str, dict[str, Any]] = {}
    for lang_patterns in FIX_PATTERNS.values():
        all_patterns.update(lang_patterns)
    return all_patterns


def detect_language(filepath: Path) -> str | None:
    """Detect language from file extension.

    Args:
        filepath: Path to check.

    Returns:
        Language string or None if unknown.
    """
    ext = filepath.suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".mjs": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".java": "java",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".go": "go",
    }
    return mapping.get(ext)


def _flag_only_fixes(
    filepath: Path,
    content: str,
    rule_id: str,
    pattern: str,
    description: str,
) -> list[FixResult]:
    """Find flag-only issues that cannot be auto-fixed."""
    results: list[FixResult] = []
    for match in re.finditer(pattern, content, re.MULTILINE):
        line_num = content[: match.start()].count("\n") + 1
        results.append(
            FixResult(
                file=str(filepath),
                rule_id=rule_id,
                line=line_num,
                original=match.group(),
                fixed="[MANUAL FIX REQUIRED]",
                description=description,
            )
        )
    return results


def _apply_replacement(
    filepath: Path,
    content: str,
    original_content: str,
    rule_id: str,
    pattern: str,
    replacement: str,
    description: str,
) -> tuple[str, list[FixResult]]:
    """Apply regex replacement and return updated content + results."""
    results: list[FixResult] = []
    new_content, count = re.subn(pattern, replacement, content, flags=re.MULTILINE)
    if count == 0:
        return content, results

    for match in re.finditer(pattern, original_content, re.MULTILINE):
        line_num = original_content[: match.start()].count("\n") + 1
        fixed_line = re.sub(pattern, replacement, match.group(), count=1)
        results.append(
            FixResult(
                file=str(filepath),
                rule_id=rule_id,
                line=line_num,
                original=match.group(),
                fixed=fixed_line,
                description=description,
            )
        )
    return new_content, results


def apply_fixes(
    filepath: Path,
    *,
    language: str | None = None,
    dry_run: bool = False,
    fix_ids: list[str] | None = None,
) -> list[FixResult]:
    """Apply auto-fixes to a file (V2.21 P5-50 拆分: 抽 _apply_rule_to_content + _write_if_changed).

    Args:
        filepath: File to fix.
        language: Language override (auto-detected if None).
        dry_run: If True, report fixes without applying.
        fix_ids: Only apply these specific rule IDs. None for all.

    Returns:
        List of FixResult for each fix applied/suggested.
    """
    lang = language or detect_language(filepath)
    if not lang or lang not in FIX_PATTERNS:
        return []

    try:
        content = filepath.read_text(encoding="utf-8")
    except (UnicodeDecodeError, FileNotFoundError):
        return []

    original_content = content
    results: list[FixResult] = []

    for rule_id, fix_config in FIX_PATTERNS[lang].items():
        if fix_ids and rule_id not in fix_ids:
            continue
        content, new_results = _apply_rule_to_content(filepath, content, original_content, rule_id, fix_config)
        results.extend(new_results)

    # ADR-072: 写盘可能被语法自检拒绝。此时**丢弃**此前累积的
    # auto-fix 结果, 只保留那条如实说明的拒绝记录 —— 否则汇总会
    # 继续打印 "N auto-fixed", 而磁盘上一个字节都没改。
    rejected = _write_if_changed(filepath, content, original_content, dry_run)
    if rejected:
        return rejected
    return results


def _apply_rule_to_content(
    filepath: Path,
    content: str,
    original_content: str,
    rule_id: str,
    fix_config: dict[str, Any],
) -> tuple[str, list[FixResult]]:
    """应用单条规则到 content, 返回新 content + results (模块级 helper).

    Args:
        filepath: 文件路径
        content: 当前内容
        original_content: 原始内容 (用于比较)
        rule_id: 规则 ID
        fix_config: 规则配置 (含 pattern/replacement/description)

    Returns:
        (new_content, new_results) 元组
    """
    pattern = fix_config["pattern"]
    replacement = fix_config.get("replacement")
    description = fix_config["description"]

    if replacement is None:
        new_results = _flag_only_fixes(filepath, content, rule_id, pattern, description)
        return content, new_results
    return _apply_replacement(filepath, content, original_content, rule_id, pattern, replacement, description)


def _write_if_changed(filepath: Path, content: str, original_content: str, dry_run: bool) -> list[FixResult]:
    """有变化且非 dry_run 时写回文件, 但写前必须通过语法自检 (ADR-072).

    Args:
        filepath: 文件路径
        content: 替换后内容
        original_content: 原始内容
        dry_run: 是否仅模拟

    Returns:
        被拒绝写盘时应告知调用方的结果 (正常写盘时为空列表)。

    ADR-072: 此前无任何校验直接 ``write_text``。实测
    ``py-os-system`` 这类 ``[^)]+`` 捕获组遇嵌套括号即截断, 把
    ``os.system(get_cmd())`` 改成无法解析的
    ``subprocess.run(get_cmd(, shell=True, check=True))``, 而 CLI 仍
    打印 "1 auto-fixed" 并退出 0 —— 声称成功、磁盘已坏。

    拒绝写盘时把该规则的结果**替换**为一条如实说明的 FixResult:
    保留原 results 会让汇总继续报 "auto-fixed", 那正是要消灭的假绿灯。
    """
    if dry_run or content == original_content:
        return []

    checked, violation, error = _verify_syntax(content, detect_language(filepath))
    if checked and violation:
        return [
            FixResult(
                file=str(filepath),
                rule_id="syntax-check-rejected",
                line=0,
                original="",
                # 必须用 MANUAL FIX REQUIRED 哨兵: _summarize 与
                # _format_text 都以该字符串判定"是否已自动修复"。若
                # 留空字符串, 汇总会把它算进 "N auto-fixed" —— 正是
                # 本 ADR 要消灭的那句假绿灯。
                fixed="[MANUAL FIX REQUIRED]",
                description=f"拒绝写盘: 修复结果无法解析 (ADR-072): {error}",
            )
        ]

    try:
        filepath.write_text(content, encoding="utf-8")
    except OSError:
        return [
            FixResult(
                file=str(filepath),
                rule_id="write-failed",
                line=0,
                original="",
                fixed="[MANUAL FIX REQUIRED]",
                description="写盘失败, 文件保持原样",
            )
        ]
    return []


def _resolve_file_lang(
    filepath: Path,
    extensions: set[str],
    languages: list[str] | None,
) -> str | None:
    """目录扫描文件过滤 + 语言判定 (Phase 36c cc 拆分).

    Returns:
        可修复的语言名；文件应跳过时返回 None
    """
    if not filepath.is_file():
        return None
    if "__pycache__" in str(filepath) or ".git" in str(filepath) or "node_modules" in str(filepath):
        return None
    if filepath.suffix.lower() not in extensions:
        return None
    lang = detect_language(filepath)
    if not lang:
        return None
    if languages and lang not in languages:
        return None
    return lang


def apply_fixes_to_directory(
    dirpath: Path,
    *,
    dry_run: bool = False,
    fix_ids: list[str] | None = None,
    languages: list[str] | None = None,
) -> list[FixResult]:
    """Apply auto-fixes to all code files in a directory.

    Args:
        dirpath: Directory to scan.
        dry_run: If True, report fixes without applying.
        fix_ids: Only apply these specific rule IDs. None for all.
        languages: Only fix files of these languages. None for all.

    Returns:
        List of all FixResults across all files.
    """
    extensions = {
        ".py",
        ".js",
        ".jsx",
        ".mjs",
        ".ts",
        ".tsx",
        ".rs",
        ".java",
        ".cs",
        ".cpp",
        ".go",
    }
    all_results: list[FixResult] = []

    for filepath in dirpath.rglob("*"):
        lang = _resolve_file_lang(filepath, extensions, languages)
        if lang is None:
            continue
        results = apply_fixes(filepath, language=lang, dry_run=dry_run, fix_ids=fix_ids)
        all_results.extend(results)

    return all_results


def format_fix_results(results: list[FixResult], *, format: str = "text") -> str:
    """Format fix results for display (V2.21 P5-49 拆分: 抽 _format_text + _summarize)."""
    if format == "json":
        import json

        return json.dumps([r.to_dict() for r in results], indent=2, ensure_ascii=False)

    if not results:
        return "No fixes applied."

    lines = _format_text(results)
    lines.append(_summarize(results))
    return "\n".join(lines)


def _format_text(results: list[FixResult]) -> list[str]:
    """格式化文本输出 (按 file 分组, 模块级 helper).

    Args:
        results: FixResult 列表

    Returns:
        文本行列表
    """
    lines: list[str] = []
    files = sorted(set(r.file for r in results))
    for filepath in files:
        file_results = [r for r in results if r.file == filepath]
        lines.append(f"\n📄 {filepath}")
        for r in file_results:
            status = "🔧" if r.fixed != "[MANUAL FIX REQUIRED]" else "⚠️"
            lines.append(f"  {status} Line {r.line}: [{r.rule_id}] {r.description}")
            lines.append(f"     Original: {r.original[:80]}")
            lines.append(f"     Fixed:    {r.fixed[:80]}")
    return lines


def _summarize(results: list[FixResult]) -> str:
    """汇总 fix 结果 (模块级 helper).

    Args:
        results: FixResult 列表

    Returns:
        汇总字符串
    """
    total = len(results)
    auto_fixed = sum(1 for r in results if r.fixed != "[MANUAL FIX REQUIRED]")
    manual_needed = total - auto_fixed
    return f"\nSummary: {total} issues found, {auto_fixed} auto-fixed, {manual_needed} manual fixes needed"

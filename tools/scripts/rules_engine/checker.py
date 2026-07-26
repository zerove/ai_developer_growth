"""Main rules engine orchestrator - coordinates all checkers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts._common import run_command

from .anti_pattern_checker import check_anti_patterns
from .complexity_checker import check_js_complexity, check_python_complexity
from .models import CheckResult, Issue
from .naming_checker import check_naming_conventions
from .plugins import get_plugins_for_language
from .rule_loader import load_rules_for_language


def check_file(
    filepath: Path,
    rules: dict[str, Any] | None = None,
    language: str | None = None,
    semantic: bool = False,
) -> CheckResult:
    """Check a single file against rules.

    Args:
        filepath: Path to the file.
        rules: Rules dict. Auto-loaded if None.
        language: Force language. Auto-detected if None.
        semantic: Enable AST-based semantic analysis (tree-sitter).
    """
    if not filepath.exists():
        return _file_not_found_result(filepath)

    if filepath.stat().st_size == 0:
        return CheckResult(file=str(filepath), issues=[], language=filepath.suffix.lower().lstrip("."), skipped=True)

    # Determine language
    lang = language or _detect_language(filepath)
    if lang == "unknown":
        return CheckResult(file=str(filepath), issues=[], language="unknown", skipped=True)

    # Load rules if not provided
    if rules is None:
        rules = load_rules_for_language(lang)

    # Read file
    try:
        content = filepath.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return CheckResult(file=str(filepath), issues=[], language=lang, skipped=True)

    lines = content.splitlines()

    # Run all checkers
    issues = _run_all_checkers(filepath, content, lines, lang, rules)

    # Optional: AST-based semantic analysis
    if semantic:
        issues.extend(_run_semantic_checks(filepath, lang))

    return CheckResult(
        file=str(filepath),
        issues=issues,
        language=lang,
    )


def _file_not_found_result(filepath: Path) -> CheckResult:
    """Create CheckResult for missing file."""
    return CheckResult(
        file=str(filepath),
        issues=[
            Issue(
                file=str(filepath),
                line=0,
                column=0,
                severity="error",
                category="io",
                rule_id="file-not-found",
                message=f"File not found: {filepath}",
            )
        ],
        language=filepath.suffix.lower().lstrip("."),
        skipped=True,
    )


def _run_all_checkers(filepath: Path, content: str, lines: list[str], lang: str, rules: dict[str, Any]) -> list[Issue]:
    """Run all checkers on file content."""
    issues: list[Issue] = []

    # Anti-patterns
    issues.extend(check_anti_patterns(filepath, lang, rules))

    # Naming conventions
    issues.extend(check_naming_conventions(lines, rules, str(filepath), lang))

    # Complexity
    if lang == "python":
        issues.extend(check_python_complexity(lines, rules, str(filepath)))
    elif lang in ("javascript", "typescript"):
        issues.extend(check_js_complexity(lines, rules, str(filepath)))

    # Run registered plugins
    for plugin in get_plugins_for_language(lang):
        try:
            issues.extend(plugin.check(filepath, content, lines, lang, rules))
        except Exception:
            # Plugin failed - continue with other checkers
            pass

    # Run external linters
    issues.extend(_run_external_linters(filepath, lang))

    return issues


def check_directory(
    dirpath: Path,
    rules: dict[str, Any] | None = None,
    languages: list[str] | None = None,
    jobs: int = 1,
    semantic: bool = False,
) -> list[CheckResult]:
    """Check all files in a directory.

    Args:
        dirpath: Directory to check.
        rules: Rules dict. Auto-loaded if None.
        languages: Filter to these languages only.
        jobs: Number of parallel workers (1 = serial).
        semantic: Enable AST-based semantic analysis.
    """
    results: list[CheckResult] = []

    if not dirpath.exists() or not dirpath.is_dir():
        return results

    # Collect files
    exts = [
        ".py",
        ".js",
        ".jsx",
        ".ts",
        ".tsx",
        ".rs",
        ".go",
        ".java",
        ".cs",
        ".cpp",
        ".cc",
        ".cxx",
        ".c",
        ".h",
        ".hpp",
    ]
    files: list[Path] = []
    for ext in exts:
        files.extend(dirpath.rglob(f"*{ext}"))

    # Filter out ignored paths
    files = [f for f in files if "__pycache__" not in str(f) and ".git" not in str(f) and "node_modules" not in str(f)]

    # Filter by language
    if languages:
        files = [f for f in files if _detect_language(f) in languages]

    if jobs <= 1 or len(files) <= 4:
        # Serial execution for small sets
        for filepath in files:
            result = check_file(filepath, rules, _detect_language(filepath), semantic=semantic)
            if not result.skipped:
                results.append(result)
    else:
        # Parallel execution
        from concurrent.futures import ProcessPoolExecutor, as_completed

        with ProcessPoolExecutor(max_workers=jobs) as executor:
            future_to_file = {
                executor.submit(check_file, fp, rules, _detect_language(fp), semantic): fp
                for fp in files
            }
            for future in as_completed(future_to_file):
                try:
                    result = future.result()
                    if not result.skipped:
                        results.append(result)
                except Exception:
                    pass

    return results


def _run_semantic_checks(filepath: Path, lang: str) -> list[Issue]:
    """Run AST-based semantic analysis on a file.

    Uses tree-sitter for accurate syntax tree analysis instead of regex.
    Detects: unused imports, missing docstrings, complexity violations.
    """
    issues: list[Issue] = []

    try:
        from .ast_parser import get_parser

        parser = get_parser()
        if not parser.available:
            return issues

        ast_result = parser.parse_file(filepath)
        if ast_result is None:
            return issues

        # Check unused imports
        for imp in ast_result.imports:
            if imp.is_from and imp.names:
                try:
                    content = filepath.read_text(encoding="utf-8")
                except Exception:
                    continue
                for name in imp.names:
                    # Skip wildcard imports
                    if name == "*":
                        continue
                    if name not in content or content.count(name) <= 1:
                        issues.append(
                            Issue(
                                file=str(filepath),
                                line=imp.line,
                                column=0,
                                severity="warning",
                                category="unused-import",
                                rule_id="semantic-unused-import",
                                message=f"Import '{name}' from '{imp.module}' appears unused",
                            )
                        )

        # Check missing docstrings for public functions
        for func in ast_result.functions:
            if not func.name.startswith("_") and func.docstring is None:
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=func.line,
                        column=0,
                        severity="info",
                        category="missing-docstring",
                        rule_id="semantic-missing-docstring",
                        message=f"Public function '{func.name}' lacks a docstring",
                    )
                )

        # Check complexity via AST
        for func in ast_result.functions:
            if func.complexity > 10:
                issues.append(
                    Issue(
                        file=str(filepath),
                        line=func.line,
                        column=0,
                        severity="warning",
                        category="complexity",
                        rule_id="semantic-high-complexity",
                        message=f"Function '{func.name}' has AST-estimated complexity {func.complexity} (>10)",
                    )
                )

    except ImportError:
        # tree-sitter not available - silently skip
        pass
    except Exception:
        # Semantic analysis failed - don't break the check pipeline
        pass

    return issues


def _detect_language(filepath: Path) -> str:
    """Detect language from file extension."""
    ext = filepath.suffix.lower()
    mapping = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".rs": "rust",
        ".go": "go",
        ".java": "java",
        ".cs": "csharp",
        ".cpp": "cpp",
        ".cc": "cpp",
        ".cxx": "cpp",
        ".c": "c",
        ".h": "c",
        ".hpp": "cpp",
    }
    return mapping.get(ext, "unknown")


def _run_external_linters(filepath: Path, lang: str) -> list[Issue]:
    """Run external linters and convert output to Issues."""
    issues: list[Issue] = []

    linters = {
        "python": ["ruff", "check", "--output-format=json", str(filepath)],
        "javascript": ["eslint", "--format=json", str(filepath)],
        "typescript": ["eslint", "--format=json", str(filepath)],
    }

    cmd = linters.get(lang)
    if not cmd:
        return issues

    try:
        exit_code, output = run_command(cmd)
        if output:
            issues.extend(_parse_linter_output(output, lang, str(filepath)))
    except Exception:
        # Linter not available or failed - silently ignore
        pass

    return issues


def _parse_linter_output(output: str, lang: str, filepath: str) -> list[Issue]:
    """Parse linter JSON output to Issues."""
    issues: list[Issue] = []
    try:
        import json

        data = json.loads(output)

        if lang == "python" and isinstance(data, list):
            # Ruff JSON format
            for item in data:
                issues.append(
                    Issue(
                        rule_id=item.get("code", "ruff"),
                        severity=_map_severity(item.get("level", "warning")),
                        category="linter",
                        file=filepath,
                        line=item.get("location", {}).get("row", 1),
                        column=item.get("location", {}).get("column", 1),
                        message=item.get("message", ""),
                    )
                )
        elif lang in ("javascript", "typescript") and isinstance(data, list):
            # ESLint JSON format
            for file_result in data:
                for msg in file_result.get("messages", []):
                    issues.append(
                        Issue(
                            rule_id=msg.get("ruleId", "eslint"),
                            severity=_map_severity(msg.get("severity", 1)),
                            category="linter",
                            file=filepath,
                            line=msg.get("line", 1),
                            column=msg.get("column", 1),
                            message=msg.get("message", ""),
                        )
                    )
    except Exception:
        # JSON parse failed - ignore
        pass

    return issues


def _map_severity(level: str | int) -> str:
    """Map various severity formats to standard levels."""
    if isinstance(level, int):
        return "error" if level == 2 else "warning"
    level = level.lower()
    if level in ("error", "critical", "fatal"):
        return "error"
    return "warning"

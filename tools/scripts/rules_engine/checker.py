"""Main rules engine orchestrator - coordinates all checkers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.scripts._common import rules_dir, run_command

from .anti_pattern_checker import check_anti_patterns
from .complexity_checker import check_js_complexity, check_python_complexity
from .context import adjust_severity, detect_file_role
from .models import CheckResult, Issue
from .naming_checker import check_naming_conventions
from .plugins import get_plugins_for_language
from .rule_loader import load_rules_for_language

# Worker 进程内共享的规则缓存（由 _worker_init 注入）
_WORKER_RULES: dict[str, Any] = {}


def _worker_init(shared_rules: dict[str, Any] | None) -> None:
    """Worker 进程初始化：注入共享规则，避免每文件重复加载。

    通过 ProcessPoolExecutor 的 initializer 调用，仅在 worker 进程中执行。
    """
    global _WORKER_RULES
    _WORKER_RULES = shared_rules or {}


def _worker_check(
    pair: tuple[Path, str],
    do_semantic: bool = False,
    do_linters: bool = True,
) -> CheckResult | None:
    """Worker 任务：使用预热规则执行单文件检查（模块级，可被 pickle）。"""
    fp, lang = pair
    result = check_file(
        fp,
        _WORKER_RULES or None,
        lang,
        semantic=do_semantic,
        run_linters=do_linters,
    )
    if result.skipped:
        return None
    return result


# ── 框架检测 ──────────────────────────────────────────────

# 目录遍历时排除的路径段（避免误扫构建产物、依赖、缓存）
DEFAULT_EXCLUDED_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".cache",
    "build",
    "dist",
    ".opencode",
    ".tox",
    "htmlcov",
    ".coverage",
    "site-packages",
    "MagicMock",
}

FRAMEWORK_DETECTORS: dict[str, dict[str, list[str]]] = {
    "react": {"files": ["package.json"], "packages": ["react", "react-dom"]},
    "vue": {"files": ["package.json"], "packages": ["vue"]},
    "express": {"files": ["package.json"], "packages": ["express"]},
    "nextjs": {"files": ["package.json", "next.config.js"], "packages": ["next"]},
    "django": {"files": ["manage.py", "requirements.txt"], "packages": ["django"]},
    "fastapi": {"files": ["requirements.txt", "pyproject.toml"], "packages": ["fastapi"]},
    "actix": {"files": ["Cargo.toml"], "packages": ["actix-web"]},
    "spring": {"files": ["pom.xml", "build.gradle"], "packages": ["spring-context"]},
    "spring-boot": {"files": ["pom.xml", "build.gradle"], "packages": ["spring-boot-starter"]},
}


def _detect_framework(dirpath: Path) -> str | None:
    """Detect project framework from project files."""
    for fw_name, hints in FRAMEWORK_DETECTORS.items():
        # Check for marker files
        for filename in hints["files"]:
            marker = dirpath / filename
            if marker.exists():
                # For package-based detection, verify dependency
                if marker.name == "package.json":
                    try:
                        import json

                        deps = {
                            **json.loads(marker.read_text()).get("dependencies", {}),
                            **json.loads(marker.read_text()).get("devDependencies", {}),
                        }
                        if any(pkg in deps for pkg in hints["packages"]):
                            return fw_name
                    except Exception:
                        return fw_name  # best effort
                elif marker.name == "Cargo.toml":
                    content = marker.read_text()
                    if any(pkg in content for pkg in hints["packages"]):
                        return fw_name
                elif marker.name == "requirements.txt":
                    content = marker.read_text().lower()
                    if any(pkg in content for pkg in hints["packages"]):
                        return fw_name
                elif marker.name == "pyproject.toml":
                    content = marker.read_text().lower()
                    if any(pkg in content for pkg in hints["packages"]):
                        return fw_name
                elif marker.name == "manage.py":
                    return fw_name
                elif marker.name in ("pom.xml", "build.gradle"):
                    return fw_name  # best effort
    return None


def check_file(
    filepath: Path,
    rules: dict[str, Any] | None = None,
    language: str | None = None,
    semantic: bool = False,
    run_linters: bool = True,
) -> CheckResult:
    """Check a single file against rules.

    Args:
        filepath: Path to the file.
        rules: Rules dict. Auto-loaded if None.
        language: Force language. Auto-detected if None.
        semantic: Enable AST-based semantic analysis (tree-sitter).
        run_linters: Run external linters (ruff/eslint) per file. Disable for
            bulk scans where per-file subprocess spawns dominate runtime.
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
    issues = _run_all_checkers(filepath, content, lines, lang, rules, run_linters=run_linters)

    # G1: 上下文感知 — 检测文件角色并调整严重度
    ctx_markers = _load_context_markers(filepath.parent)
    file_role = detect_file_role(filepath, ctx_markers)
    if file_role:
        for issue in issues:
            issue.context_role = file_role
            issue.severity = adjust_severity(issue.severity, file_role)

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


def _run_all_checkers(
    filepath: Path, content: str, lines: list[str], lang: str, rules: dict[str, Any], run_linters: bool = True
) -> list[Issue]:
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
    if run_linters:
        issues.extend(_run_external_linters(filepath, lang))

    return issues


def check_directory(
    dirpath: Path,
    rules: dict[str, Any] | None = None,
    languages: list[str] | None = None,
    jobs: int = 1,
    semantic: bool = False,
    run_linters: bool = True,
) -> list[CheckResult]:
    """Check all files in a directory.

    Args:
        dirpath: Directory to check.
        rules: Rules dict. Auto-loaded if None.
        languages: Filter to these languages only.
        jobs: Number of parallel workers (1 = serial).
        semantic: Enable AST-based semantic analysis.
        run_linters: Run external linters (ruff/eslint) per file.
    """
    results: list[CheckResult] = []

    if not dirpath.exists() or not dirpath.is_dir():
        return results

    # Detect framework and load framework-specific rules
    framework = _detect_framework(dirpath)
    if framework:
        try:
            fw_rules = load_rules_for_language(framework, rules_dir() / "frameworks" / framework)
            if rules:
                from .rule_loader import _merge_rules

                rules = _merge_rules(rules, fw_rules)
        except Exception:
            _ = None  # framework rules optional

    # Load domain rules from project config
    try:
        from .rule_loader import load_domain_rules

        domain_rules = load_domain_rules(dirpath)
        if domain_rules.get("anti_patterns"):
            if rules:
                from .rule_loader import _merge_rules

                rules = _merge_rules(rules, domain_rules)
            else:
                rules = domain_rules
    except Exception:
        _ = None  # domain rules optional

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

    # Filter out ignored paths (path-segment match to avoid false hits like "dist" in names)

    def _is_excluded(filepath: Path) -> bool:
        parts = set(filepath.parts)
        return bool(parts & DEFAULT_EXCLUDED_DIRS)

    files = [f for f in files if not _is_excluded(f)]

    # Filter by language
    if languages:
        files = [f for f in files if _detect_language(f) in languages]

    if jobs <= 1 or len(files) <= 4:
        # Serial execution for small sets
        for filepath in files:
            result = check_file(filepath, rules, _detect_language(filepath), semantic=semantic, run_linters=run_linters)
            if not result.skipped:
                results.append(result)
    else:
        # Parallel execution with worker warm-up (shared rules, no re-load)
        from collections.abc import Iterator
        from concurrent.futures import ProcessPoolExecutor

        # 预热规则：在主进程加载一次，随后通过 initializer 传递给 worker，
        # 避免每个任务内部重复读取 YAML / 解析规则文件
        warmup_rules = rules or {}

        pairs = [(fp, _detect_language(fp)) for fp in files]
        with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(warmup_rules,)) as executor:
            worker_results: Iterator[CheckResult | None] = executor.map(
                _worker_check,
                pairs,
                [semantic] * len(pairs),
                [run_linters] * len(pairs),
                chunksize=16,
            )
            for worker_result in worker_results:
                try:
                    if worker_result is not None:
                        results.append(worker_result)
                except Exception:
                    _ = None  # skip failed check

    # Architecture analysis (cross-file)
    try:
        from .arch import DependencyGraph, LayerChecker

        arch_graph = DependencyGraph()
        arch_issues = arch_graph.analyze_directory(dirpath)

        # Layer check only if we have a config
        layer_config_path = dirpath / ".adg" / "architecture.yml"
        if layer_config_path.exists():
            from .arch import LayerConfig

            lc = LayerConfig.from_yaml(layer_config_path)
            layer_checker = LayerChecker(lc)
            arch_issues.extend(layer_checker.check_graph(arch_graph))

        # Convert architecture issues to CheckResult
        if arch_issues:
            arch_result = CheckResult(
                file=str(dirpath / ".architecture"),
                issues=[i.to_issue("arch-" + i.category) for i in arch_issues],
                language="architecture",
            )
            results.append(arch_result)
    except ImportError:
        _ = None  # arch module not available
    except Exception:
        _ = None  # arch checks optional

    return results


def _run_semantic_checks(filepath: Path, lang: str) -> list[Issue]:
    """Run AST-based semantic analysis on a file.

    Uses tree-sitter for accurate syntax tree analysis instead of regex.
    通过语义规则插件系统执行检查（见 semantic_rules.py），
    新增规则只需注册 SemanticRule，无需修改本模块。
    """
    issues: list[Issue] = []

    try:
        from .ast_parser import get_parser
        from .semantic_rules import run_semantic_rules

        parser = get_parser()
        if not parser.available:
            return issues

        ast_result = parser.parse_file(filepath)
        if ast_result is None:
            return issues

        # 运行所有匹配语言的语义规则插件
        issues.extend(run_semantic_rules(ast_result, filepath, lang))

    except ImportError:
        # tree-sitter not available - silently skip
        pass
    except Exception:
        # Semantic analysis failed - don't break the check pipeline
        pass

    return issues


def _load_context_markers(dirpath: Path) -> dict[str, str]:
    """Load user-defined context markers from .adg/config.yml."""
    for search_dir in [dirpath, dirpath.parent, dirpath.parents[2] if len(dirpath.parents) > 2 else None]:
        if search_dir is None:
            continue
        config_path = search_dir / ".adg" / "config.yml"
        if config_path.exists():
            try:
                from .context import load_role_config

                return load_role_config(config_path)
            except Exception:
                _ = None  # role config optional
    return {}


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


# Test change

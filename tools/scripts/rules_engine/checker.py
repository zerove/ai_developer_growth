"""Main rules engine orchestrator - coordinates all checkers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts._common import rules_dir, run_command
from tools.scripts.rules_engine.logger import logger

from .anti_pattern_checker import check_anti_patterns
from .complexity_checker import check_js_complexity, check_python_complexity
from .context import adjust_severity, detect_file_role
from .models import CheckResult, Issue
from .naming_checker import check_naming_conventions
from .plugins import get_plugins_for_language
from .rule_loader import load_rules_for_language

if TYPE_CHECKING:
    from .store import CheckStore

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
    cache_db: str | None = None,
    rules_hash: str = "",
) -> CheckResult | None:
    """Worker 任务：使用预热规则执行单文件检查（模块级，可被 pickle）。

    cache_db 非空时启用增量缓存写入（每个 worker 独立 SQLite 连接，
    WAL 模式下多进程并发写安全）。rules_hash 为规则集签名，
    规则/引擎变化时旧缓存键不匹配自然失效。
    """
    fp, lang = pair
    store = None
    if cache_db:
        try:
            from .store import CheckStore

            store = CheckStore(cache_db)
            stat = fp.stat()
            cached = store.get_cached_result(str(fp), stat.st_mtime, stat.st_size, rules_hash)
            if cached is not None:
                issues = [Issue(**i) for i in cached["issues"]]
                return CheckResult(file=str(fp), issues=issues, language=cached["language"])
        except Exception as exc:  # noqa: BLE001
            logger.debug("worker 缓存读取失败，回退完整检查 %s: %s", fp, exc)
            store = None  # 缓存不可用时退化为完整检查
    result = check_file(
        fp,
        _WORKER_RULES or None,
        lang,
        semantic=do_semantic,
        run_linters=do_linters,
    )
    if result.skipped:
        return None
    if store is not None:
        try:
            stat = fp.stat()
            store.set_cached_result(
                str(fp),
                stat.st_mtime,
                stat.st_size,
                {
                    "language": result.language,
                    "passed": result.passed,
                    "errors": result.error_count,
                    "warnings": result.warning_count,
                    "info": result.info_count,
                    "issues": [i.to_dict() for i in result.issues],
                },
                rules_hash,
            )
        except Exception as exc:  # noqa: BLE001
            logger.debug("worker 缓存写入失败（不影响检查结果）: %s: %s", type(exc).__name__, exc)
    return result


# ── 框架检测 ──────────────────────────────────────────────


def _config_excluded_dirs() -> set[str]:
    """从 [tool.adg].exclude 合并额外的排除目录。"""
    overrides: set[str] = {
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
    try:
        from tools.scripts.app_config import get_setting

        extra = get_setting("exclude", [])
        if isinstance(extra, list):
            overrides.update(str(item) for item in extra)
    except Exception:
        import logging

        logging.getLogger(__name__).warning("Failed to load exclude config", exc_info=True)
    return overrides


# 目录遍历时排除的路径段（避免误扫构建产物、依赖、缓存）
DEFAULT_EXCLUDED_DIRS: set[str] = _config_excluded_dirs()

FRAMEWORK_DETECTORS: dict[str, dict[str, list[str]]] = {
    "react": {"files": ["package.json"], "packages": ["react", "react-dom"]},
    "vue": {"files": ["package.json"], "packages": ["vue"]},
    "express": {"files": ["package.json"], "packages": ["express"]},
    "nextjs": {"files": ["package.json", "next.config.js"], "packages": ["next"]},
    "django": {"files": ["manage.py", "requirements.txt"], "packages": ["django"]},
    "fastapi": {
        "files": ["requirements.txt", "pyproject.toml"],
        "packages": ["fastapi"],
    },
    "actix": {"files": ["Cargo.toml"], "packages": ["actix-web"]},
    "spring": {"files": ["pom.xml", "build.gradle"], "packages": ["spring-context"]},
    "spring-boot": {
        "files": ["pom.xml", "build.gradle"],
        "packages": ["spring-boot-starter"],
    },
}


def _detect_framework(dirpath: Path) -> str | None:
    """Detect project framework from project files (V2.21 P5-37 拆分: 抽 _check_marker)."""
    for fw_name, hints in FRAMEWORK_DETECTORS.items():
        for filename in hints["files"]:
            marker = dirpath / filename
            if marker.exists() and _check_marker(marker, hints["packages"]):
                return fw_name
    return None


def _check_marker(marker: Path, packages: list[str]) -> bool:
    """检查 marker 文件是否匹配 framework (按文件名分派, 模块级 helper).

    Args:
        marker: marker 文件路径
        packages: 框架依赖包列表

    Returns:
        是否匹配
    """
    if marker.name == "package.json":
        return _check_package_json(marker, packages)
    if marker.name == "Cargo.toml":
        return _check_text_contains(marker, packages)
    if marker.name in ("requirements.txt", "pyproject.toml"):
        return _check_text_contains(marker, packages, lower=True)
    if marker.name == "manage.py":
        return True
    if marker.name in ("pom.xml", "build.gradle"):
        return True  # best effort
    return False


def _check_package_json(marker: Path, packages: list[str]) -> bool:
    """检查 package.json 依赖 (模块级 helper).

    Args:
        marker: package.json 路径
        packages: 框架包列表

    Returns:
        是否任一包在 dependencies/devDependencies 中
    """
    import json

    try:
        data = json.loads(marker.read_text())
    except Exception:
        return True  # best effort
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    return any(pkg in deps for pkg in packages)


def _check_text_contains(marker: Path, packages: list[str], lower: bool = False) -> bool:
    """检查 marker 文件内容是否含任一 package (模块级 helper).

    Args:
        marker: 文件路径
        packages: 包列表
        lower: 是否 lowercase (requirements.txt/pyproject.toml)

    Returns:
        是否含任一包
    """
    content = marker.read_text()
    if lower:
        content = content.lower()
    return any(pkg in content for pkg in packages)


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
        return CheckResult(
            file=str(filepath),
            issues=[],
            language=filepath.suffix.lower().lstrip("."),
            skipped=True,
        )

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

    # 豁免过滤: 行级 noqa 注释 + 文件级 ignored-rules.toml
    issues = _filter_suppressed_issues(filepath, issues, lines)

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


def _filter_suppressed_issues(
    filepath: Path,
    issues: list[Issue],
    lines: list[str],
) -> list[Issue]:
    """过滤被豁免的违规。

    支持两种机制:
    1. 行级 noqa 注释: ``# noqa`` (全豁免) 或 ``# noqa: rule-id[,rule-id]``
       规则引擎不依赖外部 linter 的 noqa 处理, 需自行解析。
    2. 文件级豁免: ``.jcode/ignored-rules.toml`` 的 [[ignored_files]] 段,
       按 file 路径片段 + rules 列表豁免。
    """
    if not issues:
        return issues

    # --- 行级 noqa ---
    noqa_by_line: dict[int, set[str] | None] = {}
    for idx, line in enumerate(lines, start=1):
        m = re.search(r"#\s*noqa(?::\s*([A-Za-z0-9_,\-]+))?", line)
        if m:
            rules_str = m.group(1)
            noqa_by_line[idx] = None if not rules_str else {r.strip() for r in rules_str.split(",") if r.strip()}

    # --- 文件级 ignored-rules.toml ---
    file_rules = _load_ignored_rules(filepath)

    result: list[Issue] = []
    for issue in issues:
        suppressed = False
        # 违规行本身, 以及其前一行 (部分检测器把多行语句的违规归到语句尾/下一行)
        candidate_lines = (issue.line, issue.line - 1)
        for ln in candidate_lines:
            line_noqa = noqa_by_line.get(ln)
            if line_noqa is None and ln in noqa_by_line:
                suppressed = True  # 裸 noqa: 全豁免
            elif line_noqa and issue.rule_id in line_noqa:
                suppressed = True
            if suppressed:
                break
        if not suppressed and file_rules and issue.rule_id in file_rules:
            suppressed = True
        if not suppressed:
            result.append(issue)
    return result


def _load_ignored_rules(filepath: Path) -> set[str]:
    """从 .jcode/ignored-rules.toml 加载针对该文件的规则豁免列表。"""
    try:
        import tomllib
    except ImportError:
        return set()

    config_path = Path(".jcode/ignored-rules.toml")
    if not config_path.exists():
        return set()

    try:
        data = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except Exception:
        return set()

    path_str = str(filepath)
    ignored: set[str] = set()
    for entry in data.get("ignored_files", []):
        pattern = str(entry.get("file", ""))
        if pattern and pattern in path_str:
            ignored.update(str(r) for r in entry.get("rules", []))
    return ignored


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
    filepath: Path,
    content: str,
    lines: list[str],
    lang: str,
    rules: dict[str, Any],
    run_linters: bool = True,
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

    # AST 语义检查: 正则无法表达的规则 (bare-raise 的 except 块判定)
    if lang == "python":
        from .ast_semantic import check_python_bare_raise

        issues.extend(check_python_bare_raise(str(filepath), lines))

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


def _load_directory_rules(dirpath: Path, base_rules: dict[str, Any] | None) -> dict[str, Any] | None:
    """合并框架规则 + 域规则到 base_rules。

    ADR-014: 从 check_directory 拆出。框架/域规则均 optional，失败回退
    到 base_rules 不抛错。
    """
    rules = base_rules
    framework = _detect_framework(dirpath)
    if framework:
        try:
            fw_rules = load_rules_for_language(framework, rules_dir() / "frameworks" / framework)
            if rules:
                from .rule_loader import _merge_rules

                rules = _merge_rules(rules, fw_rules)
        except Exception:
            _ = None  # framework rules optional

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

    return rules


def _discover_target_files(dirpath: Path, languages: list[str] | None) -> list[Path]:
    """发现目录下所有可检查文件，按扩展名 + 排除目录 + 语言过滤。

    ADR-014: 从 check_directory 拆出。
    """
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

    def _is_excluded(filepath: Path) -> bool:
        parts = set(filepath.parts)
        return bool(parts & DEFAULT_EXCLUDED_DIRS)

    files = [f for f in files if not _is_excluded(f)]

    if languages:
        files = [f for f in files if _detect_language(f) in languages]

    return files


def _init_cache_store(use_cache: bool, db_path: str | Path) -> tuple[CheckStore | None, str]:
    """初始化增量缓存。

    ADR-014: 从 check_directory 拆出。失败时 store=None + rules_hash=""
    表示退化为完整检查。
    """
    store = None
    rules_hash = ""
    if use_cache:
        try:
            from .store import CheckStore, compute_rules_signature

            store = CheckStore(db_path)
            rules_hash = compute_rules_signature()
        except Exception as exc:  # noqa: BLE001
            store = None
            logger.warning(
                "增量缓存初始化失败，本次退化为完整检查: %s: %s",
                type(exc).__name__,
                exc,
            )
    return store, rules_hash


def _run_architecture_analysis(dirpath: Path) -> list[CheckResult]:
    """运行跨文件架构分析（依赖图 + 分层检查）。

    ADR-014: 从 check_directory 拆出。arch 模块 ImportError 时返回空列表
    （非阻塞），其他异常也吞掉。
    """
    results: list[CheckResult] = []
    try:
        from .arch import DependencyGraph, LayerChecker

        arch_graph = DependencyGraph()
        arch_issues = arch_graph.analyze_directory(dirpath)

        layer_config_path = dirpath / ".adg" / "architecture.yml"
        if layer_config_path.exists():
            from .arch import LayerConfig

            lc = LayerConfig.from_yaml(layer_config_path)
            layer_checker = LayerChecker(lc)
            arch_issues.extend(layer_checker.check_graph(arch_graph))

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


def _check_with_cache(
    filepath: Path,
    lang: str,
    rules: dict[str, Any] | None,
    store: CheckStore | None,
    rules_hash: str,
    semantic: bool,
    run_linters: bool,
) -> tuple[CheckResult, bool]:
    """单文件检查（带缓存），返回 (CheckResult, cache_degraded_increment)。

    ADR-014: 从 check_directory 拆出 cache logic。store=None 时退化为完整检查。
    """
    cache_degraded = False
    if store is not None:
        try:
            stat = filepath.stat()
            cached = store.get_cached_result(str(filepath), stat.st_mtime, stat.st_size, rules_hash)
            if cached is not None:
                issues = [Issue(**i) for i in cached["issues"]]
                return (
                    CheckResult(file=str(filepath), issues=issues, language=cached["language"]),
                    False,
                )
        except Exception as exc:  # noqa: BLE001
            cache_degraded = True
            logger.debug("缓存读取失败，回退完整检查 %s: %s", filepath, exc)
    result = check_file(filepath, rules, lang, semantic=semantic, run_linters=run_linters)
    if store is not None and not result.skipped:
        try:
            stat = filepath.stat()
            store.set_cached_result(
                str(filepath),
                stat.st_mtime,
                stat.st_size,
                {
                    "language": result.language,
                    "passed": result.passed,
                    "errors": result.error_count,
                    "warnings": result.warning_count,
                    "info": result.info_count,
                    "issues": [i.to_dict() for i in result.issues],
                },
                rules_hash,
            )
        except Exception as exc:  # noqa: BLE001
            cache_degraded = True
            logger.debug("缓存写入失败（不影响检查结果）%s: %s", filepath, exc)
    return result, cache_degraded


def _check_files_serial(
    files: list[Path],
    rules: dict[str, Any] | None,
    store: CheckStore | None,
    rules_hash: str,
    semantic: bool,
    run_linters: bool,
) -> tuple[list[CheckResult], int]:
    """串行检查（小集合 jobs<=1 或 files<=4）。

    ADR-014: 从 check_directory 拆出。
    """
    results: list[CheckResult] = []
    degraded = 0
    for filepath in files:
        result, was_degraded = _check_with_cache(
            filepath, _detect_language(filepath), rules, store, rules_hash, semantic, run_linters
        )
        if was_degraded:
            degraded += 1
        if not result.skipped:
            results.append(result)
    return results, degraded


def _check_files_parallel(
    files: list[Path],
    rules: dict[str, Any] | None,
    store: CheckStore | None,
    rules_hash: str,
    db_path: str | Path,
    use_cache: bool,
    semantic: bool,
    run_linters: bool,
    jobs: int,
) -> list[CheckResult]:
    """并行检查（ProcessPoolExecutor + worker 缓存）。

    ADR-014: 从 check_directory 拆出。worker 进程各自独立 SQLite 连接，
    WAL 模式下并发写安全。
    """
    from collections.abc import Iterator
    from concurrent.futures import ProcessPoolExecutor

    warmup_rules = rules or {}
    pairs = [(fp, _detect_language(fp)) for fp in files]
    cache_db: str | None = str(db_path) if use_cache and store is not None else None
    worker_rules_hash = rules_hash
    results: list[CheckResult] = []
    with ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(warmup_rules,)) as executor:
        worker_results: Iterator[CheckResult | None] = executor.map(
            _worker_check,
            pairs,
            [semantic] * len(pairs),
            [run_linters] * len(pairs),
            [cache_db] * len(pairs),
            [worker_rules_hash] * len(pairs),
            chunksize=16,
        )
        for worker_result in worker_results:
            try:
                if worker_result is not None:
                    results.append(worker_result)
            except Exception:
                _ = None  # skip failed check
    return results


def check_directory(
    dirpath: Path,
    rules: dict[str, Any] | None = None,
    languages: list[str] | None = None,
    jobs: int = 1,
    semantic: bool = False,
    run_linters: bool = True,
    use_cache: bool = False,
    db_path: str | Path = "adg_quality.db",
) -> list[CheckResult]:
    """Check all files in a directory.

    Args:
        dirpath: Directory to check.
        rules: Rules dict. Auto-loaded if None.
        languages: Filter to these languages only.
        jobs: Number of parallel workers (1 = serial).
        semantic: Enable AST-based semantic analysis.
        run_linters: Run external linters (ruff/eslint) per file.
        use_cache: 启用增量缓存（mtime+size 未变则复用上次结果）。
        db_path: 统一存储数据库路径（use_cache=True 时使用）。
    """
    results: list[CheckResult] = []

    if not dirpath.exists() or not dirpath.is_dir():
        return results

    rules = _load_directory_rules(dirpath, rules)
    files = _discover_target_files(dirpath, languages)
    store, rules_hash = _init_cache_store(use_cache, db_path)

    if jobs <= 1 or len(files) <= 4:
        checked, cache_degraded = _check_files_serial(files, rules, store, rules_hash, semantic, run_linters)
    else:
        cache_degraded = 0
        checked = _check_files_parallel(
            files, rules, store, rules_hash, db_path, use_cache, semantic, run_linters, jobs
        )

    results.extend(checked)
    results.extend(_run_architecture_analysis(dirpath))

    if use_cache and cache_degraded:
        logger.warning("本次运行缓存降级 %d 次（读取/写入失败已回退完整检查）", cache_degraded)

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
    for search_dir in [
        dirpath,
        dirpath.parent,
        dirpath.parents[2] if len(dirpath.parents) > 2 else None,
    ]:
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

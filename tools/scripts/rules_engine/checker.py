"""Main rules engine orchestrator - coordinates all checkers."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts._common import rules_dir, walk_files
from tools.scripts.app_config import get_setting
from tools.scripts.rules_engine.logger import logger

from ._checker_linters import _batched_linters as _batched_linters
from ._checker_linters import _map_severity as _map_severity
from ._checker_linters import _parse_linter_output as _parse_linter_output
from ._checker_linters import _run_external_linters as _run_external_linters
from ._checker_markers import DEFAULT_EXCLUDED_DIRS as DEFAULT_EXCLUDED_DIRS
from ._checker_markers import FRAMEWORK_DETECTORS as FRAMEWORK_DETECTORS
from ._checker_markers import _check_marker as _check_marker
from ._checker_markers import _check_package_json as _check_package_json
from ._checker_markers import _check_text_contains as _check_text_contains
from ._checker_markers import _config_excluded_dirs as _config_excluded_dirs
from ._checker_markers import _detect_framework as _detect_framework
from ._checker_markers import _detect_language as _detect_language
from ._checker_markers import _load_context_markers as _load_context_markers
from ._checker_noqa import _filter_suppressed_issues as _filter_suppressed_issues
from ._checker_noqa import _is_issue_suppressed as _is_issue_suppressed
from ._checker_noqa import _load_ignored_rules as _load_ignored_rules
from ._checker_noqa import _parse_noqa_lines as _parse_noqa_lines
from ._checker_workers import _worker_check as _worker_check
from ._checker_workers import _worker_init as _worker_init
from .anti_pattern_checker import check_anti_patterns
from .complexity_checker import check_js_complexity, check_python_complexity
from .context import adjust_severity, detect_file_role
from .models import CheckResult, Issue
from .naming_checker import check_naming_conventions
from .plugins import get_plugins_for_language
from .rule_loader import load_rules_for_language

if TYPE_CHECKING:
    from .store import CheckStore

__all__ = [
    "DEFAULT_EXCLUDED_DIRS",
    "FRAMEWORK_DETECTORS",
    "check_directory",
    "check_file",
    "load_rules_for_language",
]

# ── 缓存可观测性词汇表（cache/stats 对齐第一阶段）────────────
#
# 目的: 让 rules_engine / hooks --cache / adg check 三条路径对"缓存状态"
# 使用同一套键名与语义, 下游只依赖词汇表即可解读, 不必逐路径猜字段。
#
# 契约:
#   cache_supported : 该执行路径是否具备缓存能力
#   cache_engine    : 缓存实现标识（无能力时为 None）
#   cache_reason    : 缓存不可用/未启用时的原因；可用且已启用时为 None
#   cache_hit_rate  : hits/(hits+misses)；计数不可知时为 None（不臆造 0）
CACHE_ENGINE_ID = "rules_engine_check_store"
CACHE_REASON_DISABLED = "cache_disabled"


def _cache_hit_rate(hits: int | None, misses: int | None) -> float | None:
    """缓存命中率；计数不可知或无缓存操作时返回 None（不臆造 0）。"""
    if hits is None or misses is None:
        return None
    total = hits + misses
    if total <= 0:
        return None
    return hits / total


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
    skip_result = _check_file_skip_conditions(filepath, language)
    if skip_result:
        return skip_result

    lang, rules, content, lines, skip_issues = _prepare_file_check(filepath, language, rules)
    if lang is None or rules is None or content is None or lines is None:
        return CheckResult(
            file=str(filepath),
            issues=skip_issues,
            language=lang or "unknown",
            skipped=True,
        )

    issues = _run_all_checkers(filepath, content, lines, lang, rules, run_linters=run_linters)
    issues = _filter_suppressed_issues(filepath, issues, lines)
    issues = _apply_context_role(filepath, issues)

    if semantic:
        issues.extend(_run_semantic_checks(filepath, lang))

    return CheckResult(
        file=str(filepath),
        issues=issues,
        language=lang,
    )


def _check_file_skip_conditions(filepath: Path, language: str | None) -> CheckResult | None:
    """检查文件跳过条件, 返回 CheckResult 若应跳过, 否则 None."""
    if not filepath.exists():
        return _file_not_found_result(filepath)

    if filepath.stat().st_size == 0:
        return CheckResult(
            file=str(filepath),
            issues=[],
            language=filepath.suffix.lower().lstrip("."),
            skipped=True,
        )
    return None


def _prepare_file_check(
    filepath: Path, language: str | None, rules: dict[str, Any] | None
) -> tuple[str | None, dict[str, Any] | None, str | None, list[str] | None, list[Issue]]:
    """准备检查所需的语言、规则、内容、行列表, 以及"跳过原因"对应的 issue.

    content/lines 为 None 表示文件无法安全解析 (非UTF-8), 调用方须按 skipped 处理。

    第 5 个通道承载跳过本身的可见记录。skipped 若不携带任何 issue, 门禁无法区分
    "该文件无需检查" 与 "该文件检查失败" —— 后者被呈现为 passed 即 fail-open,
    与 ADR-074/076/078 同一族缺陷。
    """
    lang = language or _detect_language(filepath)
    if lang == "unknown":
        return None, None, "", [], []

    if rules is None:
        rules = load_rules_for_language(lang)

    try:
        # utf-8-sig 而非 utf-8: 后者不剥离 BOM, 导致文件首行的 ^ 锚点规则全部失效。
        content = filepath.read_text(encoding="utf-8-sig")
    except UnicodeDecodeError as exc:
        # 该文件属于受支持语言, 却读不出来 —— 语义上它是"检查失败"而非"无需检查"。
        # 必须留痕, 否则 check_file 返回 skipped=True 且零 issue, 门禁无从察觉。
        logger.warning(f"跳过非 UTF-8 文件 (无法安全解析): {filepath}")
        return lang, rules, None, None, [_undecodable_file_issue(filepath, exc)]

    lines = content.splitlines()
    return lang, rules, content, lines, []


def _apply_context_role(filepath: Path, issues: list[Issue]) -> list[Issue]:
    """应用上下文角色调整严重度."""
    ctx_markers = _load_context_markers(filepath.parent)
    file_role = detect_file_role(filepath, ctx_markers)
    if file_role:
        for issue in issues:
            issue.context_role = file_role
            issue.severity = adjust_severity(issue.severity, file_role)
    return issues


def _undecodable_file_issue(filepath: Path, exc: UnicodeDecodeError) -> Issue:
    """Create the Issue recorded when a supported-language file cannot be decoded."""
    return Issue(
        file=str(filepath),
        line=0,
        column=0,
        severity="error",
        category="io",
        rule_id="file-decode-error",
        message=f"File could not be decoded as UTF-8, so it was not checked: {exc}",
        fix_hint="Re-save the file as UTF-8, or exclude it from the checked paths",
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
    filepath: Path,
    content: str,
    lines: list[str],
    lang: str,
    rules: dict[str, Any],
    run_linters: bool = True,
) -> list[Issue]:
    """Run all checkers on file content."""
    issues: list[Issue] = []

    # Anti-patterns (传入已读的 content/lines, 避免对同一文件重复读盘)
    issues.extend(check_anti_patterns(filepath, lang, rules, content=content, lines=lines))

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
            # Plugin failed - log at debug level so bugs are visible without
            # breaking the pipeline (CLI 工具 best-effort 模式).
            logger.debug("Plugin {} failed on {}: {}", plugin.__class__.__name__, filepath, exc_info=True)

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
        except Exception as exc:
            logger.debug(f"框架规则加载失败 {framework}: {exc}")

    try:
        from .rule_loader import load_domain_rules

        domain_rules = load_domain_rules(dirpath)
        if domain_rules.get("anti_patterns"):
            if rules:
                from .rule_loader import _merge_rules

                rules = _merge_rules(rules, domain_rules)
            else:
                rules = domain_rules
    except Exception as exc:
        logger.debug(f"域规则加载失败: {exc}")

    return rules


def _discover_target_files(dirpath: Path, languages: list[str] | None) -> list[Path]:
    """发现目录下所有可检查文件，按扩展名 + 排除目录 + 语言过滤。

    ADR-014: 从 check_directory 拆出。
    """
    exts = {
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
    }
    # 性能: 遍历中就地剪枝排除目录 —— rglob("*") 不剪枝，会把 .venv/.git/node_modules
    # 一并枚举（仓库根实测 22755 路径，0.82s）。共享 _common.walk_files 统一实现。
    files = [
        path
        for path in walk_files(dirpath, skip_dir=lambda name: name in DEFAULT_EXCLUDED_DIRS)
        if path.suffix.lower() in exts
    ]

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
        except Exception as exc:  # noqa: BLE001 - 缓存库不可用属可降级故障，本次退化为完整检查
            store = None
            logger.warning(f"增量缓存初始化失败，本次退化为完整检查: {type(exc).__name__}: {exc}")
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
    except ImportError as exc:
        logger.debug(f"arch 模块不可用: {exc}")
    except Exception as exc:
        logger.debug(f"arch 检查失败: {exc}")
    return results


def _check_with_cache(
    filepath: Path,
    lang: str,
    rules: dict[str, Any] | None,
    store: CheckStore | None,
    rules_hash: str,
    semantic: bool,
    run_linters: bool,
    commit: bool = True,
) -> tuple[CheckResult, bool, bool | None]:
    """单文件检查（带缓存），返回 (CheckResult, cache_degraded, cache_hit)。

    cache_hit: True 命中缓存，False 未命中/未使用缓存路径，None 缓存未启用。
    ADR-014: 从 check_directory 拆出 cache logic。store=None 时退化为完整检查。
    """
    cache_degraded = False
    cache_enabled = store is not None
    # semantic / run_linters 会改变结果却不在 store 的键里 (键仅 file+mtime+size+rules_hash),
    # 导致 run_linters=False 跑出的无 linter 结果会被后续 run_linters=True 复用并静默丢失
    # 全部 linter 问题。两者并入签名, 无需改表结构。
    cache_signature = f"{rules_hash}:s{int(semantic)}:l{int(run_linters)}"
    if store is not None:
        try:
            stat = filepath.stat()
            cached = store.get_cached_result(str(filepath), stat.st_mtime, stat.st_size, cache_signature)
            if cached is not None:
                issues = [Issue(**i) for i in cached["issues"]]
                return (
                    CheckResult(file=str(filepath), issues=issues, language=cached["language"]),
                    False,
                    True,
                )
        except Exception as exc:  # noqa: BLE001 - 缓存条目损坏时重算，不影响检查结论
            cache_degraded = True
            logger.debug(f"缓存读取失败，回退完整检查 {filepath}: {exc}")
    result = check_file(filepath, rules, lang, semantic=semantic, run_linters=run_linters)
    if store is not None and not result.skipped:
        try:
            stat = filepath.stat()
            store.set_cached_result(
                str(filepath),
                stat.st_mtime,
                stat.st_size,
                _result_payload(result),
                cache_signature,
                commit=commit,
            )
        except Exception as exc:  # noqa: BLE001 - 缓存写入失败仅丢性能，检查结论已得出
            cache_degraded = True
            logger.debug(f"缓存写入失败（不影响检查结果）{filepath}: {exc}")
    return result, cache_degraded, (False if cache_enabled else None)


def _result_payload(result: CheckResult) -> dict[str, Any]:
    """CheckResult →缓存表行负载。"""
    return {
        "language": result.language,
        "passed": result.passed,
        "errors": result.error_count,
        "warnings": result.warning_count,
        "info": result.info_count,
        "issues": [i.to_dict() for i in result.issues],
    }


def _check_files_serial(
    files: list[Path],
    rules: dict[str, Any] | None,
    store: CheckStore | None,
    rules_hash: str,
    semantic: bool,
    run_linters: bool,
) -> tuple[list[CheckResult], int, dict[str, int | None]]:
    """串行检查（小集合 jobs<=1 或 files<=4）。

    返回 (results, cache_degraded, cache_stats)。
    ADR-014: 从 check_directory 拆出。
    """
    results: list[CheckResult] = []
    degraded = 0
    hits = 0
    misses = 0
    with _batched_linters(files, run_linters):
        for filepath in files:
            result, was_degraded, cache_hit = _check_with_cache(
                filepath,
                _detect_language(filepath),
                rules,
                store,
                rules_hash,
                semantic,
                run_linters,
                commit=False,
            )
            if was_degraded:
                degraded += 1
            if cache_hit is True:
                hits += 1
            elif cache_hit is False:
                misses += 1
            # Phase 33b-13 fix (ADR-053): 不再静默过滤 skipped 文件, 让 report_generator 输出 notApplicable
            results.append(result)
        if store is not None:
            store.commit()
    return results, degraded, {"cache_hits": hits, "cache_misses": misses}


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
) -> tuple[list[CheckResult], int, dict[str, int | None]]:
    """并行检查（ProcessPoolExecutor + worker 缓存）。

    返回 (results, cache_degraded, cache_stats)，与 _check_files_serial 对齐。
    cache_stats: cache_hits/cache_misses；未启用缓存时返回 0/0（无缓存操作）。

    ADR-014: 从 check_directory 拆出。worker 进程各自独立 SQLite 连接，
    WAL 模式下并发写安全。
    """
    from collections.abc import Iterator
    from concurrent.futures import ProcessPoolExecutor

    warmup_rules = rules or {}
    pairs = [(fp, _detect_language(fp)) for fp in files]
    cache_db: str | None = str(db_path) if use_cache and store is not None else None
    # 与串行路径 _check_with_cache 保持一致: 缓存键必须包含 semantic / run_linters,
    # 否则 jobs>1 + use_cache=True 时仍会复用另一组标志跑出的结果。
    worker_rules_hash = f"{rules_hash}:s{int(semantic)}:l{int(run_linters)}"
    results: list[CheckResult] = []
    degraded = 0
    hits = 0
    misses = 0
    cache_enabled = cache_db is not None
    # 合并进同一个 with: prime 必须发生在进程池创建之前 (worker 经 fork 继承该表,
    # 子进程内不再 spawn)。非 fork 启动方式下 worker 拿不到表, 自动回退逐文件 spawn。
    with (
        _batched_linters(files, run_linters),
        ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(warmup_rules, cache_db)) as executor,
    ):
        worker_results: Iterator[tuple[CheckResult | None, int, bool | None]] = executor.map(
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
                if worker_result is None:
                    # 向后兼容：异常/旧协议意外返回 None
                    degraded += 1
                    misses += 1 if cache_enabled else 0
                    continue
                result, was_degraded, cache_hit = worker_result
                degraded += int(was_degraded or 0)
                if result is not None:
                    results.append(result)
                if cache_hit is True:
                    hits += 1
                elif cache_hit is False:
                    misses += 1
            except Exception as exc:
                logger.debug(f"worker 结果处理失败: {exc}")
                degraded += 1
    return results, degraded, {"cache_hits": hits, "cache_misses": misses}


def check_directory(
    dirpath: Path,
    rules: dict[str, Any] | None = None,
    languages: list[str] | None = None,
    jobs: int | None = None,
    semantic: bool = False,
    run_linters: bool = True,
    use_cache: bool = False,
    db_path: str | Path = "adg_quality.db",
    stats: dict[str, Any] | None = None,
) -> list[CheckResult]:
    """Check all files in a directory.

    Args:
        dirpath: Directory to check.
        rules: Rules dict. Auto-loaded if None.
        languages: Filter to these languages only.
        jobs: Number of parallel workers (None/<=0 = use configured default from [tool.adg] jobs, default 4).
        semantic: Enable AST-based semantic analysis.
        run_linters: Run external linters (ruff/eslint) per file.
        use_cache: 启用增量缓存（mtime+size 未变则复用上次结果）。
        db_path: 统一存储数据库路径（use_cache=True 时使用）。
        stats: 可选出参，填充可观测统计（files_checked/use_cache/cache_* 等）；未启用缓存时 cache 计数为 null。
    """
    results: list[CheckResult] = []

    if not dirpath.exists() or not dirpath.is_dir():
        if stats is not None:
            stats.clear()
            stats.update(
                {
                    "files_checked": 0,
                    "use_cache": bool(use_cache),
                    "cache_supported": True,
                    "cache_engine": CACHE_ENGINE_ID,
                    "cache_reason": None if use_cache else CACHE_REASON_DISABLED,
                    "cache_initialized": False,
                    "cache_degraded": None,
                    "cache_hits": None,
                    "cache_misses": None,
                    "cache_hit_rate": None,
                    "parallel": False,
                    "jobs": 0,
                }
            )
        return results

    rules = _load_directory_rules(dirpath, rules)
    files = _discover_target_files(dirpath, languages)
    store, rules_hash = _init_cache_store(use_cache, db_path)

    # P-01: jobs 未显式指定时回退到 [tool.adg] jobs 配置（默认 4），
    # 避免 CLI 默认 jobs=1 导致目录级检查始终串行。
    effective_jobs = jobs if jobs and jobs > 0 else int(str(get_setting("jobs", default=4) or 4))
    effective_jobs = max(1, effective_jobs)

    cache_stats: dict[str, int | None] = {"cache_hits": None, "cache_misses": None}
    parallel = False
    if len(files) <= 4 or effective_jobs <= 1:
        checked, cache_degraded, cache_stats = _check_files_serial(
            files, rules, store, rules_hash, semantic, run_linters
        )
    else:
        parallel = True
        checked, cache_degraded, cache_stats = _check_files_parallel(
            files, rules, store, rules_hash, db_path, use_cache, semantic, run_linters, effective_jobs
        )

    results.extend(checked)
    results.extend(_run_architecture_analysis(dirpath))

    if use_cache and cache_degraded:
        logger.warning(f"本次运行缓存降级 {cache_degraded} 次（读取/写入失败已回退完整检查）")

    if stats is not None:
        hits = cache_stats.get("cache_hits")
        misses = cache_stats.get("cache_misses")
        cache_degraded_out: int | None = cache_degraded
        # 缓存未启用时返回 null，不臆造 0；并行/串行在启用缓存时返回 worker 聚合的真实计数
        if not use_cache:
            hits = None
            misses = None
            cache_degraded_out = None
        stats.clear()
        stats.update(
            {
                "files_checked": len(files),
                "use_cache": bool(use_cache),
                "cache_supported": True,
                "cache_engine": CACHE_ENGINE_ID,
                "cache_reason": None if use_cache else CACHE_REASON_DISABLED,
                "cache_initialized": store is not None,
                "cache_degraded": cache_degraded_out,
                "cache_hits": hits,
                "cache_misses": misses,
                "cache_hit_rate": _cache_hit_rate(hits, misses),
                "parallel": parallel,
                "jobs": effective_jobs,
            }
        )

    return results


def _run_semantic_checks(filepath: Path, lang: str) -> list[Issue]:
    """Run AST-based semantic analysis on a file.

    Uses tree-sitter for accurate syntax tree analysis instead of regex.
    通过语义规则插件系统执行检查（见 semantic_rules.py），
    新增规则只需注册 SemanticRule，无需修改本模块。

    降级可见性（ADR-064）：tree-sitter 不可用时**不得静默返回空列表**。
    旧实现直接 `return issues`（空），调用方无法区分"检查通过"与
    "检查根本没跑" —— 实测缺失时 SemanticChecker 报 0 个问题，
    而依赖齐全时报 54 个，输出看起来像"代码完美"。现在统一产生一条
    ``semantic-degraded`` error Issue（严重度理由见 _degraded_issue）。
    """
    issues: list[Issue] = []

    try:
        from .ast_parser import get_parser
        from .semantic_rules import run_semantic_rules

        parser = get_parser()
        if not parser.available:
            return [_degraded_issue(filepath, "tree-sitter 未安装")]

        ast_result = parser.parse_file(filepath, lang)
        if ast_result is None:
            # 区分两种 None：解析器缺失 vs 真正解析失败
            # 用公开属性 supported_languages()，不碰私有 _parsers
            if lang not in parser.supported_languages():
                return [_degraded_issue(filepath, f"tree-sitter 的 {lang} 解析器不可用")]
            return [_degraded_issue(filepath, f"{lang} 文件解析失败")]

        # 运行所有匹配语言的语义规则插件
        issues.extend(run_semantic_rules(ast_result, filepath, lang))

    except ImportError as exc:
        return [_degraded_issue(filepath, f"语义检查依赖缺失: {exc}")]
    except Exception as exc:  # noqa: BLE001 - 语义插件异常不中断管道，但降级为可见 Issue
        # 不中断检查管道，但必须留痕（原先 `pass` 会完全静默）
        return [_degraded_issue(filepath, f"语义分析异常: {type(exc).__name__}: {exc}")]

    return issues


def _degraded_issue(filepath: Path, reason: str) -> Issue:
    """语义检查降级时产生的可见 Issue。

    ADR-064: 严重度取 ``error`` 而非 info/warning。实测
    ``CheckResult.passed`` 只看 ``error_count``（models.py:121），实测
    info 与 warning 都会被 report_generator / quality_gate 渲染成
    "PASS ✅" —— 等于把"检查根本没跑"重新伪装成绿灯，正是本 ADR
    要根除的假绿灯。

    取 error 不会误伤常规门禁：全仓仅 ``phase_runner._run_semantic_check``
    以 ``semantic=True`` 调用检查器，且 ``.jcode/hooks.json`` 无任何 hook
    触发 semantic-check（已核验 on_commit/on_pr/on_merge/scheduled）。
    即"显式要求语义检查却没跑成"才会触发 error，属于名副其实的错误。
    """
    return Issue(
        rule_id="semantic-degraded",
        severity="error",
        category="infrastructure",
        file=str(filepath),
        line=0,
        message=f"AST 语义检查未执行: {reason}（本文件的语义规则未被检查）",
        fix_hint="安装可选依赖后重试: uv pip install 'tree-sitter' 'tree-sitter-<lang>'",
        explanation=(
            "语义检查依赖 tree-sitter。缺失时不会报错，但相关规则"
            "（未使用导入、缺 docstring、复杂度等）实际上一条都没跑。"
        ),
    )

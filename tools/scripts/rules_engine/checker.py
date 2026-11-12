"""Main rules engine orchestrator - coordinates all checkers."""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import TYPE_CHECKING, Any

from tools.scripts._common import rules_dir, walk_files
from tools.scripts.app_config import get_setting
from tools.scripts.rules_engine.logger import logger

from ._checker_file import _apply_context_role as _apply_context_role
from ._checker_file import _check_file_skip_conditions as _check_file_skip_conditions
from ._checker_file import _degraded_issue as _degraded_issue
from ._checker_file import _file_not_found_result as _file_not_found_result
from ._checker_file import _prepare_file_check as _prepare_file_check
from ._checker_file import _run_all_checkers as _run_all_checkers
from ._checker_file import _run_semantic_checks as _run_semantic_checks
from ._checker_file import _undecodable_file_issue as _undecodable_file_issue
from ._checker_file import check_file as check_file
from ._checker_linters import _batched_linters as _batched_linters
from ._checker_linters import _map_severity as _map_severity
from ._checker_linters import _parse_linter_output as _parse_linter_output
from ._checker_markers import DEFAULT_EXCLUDED_DIRS as DEFAULT_EXCLUDED_DIRS
from ._checker_markers import FRAMEWORK_DETECTORS as FRAMEWORK_DETECTORS
from ._checker_markers import _check_marker as _check_marker
from ._checker_markers import _check_package_json as _check_package_json
from ._checker_markers import _check_text_contains as _check_text_contains
from ._checker_markers import _config_excluded_dirs as _config_excluded_dirs
from ._checker_markers import _detect_framework as _detect_framework
from ._checker_markers import _detect_language as _detect_language
from ._checker_noqa import _filter_suppressed_issues as _filter_suppressed_issues
from ._checker_noqa import _is_issue_suppressed as _is_issue_suppressed
from ._checker_noqa import _load_ignored_rules as _load_ignored_rules
from ._checker_noqa import _parse_noqa_lines as _parse_noqa_lines
from .models import CheckResult, Issue
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
    # 延迟导入 worker 模块: worker 需要 checker.check_file, 而 checker 在模块级
    # 导入 worker 就成环 (checker → _checker_workers → checker)。
    # 改为在真正要开进程池时再导入, 依赖方向单一。
    from ._checker_workers import _worker_check, _worker_init

    # 合并进同一个 with: prime 必须发生在进程池创建之前 (worker 经 fork 继承该表,
    # 子进程内不再 spawn)。非 fork 启动方式下 worker 拿不到表, 自动回退逐文件 spawn。
    # 这里用 ExitStack 而不是括号化 with (PEP 3.10+): parso 0.8.7 (mutmut 2.x 的
    # 依赖) 无法解析 `with (a, b as c):`, 变异测试会在解析阶段直接失败。
    with contextlib.ExitStack() as stack:
        stack.enter_context(_batched_linters(files, run_linters))
        executor = stack.enter_context(
            ProcessPoolExecutor(max_workers=jobs, initializer=_worker_init, initargs=(warmup_rules, cache_db))
        )
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

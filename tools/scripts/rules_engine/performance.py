"""Performance optimization module for the rules engine.

Provides incremental checking, parallel processing, caching,
and scan time optimization.

.. deprecated:: 现状说明（2026-08 核实）
    本模块当前无生产调用方：仅 perf_benchmark.py（基准工具）与
    测试引用。生产路径的增量缓存由 checker.check_directory(use_cache=True)
    + store.CheckStore 提供，并行执行也内置于 check_directory。
    本模块保留用于基准对比实验；若确认不再需要可整体移除。
    请勿在文档中声称其为生产加速组件。

Usage:
    from tools.scripts.rules_engine.performance import PerformanceOptimizer

    optimizer = PerformanceOptimizer()
    results = optimizer.optimized_check_directory(dirpath)
"""

from __future__ import annotations

import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tools.scripts._common import file_hash_full


@dataclass
class CacheEntry:
    """Cached analysis result for a file."""

    file_hash: str
    result: dict[str, Any]
    timestamp: float
    size: int


@dataclass
class PerformanceMetrics:
    """Performance metrics for a scan."""

    total_files: int
    cached_files: int
    new_files: int
    changed_files: int
    scan_time_ms: float
    cache_hit_rate: float
    files_per_second: float
    avg_ms_per_file: float
    parallel_workers: int
    peak_memory_mb: float


class FileCache:
    """LRU cache for file analysis results."""

    def __init__(self, max_entries: int = 10000, cache_dir: Path | None = None) -> None:
        self.max_entries = max_entries
        self.cache_dir = cache_dir or Path.home() / ".cache" / "adg" / "analysis"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self._memory_cache: dict[str, CacheEntry] = {}
        self._load_disk_cache()

    def _load_disk_cache(self) -> None:
        """Load cache entries from disk."""
        cache_index = self.cache_dir / "index.txt"
        if not cache_index.exists():
            return

        try:
            for line in cache_index.read_text().splitlines()[: self.max_entries]:
                parts = line.strip().split("|")
                if len(parts) == 4:
                    filepath, file_hash, timestamp, size = parts
                    cache_file = self.cache_dir / f"{file_hash}.cache"
                    if cache_file.exists():
                        import json

                        try:
                            result = json.loads(cache_file.read_text())
                            self._memory_cache[filepath] = CacheEntry(
                                file_hash=file_hash,
                                result=result,
                                timestamp=float(timestamp),
                                size=int(size),
                            )
                        except (ValueError, OSError):
                            pass  # cache entry invalid
        except (OSError, json.JSONDecodeError):
            pass  # cache load error

    def get(self, filepath: str) -> dict[str, Any] | None:
        """Get cached result for a file."""
        entry = self._memory_cache.get(filepath)
        if entry is None:
            return None

        # Check if file has changed
        try:
            os.stat(filepath)
            current_hash = file_hash_full(Path(filepath))
            if current_hash != entry.file_hash:
                del self._memory_cache[filepath]
                return None
        except OSError:
            return None

        return entry.result

    def set(self, filepath: str, result: dict[str, Any]) -> None:
        """Cache a result for a file."""
        try:
            stat = os.stat(filepath)
            file_hash = file_hash_full(Path(filepath))
            entry = CacheEntry(
                file_hash=file_hash,
                result=result,
                timestamp=time.time(),
                size=stat.st_size,
            )
            self._memory_cache[filepath] = entry

            # Evict if over limit
            if len(self._memory_cache) > self.max_entries:
                oldest_key = min(self._memory_cache, key=lambda k: self._memory_cache[k].timestamp)
                del self._memory_cache[oldest_key]
        except OSError:
            pass  # stat failed

    def save(self) -> None:
        """Persist cache to disk."""
        import json

        cache_index = self.cache_dir / "index.txt"
        lines: list[str] = []

        for filepath, entry in self._memory_cache.items():
            lines.append(f"{filepath}|{entry.file_hash}|{entry.timestamp}|{entry.size}")

            cache_file = self.cache_dir / f"{entry.file_hash}.cache"
            try:
                cache_file.write_text(json.dumps(entry.result))
            except (OSError, TypeError):
                pass  # write cache failed

        try:
            cache_index.write_text("\n".join(lines[: self.max_entries]))
        except OSError:
            pass  # cache write failed

    def clear(self) -> None:
        """Clear the cache."""
        self._memory_cache.clear()
        import shutil

        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        total_size = sum(e.size for e in self._memory_cache.values())
        return {
            "entries": len(self._memory_cache),
            "total_size_mb": total_size / (1024 * 1024),
            "max_entries": self.max_entries,
        }

    @staticmethod
    def _check_file_worker(args: tuple[str, str | None]) -> dict[str, Any] | None:
        """Worker function for parallel file checking.

        注意: 下面 ``except (AttributeError, OSError) -> None`` 是一个
        **fail-open** 分支 (失败被吐成 None, 父进程只会把它剔除)。自
        ADR-074/076 起, 父进程两条路径都会把这种 None 记入
        ``failed_files``, 因此本分支**不再是静默的**。

        保留它的理由: ``return None`` 是既有返回契约的一部分, 上层
        ``optimized_check_directory`` 依赖 ``None`` 过滤。彻底删掉会
        改变行为而非修复问题。

        已逐条证伪的触发源 (勿重复排查, 详见 CONTEXT.md):
        fork 后惰性 import 触发 AttributeError、外部 ruff 子进程失败、
        生成规则目录读取、共享配置被删导致的 FileNotFoundError、
        fd 耗尽 (EMFILE) —— 五项实测均无法让本分支触发。
        """
        filepath, language = args
        try:
            from pathlib import Path

            from tools.scripts.rules_engine.checker import check_file

            result = check_file(Path(filepath), language=language)
            return {
                "file": filepath,
                "issues": [{"rule_id": i.rule_id, "severity": i.severity, "message": i.message} for i in result.issues],
                "language": result.language,
                "skipped": result.skipped,
            }
        except (AttributeError, OSError):
            return None


class PerformanceOptimizer:
    """Performance optimization for code analysis."""

    def __init__(self, max_workers: int | None = None, cache_enabled: bool = True) -> None:
        self.max_workers = max_workers or min(os.cpu_count() or 4, 8)
        self.cache = FileCache() if cache_enabled else None
        # worker 失败记录: filepath -> 原因。用于识别"静默没检查到"的文件,
        # 避免与"检查通过"混淆 (ADR-074)。
        self.failed_files: dict[str, str] = {}
        self._metrics = PerformanceMetrics(
            total_files=0,
            cached_files=0,
            new_files=0,
            changed_files=0,
            scan_time_ms=0,
            cache_hit_rate=0,
            files_per_second=0,
            avg_ms_per_file=0,
            parallel_workers=self.max_workers,
            peak_memory_mb=0,
        )

    @property
    def metrics(self) -> PerformanceMetrics:
        """Get the last scan's performance metrics."""
        return self._metrics

    def diagnostics(self) -> dict[str, Any]:
        """返回 JSON 可序列化诊断信息（Phase 2.3/3 可观测性）。"""
        m = self._metrics
        return {
            "cache": {
                "enabled": self.cache is not None,
                "cached_files": m.cached_files,
                "cache_hit_rate": m.cache_hit_rate,
                "new_files": m.new_files,
            },
            "failed_files": dict(self.failed_files),
            "failed_count": len(self.failed_files),
            "total_files": m.total_files,
            "scan_time_ms": m.scan_time_ms,
        }

    def optimized_check_directory(
        self,
        dirpath: Path,
        languages: list[str] | None = None,
        incremental: bool = True,
        parallel: bool = True,
    ) -> list[dict[str, Any]]:
        """Optimized directory checking with caching and parallelism (V2.21 P5-48 拆分: 抽 _partition_files + _run_checks_parallel_or_serial + _build_metrics)."""
        start_time = time.monotonic()

        # 每次扫描前清空, 避免上一轮的失败记录污染本轮判定。
        self.failed_files = {}

        source_files = self._collect_files(dirpath, languages)
        total_files = len(source_files)

        files_to_check, cached_results, cached_count = self._partition_files(source_files, incremental)

        new_files = len(files_to_check)
        results = self._run_checks_parallel_or_serial(files_to_check, parallel)

        # Update cache
        if self.cache:
            for result in results:
                if result is not None:
                    self.cache.set(result["file"], result)
            self.cache.save()

        scan_time = (time.monotonic() - start_time) * 1000
        all_results = cached_results + [r for r in results if r is not None]
        self._metrics = self._build_metrics(total_files, cached_count, new_files, scan_time, parallel)
        return all_results

    def _partition_files(
        self, source_files: list[Path], incremental: bool
    ) -> tuple[list[tuple[str, str | None]], list[dict[str, Any]], int]:
        """分离 cached 和 uncached 文件 (方法级 helper).

        Args:
            source_files: 待扫描文件列表
            incremental: 是否使用 cache

        Returns:
            (files_to_check, cached_results, cached_count) 三元组
        """
        files_to_check: list[tuple[str, str | None]] = []
        cached_results: list[dict[str, Any]] = []
        cached_count = 0
        if incremental and self.cache:
            for filepath in source_files:
                str_path = str(filepath)
                cached = self.cache.get(str_path)
                if cached is not None:
                    cached_results.append(cached)
                    cached_count += 1
                else:
                    language = self._detect_language(filepath)
                    files_to_check.append((str_path, language))
        else:
            for filepath in source_files:
                str_path = str(filepath)
                language = self._detect_language(filepath)
                files_to_check.append((str_path, language))
        return files_to_check, cached_results, cached_count

    def _run_checks_parallel_or_serial(
        self, files_to_check: list[tuple[str, str | None]], parallel: bool
    ) -> list[dict[str, Any] | None]:
        """根据 parallel 和 new_files 数量分派 parallel or serial 检查 (方法级 helper).

        Args:
            files_to_check: 待检查文件
            parallel: 是否并行

        Returns:
            检查结果列表
        """
        if parallel and len(files_to_check) > 4:
            return self._parallel_check(files_to_check)
        return self._serial_check(files_to_check)

    def _build_metrics(
        self,
        total_files: int,
        cached_count: int,
        new_files: int,
        scan_time: float,
        parallel: bool,
    ) -> PerformanceMetrics:
        """构造 PerformanceMetrics (方法级 helper).

        Args:
            total_files: 总文件数
            cached_count: 命中缓存数
            new_files: 新文件数
            scan_time: 扫描时间 ms
            parallel: 是否并行

        Returns:
            PerformanceMetrics 实例
        """
        return PerformanceMetrics(
            total_files=total_files,
            cached_files=cached_count,
            new_files=new_files,
            changed_files=new_files - cached_count if total_files > 0 else 0,
            scan_time_ms=scan_time,
            cache_hit_rate=cached_count / total_files if total_files > 0 else 0,
            files_per_second=total_files / (scan_time / 1000) if scan_time > 0 else 0,
            avg_ms_per_file=scan_time / total_files if total_files > 0 else 0,
            parallel_workers=self.max_workers if parallel else 1,
            peak_memory_mb=self._get_memory_usage(),
        )

    def _parallel_check(self, files: list[tuple[str, str | None]]) -> list[dict[str, Any] | None]:
        """Run checks in parallel using ProcessPoolExecutor.

        worker 失败时**不静默丢弃**: 保留 None 占位 (维持既有返回契约,
        ``optimized_check_directory`` 仍会过滤), 但同时把失败原因记入
        ``self.failed_files``, 使调用方能区分"检查通过"与"没检查到"。

        ADR-076: 必须覆盖 worker **正常返回 None** 的情形。原先只处理了
        "抛异常" 分支, 而 ``_check_file_worker`` 内部会把
        ``AttributeError`` / ``OSError`` 吞掉后返回 None —— 那是更常见的
        失败形态, 却是静默的。实测对比:
            并行: 结果数 4, failed_files 为空   ← 无任何线索
            串行: 结果数 4, failed_files 有记录
        即 ADR-074 只修了一半, 与串行路径行为不一致。
        """
        results: list[dict[str, Any] | None] = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(FileCache._check_file_worker, f): f[0] for f in files}
            for future in as_completed(future_to_file):
                filepath = future_to_file[future]
                try:
                    result = future.result()
                except Exception as exc:  # noqa: BLE001 — 必须捕获, 否则整批丢失
                    # 关键: 不再把失败伪装成 None 后无声消失。None 占位仍在,
                    # 但失败原因与文件路径被记录, 调用方可据此判定 fail-open。
                    self.failed_files[filepath] = f"{type(exc).__name__}: {exc}"
                    results.append(None)
                    continue

                # ADR-076: 返回 None 与抛异常同样是"没检查到", 同样要留痕。
                # 否则该文件被上层静默剔除, 而 failed_files 空着 —— 调用方
                # 只看到结果数变少, 无从判断是漏收还是失败。
                if result is None:
                    self.failed_files[filepath] = "worker returned None (check_file raised or file unreadable)"
                results.append(result)

        return results

    def _serial_check(self, files: list[tuple[str, str | None]]) -> list[dict[str, Any] | None]:
        """Run checks serially."""
        results: list[dict[str, Any] | None] = []
        for filepath, language in files:
            result = FileCache._check_file_worker((filepath, language))
            if result is None:
                # worker 内部已吞掉 AttributeError/OSError (见 _check_file_worker),
                # 这里补记, 否则串行路径与并行路径一样会静默少结果。
                self.failed_files[filepath] = "worker returned None (check_file raised or file unreadable)"
            results.append(result)
        return results

    def _collect_files(self, dirpath: Path, languages: list[str] | None) -> list[Path]:
        """Collect source files for checking."""
        extensions = {
            "python": {".py"},
            "javascript": {".js", ".jsx"},
            "typescript": {".ts", ".tsx"},
            "rust": {".rs"},
            "go": {".go"},
            "java": {".java"},
        }

        if languages:
            exts: set[str] = set()
            for lang in languages:
                exts.update(extensions.get(lang, set()))
        else:
            exts = set()
            for ext_set in extensions.values():
                exts.update(ext_set)

        ignore_dirs = {
            "node_modules",
            ".git",
            "__pycache__",
            ".venv",
            "venv",
            "dist",
            "build",
            ".cache",
        }

        files: list[Path] = []
        for ext in exts:
            for filepath in dirpath.rglob(f"*{ext}"):
                if any(d in filepath.parts for d in ignore_dirs):
                    continue
                files.append(filepath)

        return sorted(files)[:10000]  # Cap at 10k files

    def _detect_language(self, filepath: Path) -> str:
        """Detect language from file extension."""
        ext_map = {
            ".py": "python",
            ".js": "javascript",
            ".jsx": "javascript",
            ".ts": "typescript",
            ".tsx": "typescript",
            ".rs": "rust",
            ".go": "go",
            ".java": "java",
        }
        return ext_map.get(filepath.suffix.lower(), "unknown")

    @staticmethod
    def _get_memory_usage() -> float:
        """Get current memory usage in MB."""
        try:
            import resource

            usage = resource.getrusage(resource.RUSAGE_SELF)
            return usage.ru_maxrss / 1024  # Convert to MB
        except (AttributeError, OSError):
            return 0.0

    def format_metrics(self) -> str:
        """Format performance metrics as human-readable text."""
        m = self._metrics
        lines = [
            "Performance Metrics",
            "=" * 50,
            f"Total files: {m.total_files}",
            f"Cached files: {m.cached_files} ({m.cache_hit_rate:.1%} hit rate)",
            f"New/changed files: {m.new_files}",
            f"Scan time: {m.scan_time_ms:.0f}ms",
            f"Throughput: {m.files_per_second:.1f} files/sec",
            f"Avg per file: {m.avg_ms_per_file:.1f}ms",
            f"Parallel workers: {m.parallel_workers}",
            f"Peak memory: {m.peak_memory_mb:.1f}MB",
        ]
        return "\n".join(lines)

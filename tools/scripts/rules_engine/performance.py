"""Performance optimization module for the rules engine.

Provides incremental checking, parallel processing, caching,
and scan time optimization.

Usage:
    from tools.scripts.rules_engine.performance import PerformanceOptimizer

    optimizer = PerformanceOptimizer()
    results = optimizer.optimized_check_directory(dirpath)
"""

from __future__ import annotations

import hashlib
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class CacheEntry:
    """Cached analysis result for a file."""

    file_hash: str
    result: Any
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
                        except Exception:
                            pass
        except Exception:
            pass

    def get(self, filepath: str) -> Any | None:
        """Get cached result for a file."""
        entry = self._memory_cache.get(filepath)
        if entry is None:
            return None

        # Check if file has changed
        try:
            os.stat(filepath)
            current_hash = self._file_hash(filepath)
            if current_hash != entry.file_hash:
                del self._memory_cache[filepath]
                return None
        except OSError:
            return None

        return entry.result

    def set(self, filepath: str, result: Any) -> None:
        """Cache a result for a file."""
        try:
            stat = os.stat(filepath)
            file_hash = self._file_hash(filepath)
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
            pass

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
            except Exception:
                pass

        try:
            cache_index.write_text("\n".join(lines[: self.max_entries]))
        except Exception:
            pass

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
    def _file_hash(filepath: str) -> str:
        """Calculate file hash for change detection."""
        h = hashlib.md5()  # nosec - used for file caching, not security
        try:
            with open(filepath, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    h.update(chunk)
        except OSError:
            return ""
        return h.hexdigest()


def _check_file_worker(args: tuple[str, str | None]) -> dict[str, Any] | None:
    """Worker function for parallel file checking."""
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
    except Exception:
        return None


class PerformanceOptimizer:
    """Performance optimization for code analysis."""

    def __init__(self, max_workers: int | None = None, cache_enabled: bool = True) -> None:
        self.max_workers = max_workers or min(os.cpu_count() or 4, 8)
        self.cache = FileCache() if cache_enabled else None
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

    def optimized_check_directory(
        self,
        dirpath: Path,
        languages: list[str] | None = None,
        incremental: bool = True,
        parallel: bool = True,
    ) -> list[dict[str, Any]]:
        """Optimized directory checking with caching and parallelism.

        Args:
            dirpath: Directory to check.
            languages: Filter to these languages.
            incremental: Use cache for unchanged files.
            parallel: Use parallel processing.

        Returns:
            List of check results.
        """
        start_time = time.monotonic()

        # Collect files
        source_files = self._collect_files(dirpath, languages)
        total_files = len(source_files)

        # Separate cached and uncached files
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

        new_files = len(files_to_check)

        # Run checks
        if parallel and new_files > 4:
            results = self._parallel_check(files_to_check)
        else:
            results = self._serial_check(files_to_check)

        # Update cache
        if self.cache:
            for result in results:
                if result is not None:
                    self.cache.set(result["file"], result)
            self.cache.save()

        # Calculate metrics
        scan_time = (time.monotonic() - start_time) * 1000
        all_results = cached_results + [r for r in results if r is not None]

        self._metrics = PerformanceMetrics(
            total_files=total_files,
            cached_files=cached_count,
            new_files=new_files,
            changed_files=new_files - cached_count if incremental else 0,
            scan_time_ms=scan_time,
            cache_hit_rate=cached_count / total_files if total_files > 0 else 0,
            files_per_second=total_files / (scan_time / 1000) if scan_time > 0 else 0,
            avg_ms_per_file=scan_time / total_files if total_files > 0 else 0,
            parallel_workers=self.max_workers if parallel else 1,
            peak_memory_mb=self._get_memory_usage(),
        )

        return all_results

    def _parallel_check(self, files: list[tuple[str, str | None]]) -> list[dict[str, Any] | None]:
        """Run checks in parallel using ProcessPoolExecutor."""
        results: list[dict[str, Any] | None] = []

        with ProcessPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_file = {executor.submit(_check_file_worker, f): f[0] for f in files}
            for future in as_completed(future_to_file):
                try:
                    result = future.result(timeout=30)
                    results.append(result)
                except Exception:
                    results.append(None)

        return results

    def _serial_check(self, files: list[tuple[str, str | None]]) -> list[dict[str, Any] | None]:
        """Run checks serially."""
        results: list[dict[str, Any] | None] = []
        for filepath, language in files:
            result = _check_file_worker((filepath, language))
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

        ignore_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".cache"}

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
        except Exception:
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

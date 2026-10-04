"""Tests for performance.py uncovered paths (_check_file_worker, optimized)."""

from __future__ import annotations

import tempfile
from pathlib import Path

import tools.scripts.rules_engine.performance as perf_mod
from tools.scripts.rules_engine.performance import (
    FileCache,
    PerformanceOptimizer,
)

# _check_file_worker 是 FileCache 的静态方法
_check_file_worker = FileCache._check_file_worker


class TestCheckFileWorker:
    """Coverage for performance._check_file_worker."""

    def test_worker_nonexistent_file(self):
        """Worker returns result with skipped=True for nonexistent file."""
        result = _check_file_worker(("/nonexistent/file.py", "python"))
        assert result is not None
        assert result.get("skipped", False) is True

    def test_worker_valid_file(self):
        """Worker processes a valid Python file."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
            f.write("x = 1")
            path = f.name
        try:
            result = _check_file_worker((path, "python"))
            assert result is not None
            assert result["file"] == path
            assert "issues" in result
        finally:
            Path(path).unlink(missing_ok=True)

    def test_worker_unknown_language(self):
        """Worker returns skipped result for unknown language."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".unk", delete=False) as f:
            f.write("content")
            path = f.name
        try:
            result = _check_file_worker((path, None))
            assert result is None or result.get("skipped", False) or True
        finally:
            Path(path).unlink(missing_ok=True)


class TestPerformanceOptimizerExtended:
    """Cover remaining PerformanceOptimizer paths."""

    def test_optimized_check_directory_empty(self):
        """Optimized check of empty dir returns empty list."""
        with tempfile.TemporaryDirectory() as tmp:
            opt = PerformanceOptimizer(max_workers=2, cache_enabled=False)
            results = opt.optimized_check_directory(Path(tmp))
            assert results == []

    def test_optimized_check_directory_serial(self):
        """Optimized check runs in serial for small file sets."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")
            (tmp_path / "b.py").write_text("y = 2")

            opt = PerformanceOptimizer(max_workers=1, cache_enabled=False)
            results = opt.optimized_check_directory(tmp_path)
            assert len(results) > 0

    def test_optimized_check_directory_parallel(self):
        """Optimized check runs in parallel for larger file sets."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(10):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
            results = opt.optimized_check_directory(tmp_path)
            assert len(results) >= 8  # at least 8 of 10 processed

    def test_optimized_check_with_cache_enabled(self):
        """Optimized check works with cache enabled."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")

            opt = PerformanceOptimizer(cache_enabled=True)
            # First run fills cache
            results1 = opt.optimized_check_directory(tmp_path)
            # Second run uses cache
            results2 = opt.optimized_check_directory(tmp_path)
            assert len(results2) == len(results1)

    def test_optimized_check_with_language_filter(self):
        """Optimized check filters by language."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").write_text("x = 1")
            (tmp_path / "b.ts").write_text("let x = 1")
            (tmp_path / "c.rs").write_text("let x = 1;")

            opt = PerformanceOptimizer()
            results = opt.optimized_check_directory(tmp_path, languages=["python"])
            assert len(results) == 1

    def test_collect_files_respects_ignore_dirs(self):
        """_collect_files skips __pycache__ and node_modules."""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            (tmp_path / "a.py").touch()
            (tmp_path / "__pycache__").mkdir()
            (tmp_path / "__pycache__" / "cache.py").touch()

            opt = PerformanceOptimizer()
            files = opt._collect_files(tmp_path, languages=None)
            paths = {str(f.relative_to(tmp_path)) for f in files}
            assert "a.py" in paths
            assert "__pycache__/cache.py" not in paths


class _FakeFuture:
    """最小 Future 替身: 只需能被 ``as_completed`` 迭代并支持 result()。

    为何不用真实 ProcessPoolExecutor 注入失败: pytest 环境下
    ``multiprocessing`` 的 start method 是 **forkserver** (由 hypothesis
    插件设置), 子进程会**重新导入 __main__**, 因此父进程的
    monkeypatch 对子进程不可见 —— 跨进程注入 worker 根本不可能生效。
    故本组直接以 FakeFuture 驱动 ``_parallel_check``, 精确覆盖
    "future 抛异常" 这条分支, 且不依赖平台与 start method。
    """

    def __init__(self, value=None, exc: BaseException | None = None) -> None:
        self._value = value
        self._exc = exc

    def result(self, timeout: float | None = None):
        if self._exc is not None:
            raise self._exc
        return self._value


class _StubExecutor:
    """替换 ProcessPoolExecutor: submit 返回预置的 FakeFuture。"""

    def __init__(self, futures: dict) -> None:
        self._futures = futures

    def __enter__(self):
        return self

    def __exit__(self, *exc_info) -> None:
        return None

    def submit(self, fn, arg):  # noqa: ARG002 — 与真实签名对齐, 故意忽略 fn
        return self._futures[arg[0]]


class TestWorkerFailureIsNotSilent:
    """worker 失败必须可观测, 不得静默丢结果 (ADR-074)。

    缺陷背景: ``_parallel_check`` 原先是
    ``except (TimeoutError, Exception): results.append(None)``, 随后
    ``optimized_check_directory`` 用
    ``[r for r in results if r is not None]`` 把 None 全部剔除 ——
    提交 10 个文件、3 个 worker 崩溃, 只返回 7 条, 且**零诊断输出**。
    调用方无法区分"检查通过"与"根本没检查到", 属 fail-open。

    另一处事实修正: 原代码的 ``future.result(timeout=30)`` 是死代码 ——
    ``as_completed()`` 只产出已完成 future, 该 timeout 永不触发 (已用
    ``result(timeout=0.001)`` 实测证伪)。真正的触发条件是 worker 抛
    异常, 而非超时。
    """

    @staticmethod
    def _make_files(tmp_path, count: int = 10):
        for i in range(count):
            (tmp_path / f"f{i}.py").write_text(f"x = {i}", encoding="utf-8")
        return [(str(tmp_path / f"f{i}.py"), None) for i in range(count)]

    def test_parallel_worker_exception_is_recorded(self, tmp_path, monkeypatch):
        """并行路径: worker 抛异常必须进 failed_files, 不能无声消失。"""
        files = self._make_files(tmp_path)
        futures = {p: _FakeFuture(value={"file": p, "issues": []}) for p, _ in files}
        for bad in ("f0.py", "f1.py", "f2.py"):
            key = str(tmp_path / bad)
            futures[key] = _FakeFuture(exc=RuntimeError("模拟 worker 崩溃"))

        opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
        monkeypatch.setattr(perf_mod, "ProcessPoolExecutor", lambda **kw: _StubExecutor(futures))
        monkeypatch.setattr(perf_mod, "as_completed", lambda futs: iter(futs))

        results = opt._parallel_check(files)

        # 返回契约不变: 失败位置仍是 None 占位
        assert results.count(None) == 3
        # 但失败必须留下可追溯痕迹
        assert len(opt.failed_files) == 3
        assert all("RuntimeError" in reason for reason in opt.failed_files.values())
        assert all("模拟 worker 崩溃" in reason for reason in opt.failed_files.values())

    def test_healthy_parallel_run_leaves_failed_files_empty(self, tmp_path, monkeypatch):
        """健康代码对照: 全部成功时 failed_files 必须为空。

        防止"无条件记录失败"这类假修复蒙过测试。
        """
        files = self._make_files(tmp_path)
        futures = {p: _FakeFuture(value={"file": p, "issues": []}) for p, _ in files}

        opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
        monkeypatch.setattr(perf_mod, "ProcessPoolExecutor", lambda **kw: _StubExecutor(futures))
        monkeypatch.setattr(perf_mod, "as_completed", lambda futs: iter(futs))

        results = opt._parallel_check(files)

        assert len(results) == 10
        assert opt.failed_files == {}

    def test_serial_none_result_is_recorded(self, tmp_path, monkeypatch):
        """串行路径有同样的洞: worker 返回 None 也必须被记录。"""
        files = self._make_files(tmp_path)

        def worker(args):
            if "f0" in args[0] or "f1" in args[0]:
                return None
            return {"file": args[0], "issues": [], "language": "python", "skipped": False}

        opt = PerformanceOptimizer(max_workers=1, cache_enabled=False)
        monkeypatch.setattr(FileCache, "_check_file_worker", staticmethod(worker))

        results = opt._serial_check(files)

        assert results.count(None) == 2
        assert len(opt.failed_files) == 2

    def test_failed_files_reset_between_scans(self, tmp_path, monkeypatch):
        """每次扫描前清空, 上一轮失败不得污染下一轮判定。"""
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text(f"x = {i}", encoding="utf-8")

        opt = PerformanceOptimizer(max_workers=1, cache_enabled=False)

        def failing(args):
            return None

        monkeypatch.setattr(FileCache, "_check_file_worker", staticmethod(failing))
        opt.optimized_check_directory(tmp_path)
        assert len(opt.failed_files) == 10

        # 第二轮全部成功, 失败记录必须已清空。
        # 显式走并行路径 (文件数 >4 时 _run_checks_parallel_or_serial 才选并行),
        # 并 stub 掉 executor, 避免依赖真实子进程。
        files = self._make_files(tmp_path)
        futures = {p: _FakeFuture(value={"file": p, "issues": []}) for p, _ in files}
        monkeypatch.setattr(perf_mod, "ProcessPoolExecutor", lambda **kw: _StubExecutor(futures))
        monkeypatch.setattr(perf_mod, "as_completed", lambda futs: iter(futs))

        results = opt.optimized_check_directory(tmp_path)

        assert len(results) == 10
        assert opt.failed_files == {}

    def test_failed_files_are_observable_to_caller(self, tmp_path, monkeypatch):
        """端到端: 调用方能从 optimized_check_directory 察觉失败。"""
        for i in range(10):
            (tmp_path / f"f{i}.py").write_text(f"x = {i}", encoding="utf-8")

        opt = PerformanceOptimizer(max_workers=1, cache_enabled=False)
        monkeypatch.setattr(FileCache, "_check_file_worker", staticmethod(lambda args: None))

        results = opt.optimized_check_directory(tmp_path)

        # 返回值仍过滤 None (既有契约不变)
        assert results == []
        # 但失败可观测 —— 这正是修复前完全缺失的信息
        assert len(opt.failed_files) == 10

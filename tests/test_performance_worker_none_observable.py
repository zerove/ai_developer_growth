"""证明 ADR-076 的缺陷: 并行路径对 worker 返回 None 不留任何痕迹。

现状 (修复前):
    ``_parallel_check`` 只在 worker **抛异常** 时记 ``failed_files``;
    若 worker 正常**返回 None**(``_check_file_worker`` 内部把
    ``AttributeError`` / ``OSError`` 吞掉后返回 None), 该文件被
    ``optimized_check_directory`` 静默剔除, 且 ``failed_files`` 为空。

后果正是那个偶发失败的特征: 结果少于文件数, 但 ``failed_files`` 拿不到
任何线索 —— 与 ADR-074 修掉的是同一类 fail-open, 只修了一半。

测试设计要点: 替换用的 worker 必须是**模块级可 pickle 的函数**。
第一版用了局部闭包, 结果 ProcessPoolExecutor 在序列化阶段就抛
``AttributeError: Can't pickle local object``, 于是所有 worker 都走了
"抛异常" 分支 —— 测到的是 ADR-074 已修好的东西, 而**不是**本文要指的
"返回 None" 分支。故本版把故障注入放到 worker **内部**在子进程里发生。
"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.scripts.rules_engine.performance import FileCache, PerformanceOptimizer  # noqa: E402

# 哪些文件名应被注入"返回 None"故障。通过环境变量传给子进程。
_FAIL_NAMES = "ADG_TEST_FAIL_NAMES"

# 必须在**导入时**捕获真实 worker。fork 出的子进程会继承已打补丁的
# ``FileCache._check_file_worker``; 若在注入函数里再去读这个属性, 就会
# 无限递归 (注入函数 → 自身), 表现为所有 worker 全部失败、结果数为 0。
_REAL_WORKER = FileCache._check_file_worker


def _none_injecting_worker(args: tuple[str, str | None]) -> dict[str, Any] | None:
    """模块级 worker: 对指定文件返回 None, 其余走真实逻辑。

    必须是模块级函数 —— ProcessPoolExecutor 要 pickle 它传给子进程。
    """
    filepath, _language = args
    targets = {n for n in os.environ.get(_FAIL_NAMES, "").split(",") if n}
    if Path(filepath).name in targets:
        # 复现真实故障形态: worker 内部把异常吞掉后返回 None,
        # 而不是把异常抛到父进程 (那走的是另一条已被 ADR-074 修好的分支)。
        try:
            raise OSError("simulated unreadable file")
        except OSError:
            return None
    return _REAL_WORKER(args)


class TestWorkerNoneIsNotSilent:
    """ADR-076: worker 返回 None 必须留下痕迹, 且不得声称已检查。"""

    def test_parallel_records_worker_returning_none(self, monkeypatch: Any) -> None:
        """并行路径: worker 返回 None 必须进 failed_files。"""
        monkeypatch.setenv(_FAIL_NAMES, "f2.py,f4.py")

        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(6):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
            # 替换 worker 本身: 子进程会继承这个 patch (fork 语义) 并执行它
            original = FileCache._check_file_worker
            FileCache._check_file_worker = staticmethod(_none_injecting_worker)  # type: ignore[method-assign]
            try:
                results = opt.optimized_check_directory(tmp_path)
            finally:
                FileCache._check_file_worker = original  # type: ignore[method-assign]

            names = {Path(p).name for p in opt.failed_files}
            print(f"\n[并行] 结果数={len(results)}, failed_files={sorted(names)}")
            assert len(results) == 4, f"期望 4 条结果, 实得 {len(results)}"
            assert names == {"f2.py", "f4.py"}, f"worker 返回 None 的文件未记入 failed_files, 实得 {sorted(names)}"

    def test_serial_and_parallel_agree_on_none_reporting(self, monkeypatch: Any) -> None:
        """对照组: 串行与并行对 None 的可观测性必须一致。"""
        monkeypatch.setenv(_FAIL_NAMES, "f3.py")

        observed: dict[str, set[str]] = {}
        counts: dict[str, int] = {}
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(6):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            original = FileCache._check_file_worker
            FileCache._check_file_worker = staticmethod(_none_injecting_worker)  # type: ignore[method-assign]
            try:
                for parallel in (True, False):
                    opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
                    results = opt.optimized_check_directory(tmp_path, parallel=parallel)
                    label = "parallel" if parallel else "serial"
                    observed[label] = {Path(p).name for p in opt.failed_files}
                    counts[label] = len(results)
                    print(f"\n[{label}] 结果数={len(results)}, failed_files={sorted(observed[label])}")
            finally:
                FileCache._check_file_worker = original  # type: ignore[method-assign]

        assert counts["parallel"] == counts["serial"], f"两路径结果数不一致: {counts}"
        assert observed["parallel"] == observed["serial"], f"两条路径对 worker None 的可观测性不一致: {observed}"
        assert "f3.py" in observed["parallel"], "并行路径未记录 worker 返回 None"

    def test_healthy_control_no_spurious_failures(self) -> None:
        """健康对照: 无故障注入时不得产生任何 failed_files。"""
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            for i in range(6):
                (tmp_path / f"f{i}.py").write_text(f"x = {i}")

            opt = PerformanceOptimizer(max_workers=4, cache_enabled=False)
            results = opt.optimized_check_directory(tmp_path)

            print(f"\n[健康对照] 结果数={len(results)}, failed_files={opt.failed_files}")
            assert len(results) == 6
            assert opt.failed_files == {}, f"健康路径不该有 failed_files: {opt.failed_files}"

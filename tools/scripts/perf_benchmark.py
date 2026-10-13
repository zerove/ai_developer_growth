#!/usr/bin/env python3
"""Performance regression benchmarks for core modules.

Run with: python tools/scripts/perf_benchmark.py
Outputs JSON baseline to .perf_baseline.json
"""

from __future__ import annotations

import json

# ADR-079: 既支持 `python -m tools.scripts.<name>`, 也支持
# `python tools/scripts/<name>.py` 直接执行 —— 后者 sys.path[0] 是脚本所在
# 目录, 仓库根不在其中, 下面的 `tools.*` 绝对导入会全崩。
# 须自带 import: 部分脚本在插入点前没有 sys/pathlib, 复用会 NameError。
# 用模块名而非别名: 别名无论 CamelCase(N812) 还是下划线(N813) 都会触发
# ruff 命名检查, 而直接 import 后取属性既合规又无歧义。
import pathlib
import statistics
import sys
import time
from pathlib import Path
from typing import Any

_REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


from tools.scripts.rules_engine.checker import check_directory  # noqa: E402
from tools.scripts.semantic_code_graph import SemanticCodeGraph  # noqa: E402

# 基准统一关闭外部 linter: 每个文件 spawn 一次 ruff 子进程, 其开销与耗时
# 噪声远大于规则引擎自身, 混进来会让回归基线无法反映引擎的真实变化。
# run_linters=True 的端到端耗时由 quality-gate 门禁覆盖, 不在此处度量。
BENCH_DIR = Path("tools/scripts")


def benchmark_semantic_code_graph(iterations: int = 3) -> dict[str, Any]:
    """Benchmark semantic_code_graph.build_graph()."""
    times = []
    node_counts = []

    for i in range(iterations):
        start = time.perf_counter()
        graph = SemanticCodeGraph(Path("."))
        graph.build_graph()
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        node_counts.append(len(graph.nodes))
        print(f"  Iteration {i + 1}: {elapsed:.3f}s, {len(graph.nodes)} nodes")

    return {
        "module": "semantic_code_graph",
        "iterations": iterations,
        "times_sec": times,
        "mean_sec": statistics.mean(times),
        "stdev_sec": statistics.stdev(times) if len(times) > 1 else 0,
        "node_count": node_counts[-1],
    }


def benchmark_rules_engine(iterations: int = 3) -> dict[str, Any]:
    """串行规则引擎基准 (jobs=1, 无缓存): 度量引擎自身的最坏情况。"""
    times = []
    file_counts = []

    for i in range(iterations):
        start = time.perf_counter()
        results = check_directory(BENCH_DIR, jobs=1, run_linters=False, use_cache=False)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        file_counts.append(len(results))
        print(f"  Iteration {i + 1}: {elapsed:.3f}s, {len(results)} files")

    return {
        "module": "rules_engine.checker.serial",
        "iterations": iterations,
        "times_sec": times,
        "mean_sec": statistics.mean(times),
        "stdev_sec": statistics.stdev(times) if len(times) > 1 else 0,
        "file_count": file_counts[-1],
    }


def benchmark_rules_engine_parallel(iterations: int = 3) -> dict[str, Any]:
    """生产并行路径基准: check_directory(jobs=4)。

    取代原先对 rules_engine.performance.PerformanceOptimizer 的基准: 该模块
    自述已无生产调用方, 对它做回归基线无法反映真实门禁耗时。

    不启用增量缓存: 实测冷缓存下 4 进程并发写 SQLite 远比无缓存慢
    (21.5s vs 3.3s), 该代价属于缓存实现而非引擎吞吐, 混入会淹没回归信号。
    """
    times = []
    file_counts = []

    for i in range(iterations):
        start = time.perf_counter()
        results = check_directory(BENCH_DIR, jobs=4, run_linters=False, use_cache=False)
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        file_counts.append(len(results))
        print(f"  Iteration {i + 1}: {elapsed:.3f}s, {len(results)} files")

    return {
        "module": "rules_engine.checker.parallel",
        "iterations": iterations,
        "times_sec": times,
        "mean_sec": statistics.mean(times),
        "stdev_sec": statistics.stdev(times) if len(times) > 1 else 0,
        "file_count": file_counts[-1],
    }


def main() -> int:
    print("=" * 60)
    print("  Performance Regression Benchmarks")
    print("=" * 60)

    results = []

    print("\n[1/3] semantic_code_graph.build_graph()")
    results.append(benchmark_semantic_code_graph())

    print("\n[2/3] rules_engine.checker (serial, no cache)")
    results.append(benchmark_rules_engine())

    print("\n[3/3] rules_engine.checker (parallel + cache)")
    results.append(benchmark_rules_engine_parallel())

    # Save baseline
    baseline = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "results": results,
    }

    baseline_path = Path(".perf_baseline.json")
    baseline_path.write_text(json.dumps(baseline, indent=2))
    print(f"\n✅ Baseline saved to {baseline_path}")

    # Print summary
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)
    for r in results:
        print(f"  {r['module']}: {r['mean_sec']:.3f}s ± {r['stdev_sec']:.3f}s")

    return 0


if __name__ == "__main__":
    import sys

    sys.exit(main())

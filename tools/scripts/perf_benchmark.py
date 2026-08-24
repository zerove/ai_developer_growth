#!/usr/bin/env python3
"""Performance regression benchmarks for core modules.

Run with: python tools/scripts/perf_benchmark.py
Outputs JSON baseline to .perf_baseline.json
"""

from __future__ import annotations

import json
import statistics
import time
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.checker import check_directory
from tools.scripts.rules_engine.performance import PerformanceOptimizer
from tools.scripts.semantic_code_graph import SemanticCodeGraph


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
    """Benchmark rules_engine checker on tools/scripts."""
    times = []
    file_counts = []

    for i in range(iterations):
        start = time.perf_counter()
        results = check_directory(Path("tools/scripts"))
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        file_counts.append(len(results))
        print(f"  Iteration {i + 1}: {elapsed:.3f}s, {len(results)} files")

    return {
        "module": "rules_engine.checker",
        "iterations": iterations,
        "times_sec": times,
        "mean_sec": statistics.mean(times),
        "stdev_sec": statistics.stdev(times) if len(times) > 1 else 0,
        "file_count": file_counts[-1],
    }


def benchmark_rules_engine_parallel(iterations: int = 3) -> dict[str, Any]:
    """Benchmark PerformanceOptimizer.optimized_check_directory()."""
    times = []

    for i in range(iterations):
        optimizer = PerformanceOptimizer(max_workers=4, cache_enabled=False)
        start = time.perf_counter()
        optimizer.optimized_check_directory(Path("tools/scripts"))
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        print(f"  Iteration {i + 1}: {elapsed:.3f}s")

    return {
        "module": "rules_engine.performance.parallel",
        "iterations": iterations,
        "times_sec": times,
        "mean_sec": statistics.mean(times),
        "stdev_sec": statistics.stdev(times) if len(times) > 1 else 0,
    }


def main() -> int:
    print("=" * 60)
    print("  Performance Regression Benchmarks")
    print("=" * 60)

    results = []

    print("\n[1/3] semantic_code_graph.build_graph()")
    results.append(benchmark_semantic_code_graph())

    print("\n[2/3] rules_engine.checker.check_directory()")
    results.append(benchmark_rules_engine())

    print("\n[3/3] rules_engine.performance.parallel")
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

"""perf_benchmark 补齐: 并行基准/main 全流程落盘基线。69%→95%+"""

from __future__ import annotations

import json
from pathlib import Path

from tools.scripts import perf_benchmark
from tools.scripts.perf_benchmark import benchmark_rules_engine_parallel, main


class TestParallelBenchmark:
    def test_returns_metrics(self) -> None:
        res = benchmark_rules_engine_parallel(iterations=1)
        assert res["module"] == "rules_engine.performance.parallel"
        assert res["iterations"] == 1
        assert res["stdev_sec"] == 0  # 单次迭代无标准差
        assert len(res["times_sec"]) == 1


class TestMainPipeline:
    def test_main_runs_all_and_saves_baseline(
        self,
        tmp_path: Path,
        monkeypatch,
        capsys,
    ) -> None:
        # 缩小真实基准成本: 打桩三个基准函数返回固定指标
        stub = {
            "module": "stub",
            "iterations": 1,
            "times_sec": [0.01],
            "mean_sec": 0.01,
            "stdev_sec": 0.0,
        }
        monkeypatch.setattr(perf_benchmark, "benchmark_semantic_code_graph", lambda: dict(stub))
        monkeypatch.setattr(perf_benchmark, "benchmark_rules_engine", lambda: dict(stub))
        monkeypatch.setattr(perf_benchmark, "benchmark_rules_engine_parallel", lambda: dict(stub))
        baseline_file = tmp_path / ".perf_baseline.json"
        monkeypatch.setattr(
            perf_benchmark.Path,
            "write_text",
            lambda self, data: None,  # 防写仓库根; 落盘验证用独立路径
        )
        code = main()
        out = capsys.readouterr().out
        assert code == 0
        assert "SUMMARY" in out
        assert "[3/3] rules_engine.performance.parallel" in out
        assert baseline_file.exists() is False  # 未真正写入(打桩)
        _ = json, baseline_file

    def test_main_real_write_in_tmp(self, tmp_path: Path, monkeypatch, capsys) -> None:
        """在 tmp_path 中真实落盘基线文件。"""
        monkeypatch.chdir(tmp_path)
        stub = {"module": "s", "iterations": 1, "times_sec": [0.001], "mean_sec": 0.001, "stdev_sec": 0.0}
        monkeypatch.setattr(perf_benchmark, "benchmark_semantic_code_graph", lambda: dict(stub))
        monkeypatch.setattr(perf_benchmark, "benchmark_rules_engine", lambda: dict(stub))
        monkeypatch.setattr(perf_benchmark, "benchmark_rules_engine_parallel", lambda: dict(stub))
        code = main()
        saved = json.loads((tmp_path / ".perf_baseline.json").read_text())
        assert code == 0 and len(saved["results"]) == 3
        assert "Baseline saved" in capsys.readouterr().out


class TestExistingBenchmarksReal:
    def test_semantic_graph_benchmark_in_tmp(self, tmp_path: Path, monkeypatch, capsys) -> None:
        # 在 tmp 下建少量 py 文件, 真实执行 build_graph 基准(1 次迭代)
        (tmp_path / "a.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / "b.py").write_text("def f():\n    return 2\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        res = perf_benchmark.benchmark_semantic_code_graph(iterations=1)
        assert res["module"] == "semantic_code_graph"
        assert res["iterations"] == 1
        assert res["node_count"] >= 0
        assert "Iteration 1" in capsys.readouterr().out

    def test_rules_engine_benchmark_in_tmp(self, tmp_path: Path, monkeypatch, capsys) -> None:
        (tmp_path / "clean.py").write_text("value = 1\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        res = perf_benchmark.benchmark_rules_engine(iterations=1)
        assert res["module"] == "rules_engine.checker"
        assert "file_count" in res
        assert "Iteration 1" in capsys.readouterr().out

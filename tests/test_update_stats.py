"""update_stats.py 单元测试。"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.update_stats import (
    README_STATS_TABLE,
    _read_readme_stats,
    append_history,
    count_adrs,
    count_cases,
    sync_readme,
)

README_SAMPLE = """# 项目

| 指标 | 数量 |
|------|------|
| 📄 核心文档 | 100 篇 |
| 📚 实践案例 | 20 个 |
| 🛠️ 代码示例 | 5 个 |
| 📋 架构决策 | 8 条 |
| 🧪 测试用例 | 500 个 |
"""


class TestCounters:
    def test_count_cases(self, tmp_path: Path) -> None:
        cs = tmp_path / "case-studies"
        cs.mkdir()
        for i in range(3):
            (cs / f"case-{i}.md").write_text("# case", encoding="utf-8")
        assert count_cases(tmp_path) == 3

    def test_count_adrs_excludes_index(self, tmp_path: Path) -> None:
        adr = tmp_path / "docs" / "adr"
        adr.mkdir(parents=True)
        (adr / "ADR-001-decision.md").write_text("# ADR", encoding="utf-8")
        (adr / "index.md").write_text("# index", encoding="utf-8")
        (adr / "template.md").write_text("# template", encoding="utf-8")
        assert count_adrs(tmp_path) == 1


class TestReadmeSync:
    def test_read_current_stats(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(README_SAMPLE, encoding="utf-8")
        current = _read_readme_stats(readme)
        label = README_STATS_TABLE["core_docs"]
        assert current[label] == 100

    def test_sync_updates_stale_values(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(README_SAMPLE, encoding="utf-8")
        stats = {"core_docs": 120, "cases": 25, "adrs": 8, "tests": 500}
        changes = sync_readme(readme, stats)
        assert len(changes) == 2
        content = readme.read_text(encoding="utf-8")
        assert "| 120 篇 |" in content
        assert "| 25 个 |" in content
        # 未变化项保持原样
        assert "| 500 个 |" in content

    def test_sync_no_changes_when_fresh(self, tmp_path: Path) -> None:
        readme = tmp_path / "README.md"
        readme.write_text(README_SAMPLE, encoding="utf-8")
        stats = {"core_docs": 100, "cases": 20, "adrs": 8, "tests": 500}
        changes = sync_readme(readme, stats)
        assert changes == []


class TestHistory:
    def test_append_history(self, tmp_path: Path) -> None:
        import json

        hist = tmp_path / "stats_history.jsonl"
        append_history(hist, {"tests": 10})
        append_history(hist, {"tests": 12})
        lines = hist.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        entry = json.loads(lines[1])
        assert entry["tests"] == 12
        assert "timestamp" in entry


class TestCollectQualityGate:
    """F 项: quality-gate JSON 采集进趋势历史。"""

    def test_collect_parses_summary(self, tmp_path: Path) -> None:
        import subprocess as sp

        import tools.scripts.update_stats as us
        from tools.scripts.update_stats import collect_quality_gate

        hooks_runner = tmp_path / "tools" / "scripts" / "hooks_runner.py"
        hooks_runner.parent.mkdir(parents=True)
        hooks_runner.write_text("# fake\n")

        fake_json = (
            '{"summary": {"passed": 145, "failed": 2, "total_files": 147,'
            ' "total_issues": 9, "baseline_exempt": 9}, "results": []}'
        )

        def fake_run(*args, **kwargs):
            return sp.CompletedProcess(args[0], 0, stdout=fake_json, stderr="")

        original = us.subprocess.run
        us.subprocess.run = fake_run  # type: ignore[method-assign]
        try:
            out = collect_quality_gate(tmp_path)
        finally:
            us.subprocess.run = original
        assert out is not None
        assert out["gate_failed"] == 2
        assert out["gate_issues"] == 9
        assert out["gate_baseline_exempt"] == 9
        total = 147
        assert out["gate_pass_rate"] == round(145 / total * 100)

    def test_collect_returns_none_when_unparseable(self, tmp_path: Path) -> None:
        from tools.scripts.update_stats import collect_quality_gate

        # 无 hooks_runner 文件 → None（不阻断统计）
        assert collect_quality_gate(tmp_path) is None

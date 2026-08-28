"""tools/scripts/metrics_telemetry.py 单元测试 — P1-4 0% 模块攻坚。

14 stmts 全覆盖：MetricsTelemetry 构造、collect_metrics 写入 .quality-trends/telemetry.json。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from tools.scripts.metrics_telemetry import MetricsTelemetry  # noqa: E402


@pytest.fixture
def tmp_root(tmp_path: Path) -> Path:
    return tmp_path


class TestMetricsTelemetry:
    def test_default_root_uses_get_project_root(self) -> None:
        # 不传 root_dir 时走 get_project_root
        # 用 monkeypatch 让它返回 tmp_path 避免污染真实项目
        import tools.scripts.metrics_telemetry as mod

        original = mod.get_project_root
        try:
            mod.get_project_root = lambda: Path("/tmp/zzz_does_not_exist_xyz")
            mt = MetricsTelemetry()
            assert mt.root_dir == Path("/tmp/zzz_does_not_exist_xyz")
            assert mt.metrics_file == Path("/tmp/zzz_does_not_exist_xyz/.quality-trends/telemetry.json")
        finally:
            mod.get_project_root = original

    def test_explicit_root_dir(self, tmp_path: Path) -> None:
        mt = MetricsTelemetry(root_dir=tmp_path)
        assert mt.root_dir == tmp_path
        assert mt.metrics_file == tmp_path / ".quality-trends" / "telemetry.json"

    def test_collect_metrics_returns_dict(self, tmp_path: Path) -> None:
        mt = MetricsTelemetry(root_dir=tmp_path)
        result = mt.collect_metrics()
        assert isinstance(result, dict)

    def test_collect_metrics_contains_required_keys(self, tmp_path: Path) -> None:
        mt = MetricsTelemetry(root_dir=tmp_path)
        result = mt.collect_metrics()
        for key in (
            "test_coverage_percent",
            "first_try_pass_rate",
            "ai_adoption_rate",
            "slop_density_index",
        ):
            assert key in result

    def test_collect_metrics_creates_parent_dir(self, tmp_path: Path) -> None:
        target = tmp_path / "deep" / "nested" / "dir"
        mt = MetricsTelemetry(root_dir=target)
        assert not (target / ".quality-trends").exists()
        mt.collect_metrics()
        assert (target / ".quality-trends").exists()

    def test_collect_metrics_writes_valid_json(self, tmp_path: Path) -> None:
        mt = MetricsTelemetry(root_dir=tmp_path)
        result = mt.collect_metrics()
        # 文件存在
        assert mt.metrics_file.exists()
        # 内容是合法 JSON 且与返回值一致
        raw = mt.metrics_file.read_text(encoding="utf-8")
        loaded = json.loads(raw)
        assert loaded == result

    def test_collect_metrics_idempotent(self, tmp_path: Path) -> None:
        mt = MetricsTelemetry(root_dir=tmp_path)
        first = mt.collect_metrics()
        second = mt.collect_metrics()
        assert first == second

    def test_collect_metrics_overwrites_existing_file(self, tmp_path: Path) -> None:
        # 先写一个旧文件
        target = tmp_path / ".quality-trends"
        target.mkdir(parents=True)
        old = target / "telemetry.json"
        old.write_text('{"stale": true}', encoding="utf-8")
        # 收集后被覆盖
        mt = MetricsTelemetry(root_dir=tmp_path)
        result = mt.collect_metrics()
        loaded = json.loads(old.read_text(encoding="utf-8"))
        assert "stale" not in loaded
        assert loaded == result

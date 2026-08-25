"""QualityTracker 连接生命周期测试（第三轮建议 1）。"""

from __future__ import annotations

from pathlib import Path

from tools.scripts.rules_engine import store as store_mod
from tools.scripts.rules_engine.quality_trends import QualityTracker


class TestTrackerLifecycle:
    def test_close_removes_pooled_connection(self, tmp_path: Path) -> None:
        db = str(tmp_path / "quality.db")
        tracker = QualityTracker(tmp_path)
        tracker._db_path = Path(db)  # 对齐 close_connection 的 key
        key = db
        assert key in store_mod._connections or tracker.store is not None
        tracker.close()
        assert key not in store_mod._connections
        assert tracker._store is None

    def test_close_is_idempotent(self, tmp_path: Path) -> None:
        tracker = QualityTracker(tmp_path)
        tracker.close()
        tracker.close()  # 二次调用不应抛异常

    def test_context_manager_closes(self, tmp_path: Path) -> None:
        with QualityTracker(tmp_path) as tracker:
            tracker.take_snapshot(tmp_path, semantic=False, hallucination=False)
            assert len(tracker.snapshots) >= 1
        # 退出后连接应已从池中移除
        assert all(not k.endswith(str(tmp_path / "quality.db")) for k in store_mod._connections)

    def test_store_property_rebuilds_after_close(self, tmp_path: Path) -> None:
        tracker = QualityTracker(tmp_path)
        tracker.close()
        _ = tracker.store  # 再访问应重建而非崩溃
        tracker.close()

"""context-sync 滚动窗口单元测试（改进建议 6）。

验证 ContextSynthesizer._prune_update_entries 的裁剪行为:
保留头部 + 最近 N 条更新记录，防止 CONTEXT.md 无限膨胀。
"""

from __future__ import annotations

from jcode_scripts_import import load_context_sync_module

ContextSynthesizer = load_context_sync_module().ContextSynthesizer


def _entry(n: int) -> str:
    return f"## 更新记录: 2026-08-25 00:00:{n:02d}\n\n### 任务\ntask {n}\n\n---\n"


class TestPruneUpdateEntries:
    def setup_method(self) -> None:
        self.synth = ContextSynthesizer()

    def test_keeps_header_and_recent_entries(self) -> None:
        content = "# 项目概述\n\n正文说明\n\n" + "".join(_entry(i) for i in range(10))
        result = self.synth._prune_update_entries(content, max_entries=3)
        assert "项目概述" in result
        # 最新记录在最前, 应保留 00:00:00..00:00:02
        for i in range(3):
            assert f"task {i}" in result
        assert "task 9" not in result
        assert "已自动裁剪 7 条" in result

    def test_no_entries_unchanged(self) -> None:
        content = "# 纯头部文档，无更新记录"
        assert self.synth._prune_update_entries(content, 5) == content

    def test_under_limit_no_pruning_marker(self) -> None:
        content = "# 头部\n\n" + _entry(0) + _entry(1)
        result = self.synth._prune_update_entries(content, max_entries=50)
        assert "已自动裁剪" not in result
        assert "task 1" in result

    def test_zero_prunes_all_at_inner_level(self) -> None:
        # 内层函数 max_entries=0 表示全裁; "禁用"由外层 synthesize 判断
        content = "# 头部\n\n" + "".join(_entry(i) for i in range(5))
        result = self.synth._prune_update_entries(content, max_entries=0)
        assert "task 4" not in result

    def test_synthesize_zero_disables(self) -> None:
        content = "# 头部\n\n" + "".join(_entry(i) for i in range(5))
        result = self.synth.synthesize_context_update("d", "t", content, max_update_entries=0)
        assert "task 4" in result and "task 0" in result
        assert "已自动裁剪" not in result

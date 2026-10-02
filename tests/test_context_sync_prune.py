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


class TestHeaderSurvivesRollingWindow:
    """ADR-061: 固定头部必须始终独立于滚动窗口。

    2026-08-23 事故：新记录被拼在头部之前，裁剪逻辑把"新记录 + 头部 + 历史"
    整段当成单条记录，头部随窗口裁剪被静默丢弃，CONTEXT.md 退化成纯同步日志。
    """

    HEADER = "# 项目上下文\n\n## 项目状态\n\n- 版本: v2.24.0\n"

    def setup_method(self) -> None:
        self.synth = ContextSynthesizer()

    def test_header_precedes_every_entry(self) -> None:
        out = self.synth.synthesize_context_update("d", "t", self.HEADER, max_update_entries=50)
        assert out.startswith("# 项目上下文")
        assert "## 项目状态" in out
        # 头部之后才出现第一条更新记录
        assert out.index("## 项目状态") < out.index("## 更新记录:")

    def test_header_survives_many_syncs(self) -> None:
        # 窗口为 5，连续 40 次同步远超窗口；旧实现下头部在第 6 次即消失
        content = self.HEADER
        for i in range(40):
            content = self.synth.synthesize_context_update("d", f"task{i}", content, max_update_entries=5)
        assert content.startswith("# 项目上下文")
        assert "## 项目状态" in content
        assert content.count("## 更新记录:") == 5

    def test_header_never_absorbed_into_entry_body(self) -> None:
        # 头部必须位于记录边界之外：紧跟在新记录标题后不应出现头部内容
        out = self.synth.synthesize_context_update("d", "t", self.HEADER, max_update_entries=50)
        record_body = out.split("## 更新记录:", 1)[1]
        assert "# 项目上下文" not in record_body

    def test_history_still_prepends_newest_first(self) -> None:
        seeded = self.HEADER + "\n\n" + _entry(0) + "\n" + _entry(1)
        out = self.synth.synthesize_context_update("d", "新任务", seeded, max_update_entries=50)
        assert out.startswith("# 项目上下文")
        assert "新任务" in out
        assert "task 1" in out and "task 0" in out
        # 记录按时间倒序：新记录在最前
        assert out.index("新任务") < out.index("task 1")


class TestSplitHeaderAndEntries:
    def setup_method(self) -> None:
        self.synth = ContextSynthesizer()

    def test_no_entries_is_all_header(self) -> None:
        assert self.synth._split_header_and_entries("# 只有头部") == ("# 只有头部", "")

    def test_splits_at_first_entry(self) -> None:
        header, entries = self.synth._split_header_and_entries("# 头\n\n" + _entry(0) + "\n" + _entry(1))
        assert header == "# 头"
        assert entries.startswith("## 更新记录:")
        assert entries.count("## 更新记录:") == 2

    def test_render_puts_header_first(self) -> None:
        out = self.synth._render("# 头", ["## 更新记录: a", "## 更新记录: b"], pruned=3)
        assert out.startswith("# 头")
        assert "已自动裁剪 3 条" in out


class TestSummarizeDiffAndGuard:
    """P2-3: 变更摘要结构化 + diff 原文输出守卫。"""

    def setup_method(self) -> None:
        self.synth = ContextSynthesizer()

    def test_summarize_diff_no_raw_lines(self) -> None:
        diff = (
            "diff --git a/foo.py b/foo.py\n"
            "index 123..456 100644\n"
            "--- a/foo.py\n"
            "+++ b/foo.py\n"
            "@@ -1,2 +1,3 @@\n"
            "+added line\n"
            "-removed line\n"
        )
        summary = ContextSynthesizer.summarize_diff(diff)
        assert "+added line" not in summary
        assert "diff --git" not in summary
        assert "@@" not in summary
        assert "foo.py" in summary
        assert "(+1 / -1 行)" in summary

    def test_guard_blocks_diff_raw(self) -> None:
        import pytest

        with pytest.raises(ValueError, match="diff 原文"):
            self.synth.guard_no_diff_raw("正常行\ndiff --git a/x b/x\n")

    def test_synthesize_output_is_clean(self) -> None:
        diff = "diff --git a/x.py b/x.py\n@@ -1 +1 @@\n+print(1)\n"
        out = self.synth.synthesize_context_update(diff, "t", "", max_update_entries=5)
        assert "diff --git" not in out
        assert "@@" not in out
        assert "x.py" in out

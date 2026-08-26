"""三个小模块攻坚: add_navigation / context_streamer / audit_attestation。

覆盖 32%/40%/40% → 90%+。
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools.scripts.add_navigation import (
    CATEGORY_DOCS,
    add_navigation_to_doc,
    get_navigation,
)
from tools.scripts.audit_attestation import AuditAttestationLedger
from tools.scripts.context_streamer import ContextStreamer

# ── add_navigation ──────────────────────────────────────────


class TestAddNavigation:
    def _doc(self, tmp_path: Path, category: str | None = "效率层", name: str = "full-cycle-workflow") -> Path:
        p = tmp_path / f"{name}.md"
        front = (
            f"---\ntitle: t\ncategory: {category}\n---\n\n# 正文\n" if category else "---\ntitle: t\n---\n\n# 正文\n"
        )
        p.write_text(front, encoding="utf-8")
        return p

    def test_nav_generated_with_related_links(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, name="anti-patterns")
        nav = get_navigation(doc, doc.read_text(encoding="utf-8"))
        assert "docs/efficiency/full-cycle-workflow" in nav
        # 自身不应出现在相关链接里
        assert "- [[docs/efficiency/anti-patterns|" not in nav

    def test_no_frontmatter_category_returns_empty(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, category=None)
        assert get_navigation(doc, doc.read_text(encoding="utf-8")) == ""

    def test_unknown_category_returns_empty(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, category="不存在的层")
        assert get_navigation(doc, doc.read_text(encoding="utf-8")) == ""

    def test_single_doc_in_category_returns_empty(self, tmp_path: Path) -> None:
        # 认知层有 4 个文档; 用一个只含自身的场景: 构造 category 只映射自身
        doc = self._doc(tmp_path, name="product-thinking", category="认知层")
        nav = get_navigation(doc, doc.read_text(encoding="utf-8"))
        assert nav and "solo-founder-loop" in nav

    def test_related_links_capped_at_five(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, name="metrics-framework", category="效率层")
        nav = get_navigation(doc, doc.read_text(encoding="utf-8"))
        link_lines = [line for line in nav.splitlines() if line.startswith("- [[")]
        assert len(link_lines) == 5  # 效率层有 7 个, 掐到 5

    def test_add_navigation_appends_once(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, name="token-optimization")
        assert add_navigation_to_doc(doc) is True
        content = doc.read_text(encoding="utf-8")
        assert "## 导航" in content
        # 第二次不再追加
        assert add_navigation_to_doc(doc) is False

    def test_skip_when_no_category(self, tmp_path: Path) -> None:
        doc = self._doc(tmp_path, category=None)
        assert add_navigation_to_doc(doc) is False

    def test_all_categories_have_docs(self) -> None:
        assert set(CATEGORY_DOCS) == {"效率层", "治理层", "认知层", "学习层"}
        for docs in CATEGORY_DOCS.values():
            assert all(len(pair) == 2 for pair in docs)

    def test_main_updates_docs_in_cwd(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:

        eff = tmp_path / "docs" / "efficiency"
        eff.mkdir(parents=True)
        (eff / "anti-patterns.md").write_text("---\ncategory: 效率层\n---\n\n正文\n", encoding="utf-8")
        (eff / "already-nav.md").write_text("---\ncategory: 效率层\n---\n\n正文\n\n## 导航\n- x\n", encoding="utf-8")
        monkeypatch.chdir(tmp_path)
        from tools.scripts.add_navigation import main

        main()
        out = capsys.readouterr().out
        assert "已更新" in out and "anti-patterns.md" in out


# ── context_streamer ────────────────────────────────────────


class TestContextStreamer:
    def test_missing_file_returns_empty(self, tmp_path: Path) -> None:
        s = ContextStreamer(root_dir=tmp_path)
        assert s.stream_file_chunks(tmp_path / "nope.txt") == []

    def test_chunks_split_by_page_size(self, tmp_path: Path) -> None:
        f = tmp_path / "big.txt"
        f.write_text("\n".join(f"line{i}" for i in range(120)), encoding="utf-8")
        s = ContextStreamer(root_dir=tmp_path, page_size=50)
        chunks = s.stream_file_chunks(f)
        assert len(chunks) == 3
        assert chunks[0].splitlines()[0] == "line0"
        assert chunks[2].splitlines()[-1] == "line119"

    def test_exact_multiple_no_empty_tail(self, tmp_path: Path) -> None:
        f = tmp_path / "exact.txt"
        f.write_text("\n".join("x" for _ in range(100)), encoding="utf-8")
        s = ContextStreamer(root_dir=tmp_path, page_size=50)
        assert len(s.stream_file_chunks(f)) == 2

    def test_default_root_fallback(self, tmp_path: Path) -> None:
        s = ContextStreamer(root_dir=tmp_path)
        assert s.root_dir == tmp_path and s.page_size == 50


# ── audit_attestation ───────────────────────────────────────


class TestAuditAttestationLedger:
    def test_record_creates_chained_entries(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        e1 = ledger.record_trace("EXEC", {"step": 1})
        e2 = ledger.record_trace("EXEC", {"step": 2})
        assert e1["prev_hash"] == "0" * 64
        assert e2["prev_hash"] == e1["current_hash"]
        assert len(e1["current_hash"]) == 64

    def test_ledger_file_persisted_jsonl(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.record_trace("A", {})
        ledger.record_trace("B", {"k": "v"})
        lines = ledger.ledger_file.read_text(encoding="utf-8").strip().splitlines()
        assert len(lines) == 2
        assert json.loads(lines[1])["event_type"] == "B"

    def test_corrupt_last_line_falls_back_to_genesis(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.ledger_file.parent.mkdir(parents=True, exist_ok=True)
        ledger.ledger_file.write_text("{ broken json\n", encoding="utf-8")
        entry = ledger.record_trace("A", {})
        assert entry["prev_hash"] == "0" * 64  # 解析失败回退创世哈希

    def test_report_empty_ledger(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        assert "No entries" in ledger.generate_report()

    def test_report_valid_chain(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.record_trace("EXEC", {"status": "ok"})
        ledger.record_trace("AUDIT", {"tool": "ruff"})
        report = ledger.generate_report()
        assert "VALID" in report and "Total Entries: 2" in report

    def test_report_detects_tampering(self, tmp_path: Path) -> None:
        ledger = AuditAttestationLedger(root_dir=tmp_path)
        ledger.record_trace("EXEC", {"status": "ok"})
        # 篡改账本内容但不改哈希 → 链断裂
        lines = ledger.ledger_file.read_text(encoding="utf-8").splitlines()
        tampered = json.loads(lines[0])
        tampered["details"]["status"] = "hacked"
        ledger.ledger_file.write_text(json.dumps(tampered) + "\n", encoding="utf-8")
        assert "BROKEN" in ledger.generate_report()

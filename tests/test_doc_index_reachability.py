"""文档索引可达性: `docs/**/README.md` 必须能自 MOC 抵达。

## 要锁住的缺陷

本轮补建了 14 个知识层 `README.md` 索引, 并据此在 `docs/MOC.md` 写下
"缺口由 101 降至 4"。但那 14 个索引**一个都没接入 MOC** —— 全部是孤儿。
索引无人引用即等于不存在: 读者从 MOC 出发永远到不了它们, 而它们内部的
69 条入链让"覆盖率"看起来是真实的。

`link_auditor.py` 对此**报绿**("All links are valid"), 因为它校验的是
"链接能否解析", 不是"文件能否被抵达"。这与 ADR-078 那条断链、ADR-052/074
的 fail-open 同源: 某一侧看起来是好的。

## 为何不用可达性图分析

从 MOC 做图遍历会牵扯 frontmatter、模板占位符与 `templates/` 目录, 误报面
大。本测试只断言一条**机械可判定**的不变量: 每个层索引都被 MOC 直接引用。
若将来索引被移进二级目录, 只需把该层加进 `NESTED` 并写明理由。
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MOC = REPO_ROOT / "docs" / "MOC.md"
DOCS = REPO_ROOT / "docs"

# 不在 docs/<层>/README.md 这一形态下的索引目录 -> 理由
NESTED: dict[str, str] = {}


def _moc_text() -> str:
    return MOC.read_text(encoding="utf-8").replace("\\|", "|")


def _layer_indexes() -> list[Path]:
    return sorted(DOCS.glob("*/README.md"))


class TestLayerIndexesAreReachable:
    def test_index_set_is_non_trivial(self) -> None:
        indexes = _layer_indexes()
        assert len(indexes) >= 14, f"只找到 {len(indexes)} 个层索引, 样本异常, 本组用例失去意义"

    def test_every_index_is_referenced_by_moc(self) -> None:
        moc = _moc_text()
        orphans = []
        for index in _layer_indexes():
            rel_dir = index.parent.relative_to(DOCS).as_posix()
            if rel_dir in NESTED:
                continue
            # MOC 以 [[docs/<层>/README|标题]] 或相对路径引用
            if f"docs/{rel_dir}/README" not in moc and f"{rel_dir}/README" not in moc:
                orphans.append(f"docs/{rel_dir}/README.md")
        assert not orphans, (
            "以下层索引未被 docs/MOC.md 引用, 属孤儿 —— 读者无法抵达, "
            "其覆盖贡献不成立:\n  " + "\n  ".join(orphans) + "\n请在 MOC 的「层索引导航」中接入。"
        )

    @pytest.mark.parametrize("rel", sorted(NESTED))
    def test_nested_entry_still_exists(self, rel: str) -> None:
        assert (DOCS / rel).is_dir(), f"NESTED 中的 {rel} 已不存在, 请移除该条目"
        assert NESTED[rel].strip(), "NESTED 条目必须写明理由"

    def test_moc_declares_no_duplicate_index_links(self) -> None:
        """同一索引在 MOC 中被引用多次 -> 导航表会重复渲染。"""
        moc = _moc_text()
        refs = re.findall(r"\[\[docs/([a-z-]+)/README", moc)
        dupes = sorted({r for r in refs if refs.count(r) > 1})
        assert not dupes, f"MOC 导航表中这些索引被重复引用: {dupes}"

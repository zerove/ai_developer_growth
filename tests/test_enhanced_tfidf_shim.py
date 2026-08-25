"""shim 一致性守卫测试。

examples/ai-navigation/src/enhanced_tfidf.py 是指向共享实现
tools/scripts/search/tfidf_engine.py 的兼容 shim。
本测试防止两处 API 静默漂移：shim 必须能重导出主实现的全部公共符号，
且两者 Document 字段保持一致（hybrid_search 依赖这些字段）。
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
SHIM = ROOT / "examples/ai-navigation/src/enhanced_tfidf.py"
IMPL = ROOT / "tools/scripts/search/tfidf_engine.py"


def test_shim_reexports_all_public_symbols() -> None:
    """shim 重导出的符号必须覆盖主实现的全部公共类/函数。"""
    impl_tree = ast.parse(IMPL.read_text(encoding="utf-8"))
    public = {
        node.name
        for node in impl_tree.body
        if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and not node.name.startswith("_")
    }
    shim_src = SHIM.read_text(encoding="utf-8")
    missing = [name for name in sorted(public) if name not in shim_src]
    assert not missing, (
        f"shim 缺少主实现新增的公共符号: {missing}（请同步 examples/ai-navigation/src/enhanced_tfidf.py）"
    )


def test_document_fields_consistent_between_impl_and_shim_import() -> None:
    """经 shim 导入的 Document 与主实现必须是同一个类（字段天然一致）。"""
    import importlib.util
    import sys

    sys.path.insert(0, str(ROOT))
    from tools.scripts.search.tfidf_engine import Document as ImplDocument

    # 通过 shim 模块的文件位置导入，模拟 ai-navigation 的引用路径

    spec = importlib.util.spec_from_file_location("enhanced_tfidf_shim", SHIM)
    assert spec and spec.loader
    shim_mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(shim_mod)

    assert shim_mod.Document is ImplDocument


@pytest.mark.parametrize("field", ["id", "title", "content", "doc_type", "tags", "category", "difficulty"])
def test_document_required_fields_exist(field: str) -> None:
    """hybrid_search 依赖的 Document 字段不可被删改。"""
    import sys

    sys.path.insert(0, str(ROOT))
    from dataclasses import fields

    from tools.scripts.search.tfidf_engine import Document

    names = {f.name for f in fields(Document)}
    assert field in names

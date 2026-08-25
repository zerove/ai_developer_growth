"""search-server 冒烟测试：验证知识库检索服务的导入链、文档加载与检索质量。

背景: search-server.py 曾因引用不存在的 enhanced_tfidf 模块而从未能启动，
且文档目录路径错误（scripts/docs）、frontmatter tags 解析用 ast.literal_eval
无法处理中文裸标签。本测试固化这三处修复，防止回归。
"""

from __future__ import annotations

import importlib.util
import logging
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def _load_server_module():
    """加载 scripts/search-server.py 为模块（不启动 uvicorn）。"""
    sys.path.insert(0, str(PROJECT_ROOT))
    spec = importlib.util.spec_from_file_location(
        "search_server_under_test", PROJECT_ROOT / "scripts" / "search-server.py"
    )
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def server() -> object:
    logging.disable(logging.CRITICAL)
    try:
        return _load_server_module()
    finally:
        logging.disable(logging.NOTSET)


class TestImportChain:
    """导入链完整性：共享 TF-IDF 引擎可从新位置导入。"""

    def test_tfidf_engine_importable(self) -> None:
        from tools.scripts.search.tfidf_engine import (  # noqa: F401
            Document,
            EnhancedTFIDF,
            create_enhanced_index,
        )

    def test_example_shim_still_works(self) -> None:
        """示例项目的兼容 shim 不因迁移而破坏。"""
        from tools.scripts.search import tfidf_engine  # noqa: F401

        shim = PROJECT_ROOT / "examples" / "ai-navigation" / "src" / "enhanced_tfidf.py"
        assert shim.exists(), "兼容 shim 文件丢失"


class TestDocumentLoading:
    """文档加载：全量 docs 目录 + frontmatter 解析。"""

    def test_loads_majority_of_docs(self, server) -> None:
        docs = server.load_documents()
        assert len(docs) > 200, f"文档加载过少: {len(docs)}"

    def test_chinese_tags_parsed(self, server) -> None:
        """中文裸标签 [架构决策, ADR] 必须解析成功而非报错丢弃。"""
        docs = {d.id: d for d in server.load_documents()}
        tagged = [d for d in docs.values() if d.tags]
        assert len(tagged) > 100, f"带标签文档过少: {len(tagged)}"
        sample = next(iter(tagged))
        assert all(isinstance(t, str) and t for t in sample.tags)


class TestSearchQuality:
    """检索质量：中英文查询均有合理结果。"""

    def test_search_returns_relevant_results(self, server) -> None:
        docs = server.load_documents()
        index = server.create_enhanced_index(docs)
        results = index.search("质量门禁", top_k=3)
        assert len(results) > 0, "中文查询无结果"

    def test_english_query_works(self, server) -> None:
        docs = server.load_documents()
        index = server.create_enhanced_index(docs)
        results = index.search("code review", top_k=3)
        assert len(results) > 0, "英文查询无结果"

    def test_stats_endpoint_data_available(self, server) -> None:
        docs = server.load_documents()
        index = server.create_enhanced_index(docs)
        stats = index.get_stats()
        assert stats["total_documents"] == len(docs)
        assert stats["total_terms"] > 0

    def test_suggestions_work(self, server) -> None:
        docs = server.load_documents()
        index = server.create_enhanced_index(docs)
        suggestions = index.suggest("ai")
        assert isinstance(suggestions, list)

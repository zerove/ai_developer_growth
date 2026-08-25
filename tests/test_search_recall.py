"""检索召回基准测试（防退化）。

固化"查询 → 期望命中文档"断言，防止未来改分词/评分时静默退化
（历史教训：jieba 缺失时回退整串匹配，所有中文长查询零召回）。

维护约定：
- 新增基准用例时先跑一次确认期望 id 稳定，再写入 CASES。
- 期望 id 是 docs/ 下文档的相对路径 id（/ 与 .md 替换为 _）。
- top_k 内命中即通过；expect=None 表示只要求非零召回。
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

# (查询, top_k 内期望命中的文档 id 或 None)
CASES: list[tuple[str, str | None]] = [
    ("质量门禁", "adr_003-quality-gate-system"),
    ("多智能体协作编排", None),
    ("AI 开发生命周期", "efficiency_ai-native-sdlc-whitepaper"),
    ("部署与运维", "efficiency_ai-deployment-operations"),
    ("代码审查反模式", "efficiency_ai-code-analysis"),
    ("语义代码图", "efficiency_ai-native-sdlc-whitepaper"),
    ("知识图谱 MOC", "MOC"),
    ("任务优先级排序", "mindset_project-management"),
    ("上下文同步", "integration_context-sync-integration"),
    ("架构漂移守卫", "tools_search-server-and-mcp"),
    ("检索服务部署", "tools_search-server-and-mcp"),
    ("自我修正循环", "integration_self-correction-loop-integration"),
    ("TF-IDF 检索引擎", "tools_search-server-and-mcp"),
    ("案例研究", "index"),
]


@pytest.fixture(scope="module")
def search_index():
    """构建一次全量索引供全部用例复用（jieba 首次加载约 1s）。"""
    sys.path.insert(0, str(ROOT))
    spec = importlib.util.spec_from_file_location("search_server", ROOT / "scripts/search-server.py")
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    from tools.scripts.search.tfidf_engine import create_enhanced_index

    return create_enhanced_index(mod.load_documents())


@pytest.mark.parametrize(("query", "expected_id"), CASES)
def test_recall(query: str, expected_id: str | None, search_index) -> None:
    hits = search_index.search(query, top_k=3)
    ids = [h.doc.id for h in hits]
    assert ids, f"查询 {query!r} 零召回（疑似 jieba 缺失回退整串匹配）"
    if expected_id is not None:
        assert expected_id in ids, f"查询 {query!r} 期望命中 {expected_id}，实际 top3={ids}"

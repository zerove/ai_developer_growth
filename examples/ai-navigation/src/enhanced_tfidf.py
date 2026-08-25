"""兼容 shim: 实现已迁移至 tools/scripts/search/tfidf_engine.py。

示例项目 (ai-navigation) 通过相对导入继续工作；
search-server 等主项目工具统一从新位置导入。
"""

from tools.scripts.search.tfidf_engine import (  # noqa: F401
    Document,
    EnhancedTFIDF,
    SearchResult,
    SynonymDictionary,
    create_enhanced_index,
)

__all__ = ["Document", "EnhancedTFIDF", "SearchResult", "SynonymDictionary", "create_enhanced_index"]

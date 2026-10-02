"""兼容 shim: 实现已迁移至 tools/scripts/search/tfidf_engine.py。

search-server 等主项目工具统一从新位置导入；示例内部继续以相对导入使用
本模块（hybrid_search.py 从这里取 Document / EnhancedTFIDF 等）。

示例可被独立安装（pip install -e examples/ai-navigation），此时仓库根不在
sys.path 上，直接 from tools... 会 ModuleNotFoundError。因此先正常导入，
失败时把仓库根补进 sys.path 后重试。tools 始终是唯一实现，这里不复制代码。
"""

import sys
from pathlib import Path

try:
    from tools.scripts.search.tfidf_engine import (
        Document,
        EnhancedTFIDF,
        SearchResult,
        SynonymDictionary,
        create_enhanced_index,
    )
except ModuleNotFoundError:
    _REPO_ROOT = Path(__file__).resolve().parents[3]
    if str(_REPO_ROOT) not in sys.path:
        sys.path.insert(0, str(_REPO_ROOT))
    from tools.scripts.search.tfidf_engine import (
        Document,
        EnhancedTFIDF,
        SearchResult,
        SynonymDictionary,
        create_enhanced_index,
    )

__all__ = [
    "Document",
    "EnhancedTFIDF",
    "SearchResult",
    "SynonymDictionary",
    "create_enhanced_index",
]

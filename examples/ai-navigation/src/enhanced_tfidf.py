"""
Enhanced TF-IDF Engine with Synonym Support

Optimized TF-IDF implementation with:
- BM25 scoring
- Synonym expansion
- Query normalization
- Relevance feedback
"""

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field


@dataclass
class Document:
    """Document representation."""

    id: str
    title: str
    content: str
    doc_type: str
    tags: list[str] = field(default_factory=list)
    category: str = ""
    difficulty: str = ""


@dataclass
class SearchResult:
    """Search result with score."""

    doc: Document
    score: float
    snippet: str
    match_terms: list[str]


class SynonymDictionary:
    """Synonym dictionary for query expansion."""

    def __init__(self):
        self.synonyms: dict[str, set[str]] = {}
        self._load_default_synonyms()

    def _load_default_synonyms(self):
        """Load default Chinese synonyms for tech terms."""
        default_synonyms = {
            # AI 相关
            "人工智能": {"ai", "机器学习", "深度学习"},
            "ai": {"人工智能", "机器学习", "深度学习"},
            "机器学习": {"ai", "人工智能", "ml", "machine learning"},
            "深度学习": {"ai", "人工智能", "神经网络", "dl"},
            "大语言模型": {"llm", "大模型", "语言模型"},
            "llm": {"大语言模型", "大模型", "语言模型"},
            # 开发相关
            "前端": {"frontend", "客户端", "界面"},
            "后端": {"backend", "服务端", "服务器"},
            "全栈": {"fullstack", "全栈开发"},
            "微服务": {"microservice", "微服务架构"},
            "api": {"接口", "api接口", "restful"},
            # 工具相关
            "代码审查": {"code review", "代码评审", "cr"},
            "单元测试": {"unit test", "ut", "单元测试"},
            "集成测试": {"integration test", "it"},
            "持续集成": {"ci", "continuous integration"},
            "持续部署": {"cd", "continuous deployment"},
            # 架构相关
            "设计模式": {"design pattern", "模式"},
            "架构": {"architecture", "体系结构"},
            "数据库": {"database", "db", "数据存储"},
            "缓存": {"cache", "缓冲"},
            # 学习相关
            "学习路径": {"学习路线", "成长路径", "learning path"},
            "最佳实践": {"best practice", "最佳方法"},
            "案例": {"case study", "实例", "例子"},
            "方法论": {"methodology", "方法", "框架"},
        }

        for key, synonyms in default_synonyms.items():
            self.synonyms[key] = synonyms
            for syn in synonyms:
                if syn not in self.synonyms:
                    self.synonyms[syn] = set()
                self.synonyms[syn].add(key)

    def expand(self, terms: list[str]) -> list[str]:
        """Expand terms with synonyms."""
        expanded = set(terms)
        for term in terms:
            if term in self.synonyms:
                expanded.update(self.synonyms[term])
        return list(expanded)

    def add_synonym(self, term: str, synonym: str):
        """Add a synonym pair."""
        if term not in self.synonyms:
            self.synonyms[term] = set()
        self.synonyms[term].add(synonym)

        if synonym not in self.synonyms:
            self.synonyms[synonym] = set()
        self.synonyms[synonym].add(term)


class EnhancedTFIDF:
    """
    Enhanced TF-IDF with BM25 scoring and synonym support.
    """

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        """
        Initialize with BM25 parameters.

        Args:
            k1: Term frequency saturation parameter
            b: Length normalization parameter
        """
        self.k1 = k1
        self.b = b
        self.documents: list[Document] = []
        self.doc_freqs: dict[str, int] = Counter()
        self.doc_lengths: list[int] = []
        self.avg_doc_length: float = 0
        self.inverted_index: dict[str, list[tuple[int, int]]] = defaultdict(list)
        self.synonym_dict = SynonymDictionary()

    def _tokenize(self, text: str) -> list[str]:
        """
        Tokenize text with Chinese support.

        Uses jieba for Chinese, falls back to simple tokenization.
        """
        try:
            import jieba

            # Use jieba for Chinese text
            tokens = list(jieba.cut(text.lower()))
        except ImportError:
            # Fallback: simple tokenization
            tokens = re.findall(r"[\w\u4e00-\u9fff]+", text.lower())

        # Filter out very short tokens
        return [t for t in tokens if len(t) > 1]

    def _compute_tf(self, term: str, doc_tokens: list[str]) -> float:
        """Compute term frequency with BM25."""
        term_count = doc_tokens.count(term)
        doc_length = len(doc_tokens)

        # BM25 TF component
        tf = (term_count * (self.k1 + 1)) / (
            term_count + self.k1 * (1 - self.b + self.b * doc_length / self.avg_doc_length)
        )
        return tf

    def _compute_idf(self, term: str) -> float:
        """Compute inverse document frequency."""
        n_docs = len(self.documents)
        doc_freq = self.doc_freqs.get(term, 0)

        if doc_freq == 0:
            return 0.0

        # IDF with smoothing
        return math.log((n_docs - doc_freq + 0.5) / (doc_freq + 0.5) + 1)

    def add_document(self, doc: Document):
        """Add a document to the index."""
        self.documents.append(doc)
        doc_id = len(self.documents) - 1

        # Tokenize
        tokens = self._tokenize(doc.title + " " + doc.content)
        self.doc_lengths.append(len(tokens))

        # Update average document length
        self.avg_doc_length = sum(self.doc_lengths) / len(self.doc_lengths)

        # Update document frequencies and inverted index
        term_counts = Counter(tokens)
        for term, count in term_counts.items():
            self.doc_freqs[term] += 1
            self.inverted_index[term].append((doc_id, count))

    def search(self, query: str, top_k: int = 5) -> list[SearchResult]:
        """
        Search with BM25 scoring and synonym expansion.

        Args:
            query: Search query
            top_k: Number of results to return

        Returns:
            List of search results sorted by relevance
        """
        # Tokenize query
        query_terms = self._tokenize(query)

        # Expand with synonyms
        expanded_terms = self.synonym_dict.expand(query_terms)

        # Compute scores for each document
        scores: dict[int, float] = defaultdict(float)
        match_terms: dict[int, set[str]] = defaultdict(set)

        for term in expanded_terms:
            if term not in self.inverted_index:
                continue

            idf = self._compute_idf(term)

            for doc_id, term_count in self.inverted_index[term]:
                # Get document tokens for TF computation
                doc = self.documents[doc_id]
                doc_tokens = self._tokenize(doc.title + " " + doc.content)

                tf = self._compute_tf(term, doc_tokens)
                scores[doc_id] += tf * idf
                match_terms[doc_id].add(term)

        # Sort by score
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]

        # Build results
        results = []
        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]

            # Generate snippet
            snippet = self._generate_snippet(doc, query_terms)

            results.append(SearchResult(doc=doc, score=score, snippet=snippet, match_terms=list(match_terms[doc_id])))

        return results

    def _generate_snippet(self, doc: Document, query_terms: list[str], max_length: int = 200) -> str:
        """Generate a relevant snippet from the document."""
        content = doc.content

        # Find the best matching paragraph
        paragraphs = content.split("\n")
        best_paragraph = paragraphs[0] if paragraphs else ""
        best_score = 0

        for para in paragraphs:
            para_lower = para.lower()
            score = sum(1 for term in query_terms if term in para_lower)
            if score > best_score:
                best_score = score
                best_paragraph = para

        # Truncate to max_length
        if len(best_paragraph) > max_length:
            best_paragraph = best_paragraph[:max_length] + "..."

        return best_paragraph

    def get_stats(self) -> dict:
        """Get index statistics."""
        return {
            "total_documents": len(self.documents),
            "total_terms": len(self.doc_freqs),
            "average_doc_length": self.avg_doc_length,
        }


def create_enhanced_index(documents: list[Document]) -> EnhancedTFIDF:
    """
    Create an enhanced TF-IDF index.

    Args:
        documents: List of documents to index

    Returns:
        EnhancedTFIDF index
    """
    index = EnhancedTFIDF()
    for doc in documents:
        index.add_document(doc)
    return index

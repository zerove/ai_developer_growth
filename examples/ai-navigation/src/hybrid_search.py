"""
Hybrid Search Engine

Combines BM25 (keyword) + Vector (semantic) search with reciprocal rank fusion.
Provides the best of both worlds: precise keyword matching + semantic understanding.
"""

import logging
from dataclasses import dataclass

from .enhanced_tfidf import (
    Document as TFIDFDocument,
)
from .enhanced_tfidf import (
    EnhancedTFIDF,
)
from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


@dataclass
class HybridSearchResult:
    """A single hybrid search result."""

    doc_id: str
    title: str
    bm25_score: float
    vector_score: float
    combined_score: float
    snippet: str
    doc_type: str
    search_method: str  # "bm25", "vector", "hybrid"


class HybridSearchEngine:
    """Combines BM25 and vector search with reciprocal rank fusion.

    Usage:
        engine = HybridSearchEngine()
        engine.add_document("doc1", "Title", "Content...", "methodology")
        results = engine.search("How to learn AI", top_k=5)
    """

    def __init__(
        self,
        bm25_weight: float = 0.4,
        vector_weight: float = 0.6,
        model_name: str = "all-MiniLM-L6-v2",
    ):
        """Initialize hybrid search engine.

        Args:
            bm25_weight: Weight for BM25 scores (0-1).
            vector_weight: Weight for vector scores (0-1).
            model_name: Sentence-transformers model for vector search.
        """
        self.bm25_weight = bm25_weight
        self.vector_weight = vector_weight
        self.bm25_engine = EnhancedTFIDF()
        self.vector_engine = VectorSearchEngine(model_name=model_name)
        self._doc_count = 0

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        doc_type: str,
        tags: list[str] | None = None,
        category: str = "",
    ) -> None:
        """Add a document to both search engines."""
        # Add to BM25
        doc = TFIDFDocument(
            id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            tags=tags or [],
            category=category,
        )
        self.bm25_engine.add_document(doc)

        # Add to vector
        self.vector_engine.add_document(
            doc_id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            tags=tags,
            category=category,
        )

        self._doc_count += 1

    def search(
        self,
        query: str,
        top_k: int = 5,
        mode: str = "hybrid",
        doc_type_filter: str | None = None,
    ) -> list[HybridSearchResult]:
        """Search using specified mode.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            mode: Search mode - "hybrid", "bm25", or "vector".
            doc_type_filter: Optional filter by document type.

        Returns:
            List of HybridSearchResult sorted by combined score.
        """
        if mode == "bm25":
            return self._search_bm25(query, top_k, doc_type_filter)
        elif mode == "vector":
            return self._search_vector(query, top_k, doc_type_filter)
        else:
            return self._search_hybrid(query, top_k, doc_type_filter)

    def _search_bm25(
        self, query: str, top_k: int, doc_type_filter: str | None
    ) -> list[HybridSearchResult]:
        """BM25-only search."""
        results = self.bm25_engine.search(query, top_k=top_k)
        output = []
        for r in results:
            if doc_type_filter and r.doc.doc_type != doc_type_filter:
                continue
            output.append(
                HybridSearchResult(
                    doc_id=r.doc.id,
                    title=r.doc.title,
                    bm25_score=r.score,
                    vector_score=0.0,
                    combined_score=r.score,
                    snippet=r.snippet,
                    doc_type=r.doc.doc_type,
                    search_method="bm25",
                )
            )
        return output

    def _search_vector(
        self, query: str, top_k: int, doc_type_filter: str | None
    ) -> list[HybridSearchResult]:
        """Vector-only search."""
        results = self.vector_engine.search(
            query, top_k=top_k, doc_type_filter=doc_type_filter
        )
        output = []
        for r in results:
            output.append(
                HybridSearchResult(
                    doc_id=r.doc_id,
                    title=r.title,
                    bm25_score=0.0,
                    vector_score=r.score,
                    combined_score=r.score,
                    snippet=r.snippet,
                    doc_type=r.doc_type,
                    search_method="vector",
                )
            )
        return output

    def _search_hybrid(
        self, query: str, top_k: int, doc_type_filter: str | None
    ) -> list[HybridSearchResult]:
        """Hybrid search with reciprocal rank fusion."""
        bm25_results = self.bm25_engine.search(query, top_k=top_k * 2)
        vector_results = self.vector_engine.search(
            query, top_k=top_k * 2, doc_type_filter=doc_type_filter
        )

        # Reciprocal Rank Fusion
        k = 60  # RRF constant
        scores: dict[str, dict] = {}

        for rank, r in enumerate(bm25_results):
            if doc_type_filter and r.doc.doc_type != doc_type_filter:
                continue
            doc_id = r.doc.id
            if doc_id not in scores:
                scores[doc_id] = {
                    "title": r.doc.title,
                    "doc_type": r.doc.doc_type,
                    "snippet": r.snippet,
                    "bm25_score": r.score,
                    "vector_score": 0.0,
                    "rrf_score": 0.0,
                }
            scores[doc_id]["rrf_score"] += self.bm25_weight / (k + rank + 1)
            scores[doc_id]["bm25_score"] = r.score

        for rank, r in enumerate(vector_results):
            doc_id = r.doc_id
            if doc_id not in scores:
                scores[doc_id] = {
                    "title": r.title,
                    "doc_type": r.doc_type,
                    "snippet": r.snippet,
                    "bm25_score": 0.0,
                    "vector_score": r.score,
                    "rrf_score": 0.0,
                }
            scores[doc_id]["rrf_score"] += self.vector_weight / (k + rank + 1)
            scores[doc_id]["vector_score"] = r.score
            # Prefer vector snippet if available (often more relevant)
            if r.snippet:
                scores[doc_id]["snippet"] = r.snippet

        # Sort by RRF score
        sorted_docs = sorted(
            scores.items(), key=lambda x: x[1]["rrf_score"], reverse=True
        )[:top_k]

        return [
            HybridSearchResult(
                doc_id=doc_id,
                title=data["title"],
                bm25_score=data["bm25_score"],
                vector_score=data["vector_score"],
                combined_score=data["rrf_score"],
                snippet=data["snippet"],
                doc_type=data["doc_type"],
                search_method="hybrid",
            )
            for doc_id, data in sorted_docs
        ]

    @property
    def document_count(self) -> int:
        """Number of documents in the index."""
        return self._doc_count

    def get_stats(self) -> dict:
        """Get engine statistics."""
        return {
            "total_documents": self._doc_count,
            "bm25_weight": self.bm25_weight,
            "vector_weight": self.vector_weight,
            "vector_model": self.vector_engine.model_name,
        }

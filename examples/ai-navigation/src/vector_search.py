"""
Vector Search Engine

Semantic search using sentence-transformers embeddings + cosine similarity.
Provides a pluggable vector backend alongside the existing BM25 engine.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class VectorDocument:
    """A document stored in the vector index."""

    id: str
    title: str
    content: str
    doc_type: str
    tags: list[str] = field(default_factory=list)
    category: str = ""
    embedding: np.ndarray | None = None


@dataclass
class VectorSearchResult:
    """A single vector search result."""

    doc_id: str
    title: str
    score: float
    snippet: str
    doc_type: str


class VectorSearchEngine:
    """Semantic search engine using sentence-transformers embeddings.

    Usage:
        engine = VectorSearchEngine()
        engine.add_document("doc1", "Title", "Content here...", "methodology")
        results = engine.search("How to learn AI", top_k=5)
    """

    def __init__(
        self,
        model_name: str = "all-MiniLM-L6-v2",
        embedding_dim: int = 384,
    ):
        """Initialize the vector search engine.

        Args:
            model_name: Sentence-transformers model name for embeddings.
            embedding_dim: Dimension of the embedding vectors.
        """
        self.model_name = model_name
        self.embedding_dim = embedding_dim
        self._model = None
        self._documents: dict[str, VectorDocument] = {}
        self._embeddings: np.ndarray | None = None
        self._doc_ids: list[str] = []

    @property
    def model(self):
        """Lazy-load the sentence-transformers model."""
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer

                self._model = SentenceTransformer(self.model_name)
                logger.info(f"Loaded embedding model: {self.model_name}")
            except ImportError:
                raise ImportError(
                    "sentence-transformers is required for vector search. "
                    "Install with: pip install sentence-transformers"
                )
        return self._model

    def add_document(
        self,
        doc_id: str,
        title: str,
        content: str,
        doc_type: str,
        tags: list[str] | None = None,
        category: str = "",
    ) -> None:
        """Add a document to the vector index."""
        doc = VectorDocument(
            id=doc_id,
            title=title,
            content=content,
            doc_type=doc_type,
            tags=tags or [],
            category=category,
        )
        self._documents[doc_id] = doc
        # Invalidate the cached embeddings
        self._embeddings = None
        self._doc_ids = []

    def _build_index(self) -> None:
        """Build/rebuild the embedding index from all documents."""
        if not self._documents:
            return

        self._doc_ids = list(self._documents.keys())
        texts = []
        for doc_id in self._doc_ids:
            doc = self._documents[doc_id]
            # Combine title + content for richer embedding
            text = f"{doc.title} {doc.content}"
            texts.append(text)

        self._embeddings = self.model.encode(
            texts, show_progress_bar=False, convert_to_numpy=True
        )
        logger.info(f"Built vector index: {len(self._doc_ids)} documents")

    def search(
        self,
        query: str,
        top_k: int = 5,
        doc_type_filter: str | None = None,
    ) -> list[VectorSearchResult]:
        """Semantic search using cosine similarity.

        Args:
            query: Search query string.
            top_k: Number of results to return.
            doc_type_filter: Optional filter by document type.

        Returns:
            List of VectorSearchResult sorted by relevance (descending).
        """
        if not self._documents:
            return []

        # Build index if needed
        if self._embeddings is None:
            self._build_index()

        # Encode query
        query_embedding = self.model.encode(
            [query], show_progress_bar=False, convert_to_numpy=True
        )

        # Cosine similarity
        similarities = self._cosine_similarity(query_embedding, self._embeddings)[0]

        # Apply doc_type filter
        if doc_type_filter:
            for i, doc_id in enumerate(self._doc_ids):
                if self._documents[doc_id].doc_type != doc_type_filter:
                    similarities[i] = -1.0

        # Get top-k indices
        top_indices = np.argsort(similarities)[::-1][:top_k]

        results = []
        for idx in top_indices:
            if similarities[idx] < 0:
                continue
            doc_id = self._doc_ids[idx]
            doc = self._documents[doc_id]
            snippet = self._generate_snippet(doc, query)
            results.append(
                VectorSearchResult(
                    doc_id=doc_id,
                    title=doc.title,
                    score=float(similarities[idx]),
                    snippet=snippet,
                    doc_type=doc.doc_type,
                )
            )

        return results

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> np.ndarray:
        """Compute cosine similarity between two sets of vectors."""
        a_norm = a / (np.linalg.norm(a, axis=1, keepdims=True) + 1e-8)
        b_norm = b / (np.linalg.norm(b, axis=1, keepdims=True) + 1e-8)
        return a_norm @ b_norm.T

    def _generate_snippet(
        self, doc: VectorDocument, query: str, max_length: int = 200
    ) -> str:
        """Generate a relevant snippet from the document."""
        content = doc.content
        if len(content) <= max_length:
            return content

        # Try to find the most relevant section
        query_lower = query.lower()
        best_pos = 0
        best_score = 0
        words = content.split()

        for i in range(0, len(words), 5):
            window = " ".join(words[i : i + 20]).lower()
            score = sum(1 for w in query_lower.split() if w in window)
            if score > best_score:
                best_score = score
                best_pos = i

        snippet_words = words[best_pos : best_pos + 30]
        snippet = " ".join(snippet_words)
        if len(snippet) > max_length:
            snippet = snippet[:max_length] + "..."
        return snippet

    @property
    def document_count(self) -> int:
        """Number of documents in the index."""
        return len(self._documents)

    def save(self, path: str | Path) -> None:
        """Save the vector index to disk."""
        path = Path(path)
        path.mkdir(parents=True, exist_ok=True)

        # Save document metadata
        meta = {}
        for doc_id, doc in self._documents.items():
            meta[doc_id] = {
                "title": doc.title,
                "content": doc.content,
                "doc_type": doc.doc_type,
                "tags": doc.tags,
                "category": doc.category,
            }
        (path / "documents.json").write_text(
            json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # Save embeddings
        if self._embeddings is not None:
            np.save(str(path / "embeddings.npy"), self._embeddings)

        # Save doc_ids order
        (path / "doc_ids.json").write_text(json.dumps(self._doc_ids), encoding="utf-8")

        logger.info(f"Saved vector index to {path}")

    @classmethod
    def load(
        cls, path: str | Path, model_name: str = "all-MiniLM-L6-v2"
    ) -> "VectorSearchEngine":
        """Load a vector index from disk."""
        path = Path(path)
        engine = cls(model_name=model_name)

        # Load metadata
        meta = json.loads((path / "documents.json").read_text(encoding="utf-8"))
        for doc_id, data in meta.items():
            engine._documents[doc_id] = VectorDocument(id=doc_id, **data)

        # Load embeddings
        emb_path = path / "embeddings.npy"
        if emb_path.exists():
            engine._embeddings = np.load(str(emb_path))

        # Load doc_ids
        ids_path = path / "doc_ids.json"
        if ids_path.exists():
            engine._doc_ids = json.loads(ids_path.read_text(encoding="utf-8"))

        logger.info(f"Loaded vector index from {path}: {len(meta)} documents")
        return engine

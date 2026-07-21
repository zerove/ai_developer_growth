"""Tests for Vector Search and Hybrid Search engines."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.vector_search import VectorDocument, VectorSearchEngine, VectorSearchResult

# ---------------------------------------------------------------------------
# VectorSearchEngine Tests
# ---------------------------------------------------------------------------


class TestVectorDocument:
    """Tests for VectorDocument dataclass."""

    def test_creation(self):
        doc = VectorDocument(id="1", title="T", content="C", doc_type="test")
        assert doc.id == "1"
        assert doc.tags == []

    def test_with_tags(self):
        doc = VectorDocument(
            id="1", title="T", content="C", doc_type="test", tags=["a", "b"]
        )
        assert len(doc.tags) == 2


class TestVectorSearchEngine:
    """Tests for VectorSearchEngine."""

    def test_empty_search(self):
        engine = VectorSearchEngine()
        results = engine.search("test query")
        assert results == []

    def test_add_document(self):
        engine = VectorSearchEngine()
        engine.add_document("1", "Title", "Content", "methodology")
        assert engine.document_count == 1

    def test_add_multiple_documents(self):
        engine = VectorSearchEngine()
        engine.add_document("1", "T1", "C1", "methodology")
        engine.add_document("2", "T2", "C2", "case_study")
        engine.add_document("3", "T3", "C3", "adr")
        assert engine.document_count == 3

    @patch.object(VectorSearchEngine, "model")
    def test_search_returns_results(self, mock_model):
        """Test that search works with mocked embeddings."""
        import numpy as np

        # Mock model.encode to return known embeddings
        mock_model.encode = MagicMock(
            side_effect=lambda texts, **kwargs: np.array([[1.0, 0.0, 0.0]] * len(texts))
        )

        engine = VectorSearchEngine()
        engine.add_document("1", "Python Guide", "Learn Python basics", "methodology")
        engine.add_document(
            "2", "JavaScript Guide", "Learn JavaScript basics", "methodology"
        )
        engine.add_document("3", "AI Tools", "AI development tools", "tool")

        results = engine.search("Python programming", top_k=2)
        assert len(results) <= 2
        assert all(isinstance(r, VectorSearchResult) for r in results)

    @patch.object(VectorSearchEngine, "model")
    def test_search_with_doc_type_filter(self, mock_model):
        import numpy as np

        mock_model.encode = MagicMock(
            side_effect=lambda texts, **kwargs: np.array([[1.0, 0.0, 0.0]] * len(texts))
        )

        engine = VectorSearchEngine()
        engine.add_document("1", "T1", "C1", "methodology")
        engine.add_document("2", "T2", "C2", "case_study")

        results = engine.search("test", doc_type_filter="methodology")
        # Only methodology docs should be returned
        for r in results:
            assert r.doc_type == "methodology"

    def test_generate_snippet_short_content(self):
        engine = VectorSearchEngine()
        doc = VectorDocument(
            id="1", title="T", content="Short content", doc_type="test"
        )
        snippet = engine._generate_snippet(doc, "query")
        assert snippet == "Short content"

    def test_generate_snippet_long_content(self):
        engine = VectorSearchEngine()
        content = " ".join(["word"] * 200)
        doc = VectorDocument(id="1", title="T", content=content, doc_type="test")
        snippet = engine._generate_snippet(doc, "query", max_length=100)
        assert len(snippet) <= 110  # Allow for "..." at end

    def test_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            engine = VectorSearchEngine()
            engine.add_document("1", "T1", "C1", "methodology")
            engine.add_document("2", "T2", "C2", "case_study")

            # Mock embeddings for saving
            import numpy as np

            engine._embeddings = np.array([[1.0, 0.0], [0.0, 1.0]])
            engine._doc_ids = ["1", "2"]

            save_path = Path(tmpdir) / "index"
            engine.save(save_path)

            # Verify files exist
            assert (save_path / "documents.json").exists()
            assert (save_path / "embeddings.npy").exists()
            assert (save_path / "doc_ids.json").exists()

            # Load and verify
            loaded = VectorSearchEngine.load(save_path)
            assert loaded.document_count == 2

    def test_cosine_similarity(self):
        engine = VectorSearchEngine()
        import numpy as np

        a = np.array([[1.0, 0.0, 0.0]])
        b = np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        sim = engine._cosine_similarity(a, b)
        assert abs(sim[0][0] - 1.0) < 1e-6  # Identical vectors
        assert abs(sim[0][1]) < 1e-6  # Orthogonal vectors

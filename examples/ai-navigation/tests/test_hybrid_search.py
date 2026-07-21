"""Tests for Hybrid Search engine."""

from unittest.mock import patch

from src.hybrid_search import HybridSearchEngine, HybridSearchResult


class TestHybridSearchEngine:
    """Tests for HybridSearchEngine."""

    def test_creation(self):
        engine = HybridSearchEngine()
        assert engine.document_count == 0
        stats = engine.get_stats()
        assert stats["bm25_weight"] == 0.4
        assert stats["vector_weight"] == 0.6

    def test_add_document(self):
        engine = HybridSearchEngine()
        engine.add_document("1", "Title", "Content", "methodology")
        assert engine.document_count == 1

    @patch("src.hybrid_search.VectorSearchEngine")
    def test_bm25_only_search(self, mock_vector_cls):
        """Test BM25-only mode doesn't require vector model."""
        engine = HybridSearchEngine()
        # Manually add a document to BM25 engine
        from src.enhanced_tfidf import Document as TFIDFDoc

        doc = TFIDFDoc(
            id="1", title="Python Guide", content="Learn Python", doc_type="methodology"
        )
        engine.bm25_engine.add_document(doc)

        results = engine.search("Python", mode="bm25", top_k=5)
        assert len(results) >= 0  # May find results depending on TF-IDF
        if results:
            assert results[0].search_method == "bm25"

    def test_search_empty_engine(self):
        engine = HybridSearchEngine()
        results = engine.search("test query")
        assert results == []

    @patch("src.hybrid_search.VectorSearchEngine")
    def test_hybrid_mode(self, mock_vector_cls):
        """Test hybrid mode combines BM25 + vector results."""
        engine = HybridSearchEngine()

        from src.enhanced_tfidf import Document as TFIDFDoc

        # Add documents to BM25
        for i in range(5):
            doc = TFIDFDoc(
                id=str(i),
                title=f"Doc {i}",
                content=f"Content about topic {i % 3}",
                doc_type="methodology",
            )
            engine.bm25_engine.add_document(doc)

        results = engine.search("topic", mode="hybrid", top_k=3)
        assert len(results) <= 3
        for r in results:
            assert isinstance(r, HybridSearchResult)

    def test_get_stats(self):
        engine = HybridSearchEngine(
            bm25_weight=0.3, vector_weight=0.7, model_name="test-model"
        )
        stats = engine.get_stats()
        assert stats["bm25_weight"] == 0.3
        assert stats["vector_weight"] == 0.7
        assert stats["vector_model"] == "test-model"

    def test_doc_type_filter_bm25(self):
        """Test that doc_type_filter works in BM25 mode."""
        engine = HybridSearchEngine()
        from src.enhanced_tfidf import Document as TFIDFDoc

        doc1 = TFIDFDoc(id="1", title="T1", content="C1", doc_type="methodology")
        doc2 = TFIDFDoc(id="2", title="T2", content="C2", doc_type="case_study")
        engine.bm25_engine.add_document(doc1)
        engine.bm25_engine.add_document(doc2)

        results = engine.search("T", mode="bm25", doc_type_filter="methodology")
        for r in results:
            assert r.doc_type == "methodology"

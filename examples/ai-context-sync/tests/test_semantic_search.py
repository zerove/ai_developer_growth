"""Tests for semantic_search.py - TF-IDF based ADR search."""

import os
import tempfile

import pytest

from src.semantic_search import SemanticSearcher, compute_idf, compute_tf, cosine_similarity, tokenize


class TestTokenize:
    def test_basic_tokenization(self):
        tokens = tokenize("The quick brown fox")
        assert "quick" in tokens
        assert "brown" in tokens
        assert "fox" in tokens
        assert "the" not in tokens

    def test_stopwords_removed(self):
        tokens = tokenize("This is a test of the system")
        assert "is" not in tokens
        assert "a" not in tokens
        assert "test" in tokens
        assert "system" in tokens

    def test_empty_text(self):
        assert tokenize("") == []


class TestComputeTF:
    def test_basic_tf(self):
        tf = compute_tf(["a", "b", "a"])
        assert tf["a"] == pytest.approx(2 / 3)
        assert tf["b"] == pytest.approx(1 / 3)

    def test_empty_tokens(self):
        assert compute_tf([]) == {}


class TestComputeIDF:
    def test_basic_idf(self):
        docs = [["hello", "world"], ["hello", "test"]]
        idf = compute_idf(docs)
        assert idf["hello"] == pytest.approx(0.0)
        assert idf["world"] == pytest.approx(0.693, abs=0.01)
        assert idf["test"] == pytest.approx(0.693, abs=0.01)

    def test_empty_docs(self):
        assert compute_idf([]) == {}


class TestCosineSimilarity:
    def test_identical_vectors(self):
        vec = {"a": 1.0, "b": 2.0}
        assert cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_orthogonal_vectors(self):
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert cosine_similarity(vec_a, vec_b) == 0.0

    def test_no_common_keys(self):
        vec_a = {"a": 1.0}
        vec_b = {"b": 1.0}
        assert cosine_similarity(vec_a, vec_b) == 0.0


class TestSemanticSearcher:
    def test_index_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "adr001.md"), "w") as f:
                f.write("# ADR-001: Use PostgreSQL\n\nWe decided to use PostgreSQL for our database.")
            with open(os.path.join(tmpdir, "adr002.md"), "w") as f:
                f.write("# ADR-002: Use Redis\n\nWe decided to use Redis for caching.")
            searcher = SemanticSearcher()
            count = searcher.index_directory(tmpdir)
            assert count == 2

    def test_search_returns_relevant(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "adr001.md"), "w") as f:
                f.write("# ADR-001: Use PostgreSQL\n\nWe chose PostgreSQL for database storage.")
            with open(os.path.join(tmpdir, "adr002.md"), "w") as f:
                f.write("# ADR-002: Use Redis\n\nWe chose Redis for caching layer.")
            searcher = SemanticSearcher()
            searcher.index_directory(tmpdir)
            results = searcher.search("database", top_k=1)
            assert len(results) == 1
            assert "PostgreSQL" in results[0][0]

    def test_search_empty_query(self):
        searcher = SemanticSearcher()
        searcher.add_document("Some content")
        results = searcher.search("")
        assert results == []

    def test_search_no_documents(self):
        searcher = SemanticSearcher()
        results = searcher.search("anything")
        assert results == []

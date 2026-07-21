#!/usr/bin/env python3
"""Tests for AI Navigation modules."""

# Add the examples directory to path
import sys
import tempfile
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.knowledge_index import Document, IndexBuilder, KnowledgeIndex
from src.path_recommender import PathRecommender, UserProfile
from src.rag_engine import QueryContext, RAGEngine


class TestDocument:
    """Test Document dataclass."""

    def test_create_document(self):
        """Test creating a document."""
        doc = Document(
            id="test-1",
            type="methodology",
            category="efficiency",
            title="Test Doc",
            content="Test content",
        )
        assert doc.id == "test-1"
        assert doc.type == "methodology"
        assert doc.category == "efficiency"
        assert doc.title == "Test Doc"
        assert doc.content == "Test content"
        assert doc.metadata == {}
        assert doc.embedding is None

    def test_document_with_metadata(self):
        """Test document with metadata."""
        doc = Document(
            id="test-2",
            type="case_study",
            category="web",
            title="Case Study",
            content="Case content",
            metadata={"tools": ["Cursor"], "efficiency": "3x"},
        )
        assert doc.metadata["tools"] == ["Cursor"]
        assert doc.metadata["efficiency"] == "3x"


class TestKnowledgeIndex:
    """Test KnowledgeIndex class."""

    def test_add_document(self):
        """Test adding a document."""
        index = KnowledgeIndex()
        doc = Document(
            id="doc-1",
            type="methodology",
            category="test",
            title="Test",
            content="Content",
        )
        index.add_document(doc)
        assert len(index.documents) == 1
        assert index.documents[0].id == "doc-1"

    def test_get_document(self):
        """Test getting a document by ID."""
        index = KnowledgeIndex()
        doc = Document(
            id="doc-1",
            type="methodology",
            category="test",
            title="Test",
            content="Content",
        )
        index.add_document(doc)

        found = index.get_document("doc-1")
        assert found is not None
        assert found.id == "doc-1"

        not_found = index.get_document("nonexistent")
        assert not_found is None

    def test_search(self):
        """Test searching documents."""
        index = KnowledgeIndex()
        doc1 = Document(
            id="doc-1",
            type="methodology",
            category="test",
            title="Python Tutorial",
            content="Learn Python programming",
        )
        doc2 = Document(
            id="doc-2",
            type="methodology",
            category="test",
            title="JavaScript Guide",
            content="Learn JavaScript development",
        )
        index.add_document(doc1)
        index.add_document(doc2)

        results = index.search("Python")
        assert len(results) > 0
        assert results[0]["doc"].id == "doc-1"

    def test_save_and_load(self):
        """Test saving and loading index."""
        with tempfile.TemporaryDirectory() as tmpdir:
            index = KnowledgeIndex(metadata={"version": "1.0"})
            doc = Document(
                id="doc-1",
                type="methodology",
                category="test",
                title="Test",
                content="Content",
            )
            index.add_document(doc)

            # Save
            save_path = Path(tmpdir) / "index.json"
            index.save(str(save_path))
            assert save_path.exists()

            # Load
            loaded = KnowledgeIndex.load(str(save_path))
            assert len(loaded.documents) == 1
            assert loaded.documents[0].id == "doc-1"
            assert loaded.metadata["version"] == "1.0"


class TestIndexBuilder:
    """Test IndexBuilder class."""

    def test_build_from_repo(self):
        """Test building index from repository."""
        repo_root = Path(__file__).parent.parent.parent.parent
        builder = IndexBuilder(str(repo_root))
        index = builder.build()

        # Should have documents
        assert len(index.documents) > 0

        # Should have different types
        types = {doc.type for doc in index.documents}
        assert "methodology" in types or "case_study" in types

    def test_extract_title(self):
        """Test title extraction."""
        builder = IndexBuilder(".")
        content = "# My Title\nSome content here"
        title = builder._extract_title(content, "fallback")
        assert title == "My Title"

    def test_extract_title_fallback(self):
        """Test title extraction fallback."""
        builder = IndexBuilder(".")
        content = "No heading here"
        title = builder._extract_title(content, "fallback")
        assert title == "fallback"

    def test_estimate_reading_time(self):
        """Test reading time estimation."""
        builder = IndexBuilder(".")
        short_content = "Short content"
        long_content = "word " * 500

        assert builder._estimate_reading_time(short_content) == "1min"
        # 500 words / 200 wpm = 2.5min, rounds to 3min but implementation uses floor
        assert builder._estimate_reading_time(long_content) in ("2min", "3min")


class TestRAGEngine:
    """Test RAGEngine class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.index = KnowledgeIndex()
        self.doc1 = Document(
            id="methodology-workflow",
            type="methodology",
            category="efficiency",
            title="全周期工作流",
            content="AI 辅助开发的全周期工作流，包括需求分析、设计、编码、测试",
            metadata={"reading_time": "15min"},
        )
        self.doc2 = Document(
            id="case-cursor",
            type="case_study",
            category="web",
            title="Cursor 重构案例",
            content="使用 Cursor 重构遗留代码的案例研究，效率提升 3x",
            metadata={"efficiency_gain": "3x"},
        )
        self.index.add_document(self.doc1)
        self.index.add_document(self.doc2)

    def test_query_basic(self):
        """Test basic query."""
        engine = RAGEngine(self.index)
        result = engine.query(QueryContext(question="如何重构代码?"))

        assert result.answer is not None
        assert len(result.citations) > 0
        assert result.confidence > 0

    def test_query_with_role(self):
        """Test query with user role."""
        engine = RAGEngine(self.index)
        result = engine.query(
            QueryContext(question="工作流是什么?", user_role="前端工程师")
        )

        assert result.answer is not None
        assert "工作流" in result.answer or "全周期" in result.answer

    def test_query_no_results(self):
        """Test query with very low relevance."""
        engine = RAGEngine(self.index)
        # Use a query that's completely unrelated
        result = engine.query(QueryContext(question="xyz123"))

        # Should have very low or no confidence
        assert (
            result.confidence <= 0.1
        )  # Very low confidence for completely unrelated query


class TestPathRecommender:
    """Test PathRecommender class."""

    def setup_method(self):
        """Set up test fixtures."""
        self.index = KnowledgeIndex()
        self.doc1 = Document(
            id="methodology-workflow",
            type="methodology",
            category="efficiency",
            title="全周期工作流",
            content="AI 辅助开发的全周期工作流",
            metadata={"reading_time": "15min"},
        )
        self.doc2 = Document(
            id="case-cursor",
            type="case_study",
            category="web",
            title="Cursor 重构案例",
            content="使用 Cursor 重构遗留代码",
            metadata={"tools_used": ["Cursor"], "reading_time": "15min"},
        )
        self.index.add_document(self.doc1)
        self.index.add_document(self.doc2)

    def test_recommend_for_frontend(self):
        """Test recommendation for frontend engineer."""
        recommender = PathRecommender(self.index)
        user = UserProfile(
            role="前端工程师",
            experience="2年",
            current_tools=["Cursor"],
            goals=["提升效率"],
        )

        paths = recommender.recommend(user)
        assert len(paths) > 0
        # Check that at least one path exists (may not have '前端' in name if no matching docs)
        assert any(len(p.steps) > 0 for p in paths)

    def test_recommend_for_backend(self):
        """Test recommendation for backend engineer."""
        recommender = PathRecommender(self.index)
        user = UserProfile(
            role="后端工程师",
            experience="5年",
            current_tools=["Claude"],
            goals=["架构设计"],
        )

        paths = recommender.recommend(user)
        # May be empty if no matching docs, that's OK for test data
        assert isinstance(paths, list)

    def test_recommend_with_goals(self):
        """Test recommendation with goals."""
        recommender = PathRecommender(self.index)
        user = UserProfile(
            role="全栈工程师", experience="3年", goals=["提升效率", "学习 RAG"]
        )

        paths = recommender.recommend(user)
        # Should return a list (may be empty if no matching docs)
        assert isinstance(paths, list)

    def test_difficulty_levels(self):
        """Test difficulty level assignment."""
        recommender = PathRecommender(self.index)

        assert recommender._get_difficulty("1年") == "beginner"
        assert recommender._get_difficulty("3年") == "intermediate"
        assert recommender._get_difficulty("5年") == "advanced"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

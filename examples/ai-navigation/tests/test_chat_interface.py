"""Tests for Chat Interface."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.chat_interface import ChatInterface, ChatMessage, ChatSession
from src.vector_search import VectorSearchEngine, VectorSearchResult

# ---------------------------------------------------------------------------
# ChatMessage Tests
# ---------------------------------------------------------------------------


class TestChatMessage:
    def test_creation(self):
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"
        assert msg.sources == []


class TestChatSession:
    def test_add_messages(self):
        session = ChatSession()
        session.add_user_message("Question")
        session.add_assistant_message("Answer", sources=[{"title": "Doc1"}])
        assert len(session.messages) == 2
        assert session.messages[0].role == "user"
        assert session.messages[1].role == "assistant"

    def test_get_context(self):
        session = ChatSession()
        session.add_user_message("你好")
        session.add_assistant_message("你好！")
        ctx = session.get_context()
        assert "用户: 你好" in ctx
        assert "助手: 你好！" in ctx

    def test_clear(self):
        session = ChatSession()
        session.add_user_message("test")
        session.clear()
        assert len(session.messages) == 0

    def test_max_history(self):
        session = ChatSession(max_history=2)
        for i in range(5):
            session.add_user_message(f"msg {i}")
        ctx = session.get_context()
        assert "msg 3" in ctx
        assert "msg 4" in ctx
        assert "msg 0" not in ctx


# ---------------------------------------------------------------------------
# ChatInterface Tests
# ---------------------------------------------------------------------------


class TestChatInterface:
    @patch.object(VectorSearchEngine, "model")
    def test_ask_empty_engine(self, mock_model):
        engine = VectorSearchEngine()
        chat = ChatInterface(engine)
        result = chat.ask("test question")
        assert "没有找到" in result["answer"]
        assert result["sources"] == []
        assert result["confidence"] == 0.0

    @patch.object(VectorSearchEngine, "model")
    def test_ask_with_results(self, mock_model):
        import numpy as np

        mock_model.encode = MagicMock(
            side_effect=lambda texts, **kwargs: np.array([[1.0, 0.0]] * len(texts))
        )

        engine = VectorSearchEngine()
        engine.add_document(
            "1", "AI 协作开发", "如何用 AI 进行协作开发的完整指南", "methodology"
        )
        engine.add_document("2", "Prompt 工程", "Prompt 设计的最佳实践", "methodology")

        chat = ChatInterface(engine)
        result = chat.ask("如何学习 AI 协作？")

        assert len(result["sources"]) > 0
        assert result["confidence"] > 0
        assert "AI 协作" in result["answer"] or "找到" in result["answer"]

    @patch.object(VectorSearchEngine, "model")
    def test_ask_maintains_history(self, mock_model):
        engine = VectorSearchEngine()
        chat = ChatInterface(engine)
        chat.ask("question 1")
        chat.ask("question 2")
        assert len(chat.get_history()) == 4  # 2 user + 2 assistant

    def test_clear(self):
        engine = VectorSearchEngine()
        chat = ChatInterface(engine)
        chat.session.add_user_message("test")
        chat.clear()
        assert len(chat.get_history()) == 0

    @patch.object(VectorSearchEngine, "model")
    def test_export_history(self, mock_model):
        engine = VectorSearchEngine()
        chat = ChatInterface(engine)
        chat.ask("test question")

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "history.json"
            chat.export_history(path)
            assert path.exists()
            data = path.read_text()
            assert "test question" in data

    def test_generate_answer_confidence_levels(self):
        engine = VectorSearchEngine()
        chat = ChatInterface(engine)

        # High confidence
        results = [VectorSearchResult("1", "T", 0.8, "snippet", "methodology")]
        answer, conf = chat._generate_answer("q", results)
        assert conf == 0.8
        assert "高度相关" in answer

        # Medium confidence
        results = [VectorSearchResult("1", "T", 0.5, "snippet", "methodology")]
        answer, conf = chat._generate_answer("q", results)
        assert "中度相关" in answer

        # Low confidence
        results = [VectorSearchResult("1", "T", 0.2, "snippet", "methodology")]
        answer, conf = chat._generate_answer("q", results)
        assert "可能相关" in answer

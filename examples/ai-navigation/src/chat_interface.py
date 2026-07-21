"""
Chat Interface

CLI-based conversational Q&A over the knowledge base.
Uses vector search for retrieval and template-based answer generation.
Works without external LLM - uses knowledge base snippets directly.
"""

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


@dataclass
class ChatMessage:
    """A single chat message."""

    role: str  # "user" or "assistant"
    content: str
    sources: list[dict] = field(default_factory=list)


@dataclass
class ChatSession:
    """A chat session with history."""

    messages: list[ChatMessage] = field(default_factory=list)
    max_history: int = 10

    def add_user_message(self, content: str) -> None:
        self.messages.append(ChatMessage(role="user", content=content))

    def add_assistant_message(
        self, content: str, sources: list[dict] | None = None
    ) -> None:
        self.messages.append(
            ChatMessage(role="assistant", content=content, sources=sources or [])
        )

    def get_context(self) -> str:
        """Get recent conversation context as string."""
        recent = self.messages[-self.max_history :]
        lines = []
        for msg in recent:
            prefix = "用户" if msg.role == "user" else "助手"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def clear(self) -> None:
        self.messages.clear()


class ChatInterface:
    """Conversational Q&A interface over the knowledge base.

    Usage:
        chat = ChatInterface(vector_engine)
        answer = chat.ask("如何学习 AI 协作开发？")
    """

    def __init__(
        self,
        search_engine: VectorSearchEngine,
        top_k: int = 3,
    ):
        """Initialize chat interface.

        Args:
            search_engine: VectorSearchEngine for document retrieval.
            top_k: Number of documents to retrieve per query.
        """
        self.search_engine = search_engine
        self.top_k = top_k
        self.session = ChatSession()

    def ask(self, question: str) -> dict:
        """Ask a question and get an answer with sources.

        Args:
            question: User's question.

        Returns:
            Dict with 'answer', 'sources', and 'confidence'.
        """
        self.session.add_user_message(question)

        # Retrieve relevant documents
        results = self.search_engine.search(question, top_k=self.top_k)

        if not results:
            answer = "抱歉，知识库中没有找到相关信息。请尝试换个问法。"
            self.session.add_assistant_message(answer)
            return {"answer": answer, "sources": [], "confidence": 0.0}

        # Generate answer from retrieved documents
        answer, confidence = self._generate_answer(question, results)

        # Build sources list
        sources = [
            {
                "title": r.title,
                "doc_type": r.doc_type,
                "score": round(r.score, 3),
                "snippet": r.snippet[:200],
            }
            for r in results
        ]

        self.session.add_assistant_message(answer, sources)

        return {
            "answer": answer,
            "sources": sources,
            "confidence": confidence,
        }

    def _generate_answer(self, question: str, results: list) -> tuple[str, float]:
        """Generate an answer from search results.

        Args:
            question: The user's question.
            results: List of VectorSearchResult.

        Returns:
            Tuple of (answer_text, confidence_score).
        """
        if not results:
            return "没有找到相关文档。", 0.0

        # Calculate average relevance
        avg_score = sum(r.score for r in results) / len(results)

        # Build answer from top results
        parts = []
        parts.append(f"根据知识库，找到 {len(results)} 个相关文档：\n")

        for i, r in enumerate(results, 1):
            parts.append(f"**{i}. {r.title}** ({r.doc_type})")
            # Clean up snippet
            snippet = r.snippet.strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            parts.append(f"   {snippet}\n")

        # Add recommendation
        if avg_score > 0.7:
            confidence_text = "高度相关"
        elif avg_score > 0.4:
            confidence_text = "中度相关"
        else:
            confidence_text = "可能相关"

        parts.append(f"---\n*置信度: {confidence_text} (平均得分: {avg_score:.3f})*")

        return "\n".join(parts), avg_score

    def get_history(self) -> list[dict]:
        """Get chat history as list of dicts."""
        return [
            {
                "role": msg.role,
                "content": msg.content,
                "sources": msg.sources,
            }
            for msg in self.session.messages
        ]

    def clear(self) -> None:
        """Clear chat history."""
        self.session.clear()

    def export_history(self, path: str | Path) -> None:
        """Export chat history to JSON."""
        history = self.get_history()
        Path(path).write_text(
            json.dumps(history, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        logger.info(f"Exported chat history to {path}")

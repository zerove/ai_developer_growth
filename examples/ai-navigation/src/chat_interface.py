"""
Enhanced Chat Interface with Multi-turn Conversation, Context Management, and Source Citations

Features:
- Multi-turn dialogue with history management
- Entity tracking across turns
- Intent clarification and follow-up questions
- Source citations with document references
- LLM Provider integration (OpenAI/Claude/Gemini/Ollama/System)
- Hybrid search (BM25 + Vector + RRF)
- Session persistence (export/import)
- CLI interactive mode + REST API ready
"""

import json
import logging
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

from .hybrid_search import HybridSearchEngine, HybridSearchResult
from .llm_client import LLMClient
from .vector_search import VectorSearchEngine

logger = logging.getLogger(__name__)


class ConversationRole(Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class SourceCitation:
    """A citation to a source document."""

    doc_id: str
    title: str
    doc_type: str
    score: float
    snippet: str
    search_method: str = "hybrid"
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    def format_markdown(self) -> str:
        """Format as markdown citation."""
        return f"[{self.title}]({self.url or f'#doc-{self.doc_id}'}) - {self.doc_type} (相关度: {self.score:.3f})"


@dataclass
class ChatMessage:
    """A single chat message with full metadata."""

    def __init__(
        self,
        role: ConversationRole | str = ConversationRole.USER,
        content: str = "",
        sources: list = None,
        metadata: dict = None,
        message_id: str = None,
        timestamp: str = None,
    ):
        # Use object.__setattr__ to bypass dataclass init
        object.__setattr__(self, "_role", ConversationRole.USER)
        object.__setattr__(self, "content", content)
        object.__setattr__(self, "sources", sources if sources is not None else [])
        object.__setattr__(self, "metadata", metadata if metadata is not None else {})
        object.__setattr__(
            self,
            "message_id",
            message_id if message_id is not None else str(uuid.uuid4())[:8],
        )
        object.__setattr__(
            self,
            "timestamp",
            timestamp if timestamp is not None else datetime.now().isoformat(),
        )

        # Handle role parameter
        if isinstance(role, str):
            try:
                self._role = ConversationRole(role)
            except ValueError:

                class _DummyRole:
                    def __init__(self, val):
                        self.value = val

                self._role = _DummyRole(role)
        elif isinstance(role, ConversationRole):
            self._role = role

    @property
    def role_str(self) -> str:
        """Get role as string (for backward compatibility with tests)."""
        return self._role.value

    @property
    def role(self) -> str:
        """Get role as string."""
        return self._role.value

    @role.setter
    def role(self, value: ConversationRole | str):
        if isinstance(value, str):
            try:
                self._role = ConversationRole(value)
            except ValueError:

                class _DummyRole:
                    def __init__(self, val):
                        self.value = val

                self._role = _DummyRole(value)
        else:
            self._role = value

    def to_dict(self) -> dict:
        return {
            "role": self.role,
            "content": self.content,
            "sources": [s.to_dict() for s in self.sources],
            "metadata": self.metadata,
            "message_id": self.message_id,
            "timestamp": self.timestamp,
        }


@dataclass
class Entity:
    """Tracked entity in conversation."""

    name: str
    type: str  # document, concept, tool, person, etc.
    references: list[str] = field(default_factory=list)  # message_ids
    metadata: dict = field(default_factory=dict)


@dataclass
class ChatSession:
    """A chat session with full context management."""

    session_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    messages: list[ChatMessage] = field(default_factory=list)
    entities: dict[str, Entity] = field(default_factory=dict)
    max_history: int = 20
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def add_message(self, message: ChatMessage) -> None:
        self.messages.append(message)
        self.updated_at = datetime.now().isoformat()
        # Track entities mentioned
        self._extract_entities(message)

    def _extract_entities(self, message: ChatMessage) -> None:
        """Simple entity extraction from message content."""
        # Track document references
        for source in message.sources:
            if source.doc_id not in self.entities:
                self.entities[source.doc_id] = Entity(
                    name=source.title,
                    type="document",
                    references=[message.message_id],
                    metadata={"doc_type": source.doc_type, "score": source.score},
                )
            else:
                self.entities[source.doc_id].references.append(message.message_id)

    def get_recent_context(self, max_turns: int = 5) -> list[ChatMessage]:
        """Get recent conversation context for LLM."""
        # Return last N user-assistant pairs
        pairs = []
        for msg in reversed(self.messages):
            pairs.append(msg)
            if len(pairs) >= max_turns * 2:
                break
        return list(reversed(pairs))

    def get_full_context(self) -> str:
        """Get formatted conversation history."""
        lines = []
        for msg in self.messages[-self.max_history :]:
            prefix = "用户" if msg._role == ConversationRole.USER else "助手"
            lines.append(f"{prefix}: {msg.content}")
        return "\n".join(lines)

    def get_context(self) -> str:
        """Get formatted conversation history (alias for backward compat)."""
        return self.get_full_context()

    def clear(self) -> None:
        self.messages.clear()
        self.entities.clear()
        self.updated_at = datetime.now().isoformat()

    def add_user_message(self, content: str) -> None:
        """Add a user message (backward compatible)."""
        msg = ChatMessage(role=ConversationRole.USER, content=content)
        self.add_message(msg)

    def add_assistant_message(self, content: str, sources: list = None) -> None:
        """Add an assistant message (backward compatible)."""
        source_citations = []
        if sources:
            for s in sources:
                if isinstance(s, dict):
                    # Handle incomplete source dicts (from tests)
                    source_citations.append(
                        SourceCitation(
                            doc_id=s.get("doc_id", "unknown"),
                            title=s.get("title", "Unknown"),
                            doc_type=s.get("doc_type", "general"),
                            score=s.get("score", 0.0),
                            snippet=s.get("snippet", ""),
                        )
                    )
                else:
                    source_citations.append(s)
        msg = ChatMessage(
            role=ConversationRole.ASSISTANT, content=content, sources=source_citations
        )
        self.add_message(msg)

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "messages": [m.to_dict() for m in self.messages],
            "entities": {k: asdict(v) for k, v in self.entities.items()},
            "max_history": self.max_history,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ChatSession":
        session = cls(
            session_id=data.get("session_id", str(uuid.uuid4())[:8]),
            max_history=data.get("max_history", 20),
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            metadata=data.get("metadata", {}),
        )
        for msg_data in data.get("messages", []):
            sources = [SourceCitation(**s) for s in msg_data.get("sources", [])]
            msg = ChatMessage(
                role=ConversationRole(msg_data["role"]),
                content=msg_data["content"],
                sources=sources,
                metadata=msg_data.get("metadata", {}),
                message_id=msg_data.get("message_id", str(uuid.uuid4())[:8]),
                timestamp=msg_data.get("timestamp", datetime.now().isoformat()),
            )
            session.messages.append(msg)
        for eid, edata in data.get("entities", {}).items():
            session.entities[eid] = Entity(**edata)
        return session


class IntentClassifier:
    """Simple intent classification for follow-up handling."""

    INTENTS = {
        "follow_up": ["更多", "详细", "展开", "继续", "再问", "进一步", "深入"],
        "clarification": ["什么意思", "不理解", "解释", "澄清", "是什么"],
        "comparison": ["对比", "区别", "差异", "比较", "优劣"],
        "example": ["例子", "示例", "案例", "实例", "怎么用"],
        "summary": ["总结", "概括", "简述", "摘要"],
        "new_topic": [],  # Default
    }

    @classmethod
    def classify(cls, question: str, previous_question: str = "") -> str:
        question_lower = question.lower()
        for intent, keywords in cls.INTENTS.items():
            if any(kw in question_lower for kw in keywords):
                return intent
        # Check if it references previous context
        if previous_question and any(
            w in question_lower for w in ["它", "这", "那个", "上面", "刚才"]
        ):
            return "follow_up"
        return "new_topic"


class EnhancedChatInterface:
    """
    Enhanced conversational Q&A interface with:
    - Multi-turn dialogue support
    - Entity tracking and context awareness
    - Hybrid search (BM25 + Vector + RRF)
    - LLM-powered answer generation with citations
    - Follow-up question handling
    - Session persistence
    """

    def __init__(
        self,
        search_engine: HybridSearchEngine | VectorSearchEngine,
        llm_client: LLMClient | None = None,
        top_k: int = 5,
        use_llm: bool = True,
        system_prompt: str | None = None,
    ):
        """
        Initialize enhanced chat interface.

        Args:
            search_engine: HybridSearchEngine or VectorSearchEngine for retrieval.
            llm_client: LLMClient for answer generation (optional).
            top_k: Number of documents to retrieve per query.
            use_llm: Whether to use LLM for answer synthesis.
            system_prompt: Custom system prompt for LLM.
        """
        self.search_engine = search_engine
        self.llm_client = llm_client
        self.top_k = top_k
        self.use_llm = use_llm and llm_client is not None
        self.session = ChatSession()
        self.system_prompt = system_prompt or self._default_system_prompt()
        self._pending_clarification: str | None = None

    def _default_system_prompt(self) -> str:
        return """你是 AI Developer Growth 知识库的智能助手。
你的任务是基于检索到的文档，准确、有用地回答用户问题。

核心原则：
1. 只基于提供的文档回答，不要编造信息
2. 每个关键结论必须引用来源文档
3. 如果文档不足以回答，诚实说明并建议用户查阅原文
4. 保持专业、简洁、结构化的回答风格
5. 对于后续追问，结合上下文理解用户意图

回答格式：
- 直接回答问题
- 关键点列表（如适用）
- 引用来源：[文档标题](链接) - 文档类型 (相关度: X.XXX)
- 如有歧义，主动询问澄清"""

    def ask(self, question: str, stream: bool = False) -> dict:
        """
        Ask a question and get an answer with sources.

        Args:
            question: User's question.
            stream: Whether to stream the response (for future streaming support).

        Returns:
            Dict with 'answer', 'sources', 'confidence', 'follow_up_suggestions', 'metadata'.
        """
        # Handle pending clarification
        if self._pending_clarification:
            question = f"{self._pending_clarification} {question}"
            self._pending_clarification = None

        # Classify intent
        previous_q = ""
        user_messages = [
            m for m in self.session.messages if m.role == ConversationRole.USER
        ]
        if user_messages:
            previous_q = user_messages[-1].content
        intent = IntentClassifier.classify(question, previous_q)

        # Add user message
        user_msg = ChatMessage(role=ConversationRole.USER, content=question)
        self.session.add_message(user_msg)

        # Retrieve relevant documents
        if isinstance(self.search_engine, HybridSearchEngine):
            results = self.search_engine.search(
                question, top_k=self.top_k, mode="hybrid"
            )
        else:
            # Fallback to vector search
            vector_results = self.search_engine.search(question, top_k=self.top_k)
            results = [
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
                for r in vector_results
            ]

        if not results:
            answer = (
                "抱歉，知识库中没有找到相关信息。请尝试换个问法，或提供更多上下文。"
            )
            self.session.add_message(
                ChatMessage(role=ConversationRole.ASSISTANT, content=answer)
            )
            return self._build_response(
                answer, [], 0.0, intent, needs_clarification=True
            )

        # Build sources
        sources = [
            SourceCitation(
                doc_id=r.doc_id,
                title=r.title,
                doc_type=r.doc_type,
                score=r.combined_score,
                snippet=r.snippet[:300],
                search_method=r.search_method,
            )
            for r in results
        ]

        # Generate answer
        if self.use_llm:
            answer, confidence = self._generate_llm_answer(question, results, intent)
        else:
            answer, confidence = self._generate_template_answer(question, results)

        # Add assistant message
        assistant_msg = ChatMessage(
            role=ConversationRole.ASSISTANT,
            content=answer,
            sources=sources,
            metadata={"intent": intent, "confidence": confidence},
        )
        self.session.add_message(assistant_msg)

        # Generate follow-up suggestions
        follow_ups = self._generate_follow_ups(question, results, intent)

        return self._build_response(answer, sources, confidence, intent, follow_ups)

    def _generate_llm_answer(
        self, question: str, results: list[HybridSearchResult], intent: str
    ) -> tuple[str, float]:
        """Generate answer using LLM with retrieved context."""
        # Build context from search results
        context_parts = []
        for i, r in enumerate(results, 1):
            context_parts.append(
                f"[文档 {i}] {r.title} ({r.doc_type}) - 相关度: {r.combined_score:.3f}\n"
                f"内容片段: {r.snippet[:500]}"
            )
        context = "\n\n---\n\n".join(context_parts)

        # Build conversation context
        conv_context = self.session.get_full_context()

        # Build prompt
        if intent == "follow_up":
            prompt = (
                f"用户正在针对上一个问题追问。\n\n"
                f"上一轮对话:\n{conv_context}\n\n"
                f"当前问题: {question}\n\n"
                f"相关文档:\n{context}\n\n"
                f"请结合上下文回答，保持回答连贯性。"
            )
        elif intent == "clarification":
            prompt = (
                f"用户请求澄清之前的回答。\n\n"
                f"上一轮对话:\n{conv_context}\n\n"
                f"当前问题: {question}\n\n"
                f"相关文档:\n{context}\n\n"
                f"请提供更详细、通俗易懂的解释。"
            )
        else:
            prompt = (
                f"用户问题: {question}\n\n"
                f"相关文档:\n{context}\n\n"
                f"请基于文档回答，必须引用来源。"
            )

        try:
            response = self.llm_client.generate(prompt, self.system_prompt)
            if not response:
                raise ValueError("Empty LLM response")
            # Calculate confidence based on top result score
            confidence = results[0].combined_score if results else 0.0
            return response, confidence
        except Exception as e:
            logger.error(f"LLM generation failed: {e}")
            # Fallback to template
            return self._generate_template_answer(question, results)

    def _generate_template_answer(
        self, question: str, results: list[HybridSearchResult]
    ) -> tuple[str, float]:
        """Generate answer using template (no LLM)."""
        if not results:
            return "没有找到相关文档。", 0.0

        avg_score = sum(r.combined_score for r in results) / len(results)

        parts = [f"根据知识库，找到 {len(results)} 个相关文档：\n"]

        for i, r in enumerate(results, 1):
            parts.append(
                f"**{i}. {r.title}** ({r.doc_type}) - 相关度: {r.combined_score:.3f}"
            )
            snippet = r.snippet.strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            parts.append(f"   {snippet}\n")

        # Confidence text
        if avg_score > 0.7:
            conf_text = "高度相关"
        elif avg_score > 0.4:
            conf_text = "中度相关"
        else:
            conf_text = "可能相关"

        parts.append(f"---\n*置信度: {conf_text} (平均得分: {avg_score:.3f})*")
        parts.append("\n**引用来源:**")
        for s in [
            SourceCitation(
                doc_id=r.doc_id,
                title=r.title,
                doc_type=r.doc_type,
                score=r.combined_score,
                snippet=r.snippet[:200],
                search_method=r.search_method,
            )
            for r in results
        ]:
            parts.append(f"- {s.format_markdown()}")

        return "\n".join(parts), avg_score

    def _generate_follow_ups(
        self, question: str, results: list[HybridSearchResult], intent: str
    ) -> list[str]:
        """Generate follow-up question suggestions."""
        suggestions = []

        # Based on retrieved documents
        doc_types = set(r.doc_type for r in results)
        if "methodology" in doc_types:
            suggestions.append("如何在实际项目中应用这个方法论？")
        if "case-study" in doc_types:
            suggestions.append("有类似的实战案例吗？")
        if "tool" in doc_types or "tools" in doc_types:
            suggestions.append("这个工具怎么安装和配置？")

        # Based on intent
        if intent == "new_topic":
            suggestions.extend(
                [
                    "能详细解释一下核心概念吗？",
                    "有实操的最佳实践吗？",
                    "常见坑点有哪些？",
                ]
            )
        elif intent == "follow_up":
            suggestions.extend(["能举个具体例子吗？", "这个方案的优缺点对比？"])

        # Limit to 3
        return suggestions[:3]

    def _build_response(
        self,
        answer: str,
        sources: list[SourceCitation],
        confidence: float,
        intent: str,
        follow_ups: list[str] | None = None,
        needs_clarification: bool = False,
    ) -> dict:
        """Build standardized response dict."""
        return {
            "answer": answer,
            "sources": [s.to_dict() for s in sources],
            "confidence": round(confidence, 3),
            "intent": intent,
            "follow_up_suggestions": follow_ups or [],
            "needs_clarification": needs_clarification,
            "session_id": self.session.session_id,
            "message_count": len(self.session.messages),
            "timestamp": datetime.now().isoformat(),
        }

    def ask_with_clarification(self, question: str, clarification: str) -> dict:
        """Handle clarification follow-up."""
        self._pending_clarification = clarification
        return self.ask(question)

    def get_history(self) -> list[dict]:
        """Get full chat history."""
        return [msg.to_dict() for msg in self.session.messages]

    def get_entities(self) -> list[dict]:
        """Get tracked entities."""
        return [
            {
                "name": e.name,
                "type": e.type,
                "mentions": len(e.references),
                "metadata": e.metadata,
            }
            for e in self.session.entities.values()
        ]

    def export_session(self, path: str | Path) -> None:
        """Export session to JSON file."""
        path = Path(path)
        path.write_text(
            json.dumps(self.session.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        logger.info(f"Exported session to {path}")

    def import_session(self, path: str | Path) -> None:
        """Import session from JSON file."""
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        self.session = ChatSession.from_dict(data)
        logger.info(f"Imported session from {path}")

    def clear(self) -> None:
        """Clear session history."""
        self.session.clear()

    def run_cli(self) -> None:
        """Run interactive CLI mode."""
        print("=" * 60)
        print("  AI Developer Growth - 智能问答助手")
        print("  输入 'exit' 退出，'clear' 清空历史，'help' 查看帮助")
        print("=" * 60)

        while True:
            try:
                question = input("\n🤔 你: ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n\n再见！")
                break

            if not question:
                continue

            if question.lower() in ("exit", "quit", "q"):
                print("再见！")
                break
            elif question.lower() in ("clear", "cls"):
                self.clear()
                print("✅ 历史记录已清空")
                continue
            elif question.lower() in ("help", "h"):
                self._print_help()
                continue
            elif question.lower() in ("history", "hist"):
                self._print_history()
                continue
            elif question.lower() in ("entities", "ents"):
                self._print_entities()
                continue
            elif question.lower().startswith("save "):
                path = question[5:].strip() or "chat_session.json"
                self.export_session(path)
                print(f"✅ 会话已保存到 {path}")
                continue
            elif question.lower().startswith("load "):
                path = question[5:].strip()
                try:
                    self.import_session(path)
                    print(f"✅ 会话已从 {path} 加载")
                except Exception as e:
                    print(f"❌ 加载失败: {e}")
                continue

            # Process question
            print("\n🤖 助手: ", end="", flush=True)
            response = self.ask(question)
            print(response["answer"])

            # Show sources
            if response["sources"]:
                print("\n📚 引用来源:")
                for i, src in enumerate(response["sources"], 1):
                    print(
                        f"  {i}. {src['title']} ({src['doc_type']}) - 相关度: {src['score']:.3f}"
                    )

            # Show follow-ups
            if response["follow_up_suggestions"]:
                print("\n💡 建议追问:")
                for s in response["follow_up_suggestions"]:
                    print(f"  - {s}")

    def _print_help(self) -> None:
        print("""
可用命令:
  exit/quit/q     - 退出程序
  clear/cls       - 清空对话历史
  help/h          - 显示帮助
  history/hist    - 显示对话历史
  entities/ents   - 显示识别的实体
  save [文件名]   - 保存会话 (默认 chat_session.json)
  load <文件名>   - 加载会话

提示:
- 支持多轮对话，自动理解上下文
- 可以追问"详细一点"、"举个例子"、"对比一下"
- 回答会自动引用知识库文档来源
""")

    def _print_history(self) -> None:
        if not self.session.messages:
            print("暂无对话历史")
            return
        print(f"\n对话历史 (共 {len(self.session.messages)} 条):")
        for i, msg in enumerate(self.session.messages, 1):
            role_icon = "🤔" if msg.role == ConversationRole.USER else "🤖"
            preview = msg.content[:80] + "..." if len(msg.content) > 80 else msg.content
            print(f"  {i}. {role_icon} {preview}")

    def _print_entities(self) -> None:
        entities = self.get_entities()
        if not entities:
            print("暂无识别实体")
            return
        print(f"\n识别的实体 (共 {len(entities)} 个):")
        for e in entities:
            print(f"  - {e['name']} ({e['type']}) - 提及 {e['mentions']} 次")


# Convenience function for quick usage
def create_chat_interface(
    documents: list[dict],
    llm_provider: str = "system",
    llm_model: str = "gpt-4o",
    top_k: int = 5,
) -> EnhancedChatInterface:
    """
    Quick factory to create chat interface with documents.

    Args:
        documents: List of dicts with keys: id, title, content, doc_type, tags, category
        llm_provider: LLM provider name
        llm_model: LLM model name
        top_k: Top-k retrieval

    Returns:
        Configured EnhancedChatInterface
    """
    engine = HybridSearchEngine()
    for doc in documents:
        engine.add_document(
            doc_id=doc["id"],
            title=doc["title"],
            content=doc["content"],
            doc_type=doc.get("doc_type", "general"),
            tags=doc.get("tags", []),
            category=doc.get("category", ""),
        )

    llm_client = None
    if llm_provider != "none":
        try:
            llm_client = LLMClient(provider=llm_provider, model=llm_model)
        except Exception as e:
            logger.warning(f"Failed to init LLM client: {e}")

    return EnhancedChatInterface(
        search_engine=engine,
        llm_client=llm_client,
        top_k=top_k,
        use_llm=llm_client is not None,
    )


if __name__ == "__main__":
    # Demo with sample documents
    sample_docs = [
        {
            "id": "doc1",
            "title": "AI 开发全生命周期标准",
            "content": "AI 开发全生命周期包含 7 个阶段：需求分析、架构设计、编码实现、测试验证、部署发布、监控运维、持续迭代。每个阶段都有质量门禁...",
            "doc_type": "standard",
            "tags": ["AI-SDLC", "质量门禁"],
            "category": "治理层",
        },
        {
            "id": "doc2",
            "title": "Prompt 工程最佳实践",
            "content": "优秀的 Prompt 应包含：角色定义、任务描述、上下文信息、输出格式、约束条件、示例演示。使用结构化模板可提升输出质量 3-5 倍...",
            "doc_type": "methodology",
            "tags": ["Prompt", "提示工程"],
            "category": "学习层",
        },
        {
            "id": "doc3",
            "title": "向量搜索与 RAG 实战",
            "content": "向量搜索使用 sentence-transformers 生成嵌入，通过余弦相似度检索。混合搜索结合 BM25 关键词匹配与语义搜索，使用 RRF 融合排序...",
            "doc_type": "case-study",
            "tags": ["RAG", "向量搜索", "混合检索"],
            "category": "效率层",
        },
    ]

    chat = create_chat_interface(sample_docs, llm_provider="none")
    chat.run_cli()


class ChatInterface:
    """
    Backward-compatible wrapper for the old ChatInterface API.
    This maintains the same interface as the original implementation.
    """

    def __init__(self, engine):
        """
        Initialize with a VectorSearchEngine or HybridSearchEngine.
        """
        self.engine = engine
        # Create enhanced interface with no LLM (template mode)
        if hasattr(engine, "search") and "mode" in engine.search.__code__.co_varnames:
            # HybridSearchEngine
            self._enhanced = EnhancedChatInterface(
                search_engine=engine, llm_client=None, use_llm=False
            )
        else:
            # VectorSearchEngine
            self._enhanced = EnhancedChatInterface(
                search_engine=engine, llm_client=None, use_llm=False
            )
        self.session = self._enhanced.session

    def ask(self, question: str) -> dict:
        """Ask a question and return response dict (old format)."""
        response = self._enhanced.ask(question)
        # Convert to old format
        return {
            "answer": response["answer"],
            "sources": response["sources"],
            "confidence": response["confidence"],
        }

    def add_user_message(self, content: str) -> None:
        """Add a user message to history."""
        self.session.add_message(
            ChatMessage(role=ConversationRole.USER, content=content)
        )

    def add_assistant_message(self, content: str, sources: list = None) -> None:
        """Add an assistant message to history."""
        source_citations = []
        if sources:
            for s in sources:
                if isinstance(s, dict):
                    source_citations.append(SourceCitation(**s))
                else:
                    source_citations.append(s)
        self.session.add_message(
            ChatMessage(
                role=ConversationRole.ASSISTANT,
                content=content,
                sources=source_citations,
            )
        )

    def get_context(self) -> str:
        """Get formatted conversation context."""
        return self.session.get_full_context()

    def get_history(self) -> list:
        """Get full chat history."""
        return self._enhanced.get_history()

    def clear(self) -> None:
        """Clear session history."""
        self._enhanced.clear()

    def export_history(self, path) -> None:
        """Export history to JSON file."""
        self._enhanced.export_session(path)

    def _generate_answer(self, question: str, results: list) -> tuple:
        """Generate answer from results (for testing)."""
        # Use template answer generation - handle both VectorSearchResult and HybridSearchResult
        if not results:
            return "没有找到相关文档。", 0.0

        # Get score attribute (combined_score for HybridSearchResult, score for VectorSearchResult)
        def get_score(r):
            return getattr(r, "combined_score", getattr(r, "score", 0.0))

        avg_score = sum(get_score(r) for r in results) / len(results)

        parts = [f"根据知识库，找到 {len(results)} 个相关文档：\n"]

        for i, r in enumerate(results, 1):
            score = get_score(r)
            parts.append(f"**{i}. {r.title}** ({r.doc_type}) - 相关度: {score:.3f}")
            snippet = r.snippet.strip()
            if len(snippet) > 300:
                snippet = snippet[:300] + "..."
            parts.append(f"   {snippet}\n")

        # Confidence text
        if avg_score > 0.7:
            conf_text = "高度相关"
        elif avg_score > 0.4:
            conf_text = "中度相关"
        else:
            conf_text = "可能相关"

        parts.append(f"---\n*置信度: {conf_text} (平均得分: {avg_score:.3f})*")
        parts.append("\n**引用来源:**")
        for r in results:
            score = get_score(r)
            s = SourceCitation(
                doc_id=r.doc_id,
                title=r.title,
                doc_type=r.doc_type,
                score=score,
                snippet=r.snippet[:200],
                search_method=getattr(r, "search_method", "vector"),
            )
            parts.append(f"- {s.format_markdown()}")

        return "\n".join(parts), avg_score

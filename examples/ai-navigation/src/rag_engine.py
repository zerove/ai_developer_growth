"""
AI Navigation - RAG Query Engine

Retrieval-Augmented Generation engine for answering questions
using the knowledge base.
"""

from dataclasses import dataclass, field

from .knowledge_index import KnowledgeIndex


@dataclass
class QueryContext:
    """Context for a RAG query."""

    question: str
    user_role: str | None = None
    experience_level: str | None = None
    tools_used: list[str] = field(default_factory=list)
    goals: list[str] = field(default_factory=list)


@dataclass
class Citation:
    """A citation to a source document."""

    doc_id: str
    title: str
    relevance: float
    snippet: str
    doc_type: str


@dataclass
class QueryResult:
    """Result from a RAG query."""

    answer: str
    citations: list[Citation]
    follow_up_questions: list[str]
    confidence: float


class RAGEngine:
    """RAG Query Engine for knowledge navigation."""

    def __init__(self, index: KnowledgeIndex):
        self.index = index
        self._setup_prompts()

    def _setup_prompts(self) -> None:
        """Setup prompt templates."""
        self.system_prompt = """你是一个 AI 开发者成长导师。
基于提供的知识库内容回答问题。
回答时请:
1. 引用具体文档或案例
2. 给出可操作的建议
3. 提供后续学习方向"""

        self.answer_template = """基于知识库中的相关信息，以下是我的回答:

{answer}

**参考来源:**
{citations}

**相关问题:**
{follow_up}"""

    def query(self, context: QueryContext) -> QueryResult:
        """
        Process a query using RAG.

        1. Retrieve relevant documents
        2. Build context
        3. Generate answer
        """
        # Step 1: Retrieve
        results = self.index.search(context.question, top_k=5)

        if not results:
            return QueryResult(
                answer="抱歉，知识库中没有找到相关信息。请尝试换个问法。",
                citations=[],
                follow_up_questions=["如何开始学习 AI 辅助开发?"],
                confidence=0.0,
            )

        # Step 2: Build context and generate answer
        citations = []
        context_parts = []

        for r in results:
            doc = r["doc"]
            citations.append(
                Citation(
                    doc_id=doc.id,
                    title=doc.title,
                    relevance=min(r["score"] / 10.0, 1.0),
                    snippet=r["snippet"],
                    doc_type=doc.type,
                )
            )
            context_parts.append(f"【{doc.title}】\n{r['snippet']}")

        # Step 3: Generate answer (simplified - in production use LLM)
        answer = self._generate_answer(context, context_parts, citations)
        follow_up = self._generate_follow_up(context, results)

        avg_relevance = (
            sum(c.relevance for c in citations) / len(citations) if citations else 0
        )

        return QueryResult(
            answer=answer,
            citations=citations,
            follow_up_questions=follow_up,
            confidence=avg_relevance,
        )

    def _generate_answer(
        self, context: QueryContext, context_parts: list[str], citations: list[Citation]
    ) -> str:
        """Generate an answer based on context."""
        # In production, this would call an LLM
        # For now, we construct a template-based answer

        combined_context = "\n\n".join(context_parts[:3])

        # Build answer based on query type
        if any(kw in context.question.lower() for kw in ["如何", "怎么", "怎样"]):
            answer = f"根据知识库中的相关内容:\n\n{combined_context}\n\n"
            answer += "建议按照以下步骤进行:\n"
            answer += "1. 先阅读相关方法论文档\n"
            answer += "2. 参考类似案例的实践经验\n"
            answer += "3. 在实际项目中尝试应用"
        elif any(kw in context.question.lower() for kw in ["什么是", "概念", "定义"]):
            answer = f"根据知识库定义:\n\n{combined_context}"
        else:
            answer = f"基于知识库中的信息:\n\n{combined_context}"

        return answer

    def _generate_follow_up(
        self, context: QueryContext, results: list[dict]
    ) -> list[str]:
        """Generate follow-up questions."""
        follow_up = []

        # Based on document types found
        doc_types = {r["doc"].type for r in results}

        if "case_study" in doc_types:
            follow_up.append("有哪些类似的成功案例?")
        if "methodology" in doc_types:
            follow_up.append("具体实施步骤是什么?")
        if "adr" in doc_types:
            follow_up.append("这个决策的技术背景是什么?")

        # Add generic follow-ups
        follow_up.extend(["有哪些常见的坑需要避免?", "推荐的学习路径是什么?"])

        return follow_up[:3]


class ConversationManager:
    """Manages multi-turn conversations."""

    def __init__(self, engine: RAGEngine):
        self.engine = engine
        self.history: list[dict] = []

    def chat(self, question: str, user_context: dict | None = None) -> QueryResult:
        """Process a chat message."""
        context = QueryContext(
            question=question,
            user_role=user_context.get("role") if user_context else None,
            experience_level=user_context.get("experience") if user_context else None,
            tools_used=user_context.get("tools", []) if user_context else [],
            goals=user_context.get("goals", []) if user_context else [],
        )

        result = self.engine.query(context)

        # Save to history
        self.history.append(
            {
                "question": question,
                "answer": result.answer,
                "citations": [c.doc_id for c in result.citations],
            }
        )

        return result

    def get_history(self) -> list[dict]:
        """Get conversation history."""
        return self.history

    def clear_history(self) -> None:
        """Clear conversation history."""
        self.history = []


def create_engine(repo_root: str) -> RAGEngine:
    """Create a RAG engine from repo root."""
    from .knowledge_index import IndexBuilder

    builder = IndexBuilder(repo_root)
    index = builder.build()
    return RAGEngine(index)


if __name__ == "__main__":
    import sys

    repo_root = sys.argv[1] if len(sys.argv) > 1 else "."
    engine = create_engine(repo_root)

    print("AI Navigation Engine ready. Type 'quit' to exit.")
    print("-" * 50)

    while True:
        question = input("\n问题: ").strip()
        if question.lower() in ("quit", "exit", "q"):
            break

        if not question:
            continue

        result = engine.query(QueryContext(question=question))

        print(f"\n回答:\n{result.answer}")
        print(f"\n置信度: {result.confidence:.2f}")
        print("\n参考来源:")
        for c in result.citations:
            print(f"  - [{c.doc_type}] {c.title} (相关度: {c.relevance:.2f})")
        print("\n相关问题:")
        for q in result.follow_up_questions:
            print(f"  - {q}")

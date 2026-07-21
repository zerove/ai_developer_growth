#!/usr/bin/env python3
"""
AI Navigation - Main Entry Point

Demonstrates the AI Navigation system with:
1. Building knowledge index
2. Querying with RAG
3. Generating personalized learning paths
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge_index import IndexBuilder, build_index
from src.path_recommender import PathRecommender, UserProfile
from src.rag_engine import ConversationManager, QueryContext, RAGEngine


def demo_index_building(repo_root: str) -> None:
    """Demo: Build knowledge index."""
    print("=" * 60)
    print("📚 Step 1: Building Knowledge Index")
    print("=" * 60)

    index = build_index(repo_root, "knowledge_index.json")

    # Show stats
    methodology = sum(1 for d in index.documents if d.type == "methodology")
    cases = sum(1 for d in index.documents if d.type == "case_study")
    adrs = sum(1 for d in index.documents if d.type == "adr")

    print("\n索引统计:")
    print(f"  - 方法论文档: {methodology}")
    print(f"  - 案例研究: {cases}")
    print(f"  - 架构决策: {adrs}")
    print(f"  - 总计: {len(index.documents)}")


def demo_rag_query(repo_root: str) -> None:
    """Demo: RAG-based querying."""
    print("\n" + "=" * 60)
    print("🔍 Step 2: RAG Query Demo")
    print("=" * 60)

    # Build index
    builder = IndexBuilder(repo_root)
    index = builder.build()

    # Create RAG engine
    engine = RAGEngine(index)

    # Example queries
    queries = [
        "如何用 Cursor 重构遗留代码?",
        "什么是 RAG? 怎么用?",
        "AI 测试策略有哪些?",
    ]

    for query in queries:
        print(f"\n问题: {query}")
        print("-" * 40)

        result = engine.query(QueryContext(question=query))

        print(f"回答:\n{result.answer[:200]}...")
        print(f"\n置信度: {result.confidence:.2f}")
        print("参考来源:")
        for c in result.citations[:2]:
            print(f"  - [{c.doc_type}] {c.title} ({c.relevance:.2f})")


def demo_personalized_paths(repo_root: str) -> None:
    """Demo: Personalized learning paths."""
    print("\n" + "=" * 60)
    print("🎯 Step 3: Personalized Learning Paths")
    print("=" * 60)

    # Build index
    builder = IndexBuilder(repo_root)
    index = builder.build()

    # Create recommender
    recommender = PathRecommender(index)

    # Example user profiles
    users = [
        UserProfile(
            role="前端工程师",
            experience="2年",
            current_tools=["Cursor", "Copilot"],
            goals=["提升效率", "学习 RAG"],
        ),
        UserProfile(
            role="后端工程师",
            experience="5年",
            current_tools=["Claude"],
            goals=["代码质量", "架构设计"],
        ),
    ]

    for user in users:
        print(f"\n用户: {user.role} ({user.experience})")
        print(f"工具: {', '.join(user.current_tools)}")
        print(f"目标: {', '.join(user.goals)}")
        print("-" * 40)

        paths = recommender.recommend(user)

        for path in paths:
            print(f"\n📚 {path.name}")
            print(f"   难度: {path.difficulty} | 时间: {path.total_time}")
            for step in path.steps[:3]:
                print(f"   {step.step_number}. {step.title}")


def interactive_mode(repo_root: str) -> None:
    """Interactive RAG query mode."""
    print("\n" + "=" * 60)
    print("🤖 Interactive Mode")
    print("=" * 60)

    builder = IndexBuilder(repo_root)
    index = builder.build()

    engine = RAGEngine(index)
    conv = ConversationManager(engine)

    print("\n输入问题进行查询 (输入 'quit' 退出):\n")

    while True:
        try:
            question = input("问题: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if question.lower() in ("quit", "exit", "q"):
            break

        if not question:
            continue

        result = conv.chat(question)

        print(f"\n回答:\n{result.answer}")
        print(f"\n置信度: {result.confidence:.2f}")
        print("\n参考来源:")
        for c in result.citations[:3]:
            print(f"  - [{c.doc_type}] {c.title}")
        print("\n相关问题:")
        for q in result.follow_up_questions:
            print(f"  - {q}")
        print()


def main():
    """Main entry point."""
    # Get repo root
    script_dir = Path(__file__).parent
    repo_root = str(script_dir.parent.parent.parent)

    if len(sys.argv) > 1:
        mode = sys.argv[1]
    else:
        mode = "demo"

    if mode == "index":
        demo_index_building(repo_root)
    elif mode == "query":
        demo_rag_query(repo_root)
    elif mode == "paths":
        demo_personalized_paths(repo_root)
    elif mode == "interactive":
        interactive_mode(repo_root)
    elif mode == "demo":
        demo_index_building(repo_root)
        demo_rag_query(repo_root)
        demo_personalized_paths(repo_root)
    else:
        print(f"Unknown mode: {mode}")
        print("Usage: python main.py [demo|index|query|paths|interactive]")
        sys.exit(1)


if __name__ == "__main__":
    main()

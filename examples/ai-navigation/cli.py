#!/usr/bin/env python3
"""
AI Navigation - CLI Interface

Production-ready CLI for the AI Navigation system.
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.knowledge_index import build_index
from src.path_recommender import PathRecommender, UserProfile
from src.rag_engine import ConversationManager, QueryContext, RAGEngine


def cmd_build(args):
    """Build knowledge index."""
    repo_root = args.repo_root or "."
    output = args.output or "knowledge_index.json"

    print(f"📚 Building knowledge index from: {repo_root}")
    index = build_index(repo_root, output)

    # Print stats
    methodology = sum(1 for d in index.documents if d.type == "methodology")
    cases = sum(1 for d in index.documents if d.type == "case_study")
    adrs = sum(1 for d in index.documents if d.type == "adr")

    print("\n✅ Index built successfully!")
    print(f"   - Methodology: {methodology}")
    print(f"   - Case Studies: {cases}")
    print(f"   - ADRs: {adrs}")
    print(f"   - Total: {len(index.documents)}")
    print(f"\n📁 Saved to: {output}")


def cmd_query(args):
    """Query the knowledge base."""
    repo_root = args.repo_root or "."
    index_path = args.index or "knowledge_index.json"

    # Load or build index
    if Path(index_path).exists():
        from src.knowledge_index import KnowledgeIndex

        index = KnowledgeIndex.load(index_path)
        print(f"📚 Loaded index: {len(index.documents)} documents")
    else:
        print(f"📚 Building index from: {repo_root}")
        index = build_index(repo_root, index_path)

    # Create engine
    engine = RAGEngine(index)

    if args.interactive:
        # Interactive mode
        print("\n🤖 Interactive Query Mode")
        print("Type 'quit' to exit, 'history' to see conversation history\n")

        conv = ConversationManager(engine)
        user_context = {}
        if args.role:
            user_context["role"] = args.role
        if args.experience:
            user_context["experience"] = args.experience

        while True:
            try:
                question = input("❓ Question: ").strip()
            except (EOFError, KeyboardInterrupt):
                break

            if question.lower() in ("quit", "exit", "q"):
                break
            if question.lower() == "history":
                history = conv.get_history()
                print(f"\n📜 Conversation history: {len(history)} messages")
                continue
            if not question:
                continue

            result = conv.chat(question, user_context)

            print("\n💡 Answer:")
            print(f"{result.answer}")
            print(f"\n📊 Confidence: {result.confidence:.2f}")

            if result.citations:
                print("\n📖 Citations:")
                for c in result.citations[:3]:
                    print(f"   - [{c.doc_type}] {c.title} ({c.relevance:.2f})")

            if result.follow_up_questions:
                print("\n🔜 Follow-up questions:")
                for q in result.follow_up_questions:
                    print(f"   - {q}")
            print()
    else:
        # Single query
        result = engine.query(QueryContext(question=args.question))

        print("\n💡 Answer:")
        print(f"{result.answer}")
        print(f"\n📊 Confidence: {result.confidence:.2f}")

        if result.citations:
            print("\n📖 Citations:")
            for c in result.citations:
                print(f"   - [{c.doc_type}] {c.title} ({c.relevance:.2f})")

        if args.json:
            print("\n📄 JSON Output:")
            print(
                json.dumps(
                    {
                        "answer": result.answer,
                        "confidence": result.confidence,
                        "citations": [
                            {
                                "doc_id": c.doc_id,
                                "title": c.title,
                                "type": c.doc_type,
                                "relevance": c.relevance,
                            }
                            for c in result.citations
                        ],
                        "follow_up": result.follow_up_questions,
                    },
                    indent=2,
                    ensure_ascii=False,
                )
            )


def cmd_recommend(args):
    """Recommend learning paths."""
    repo_root = args.repo_root or "."
    index_path = args.index or "knowledge_index.json"

    # Load or build index
    if Path(index_path).exists():
        from src.knowledge_index import KnowledgeIndex

        index = KnowledgeIndex.load(index_path)
    else:
        index = build_index(repo_root, index_path)

    # Create recommender
    recommender = PathRecommender(index)

    # Create user profile
    user = UserProfile(
        role=args.role or "全栈工程师",
        experience=args.experience or "3年",
        current_tools=args.tools.split(",") if args.tools else [],
        goals=args.goals.split(",") if args.goals else [],
    )

    print("\n👤 User Profile:")
    print(f"   Role: {user.role}")
    print(f"   Experience: {user.experience}")
    print(f"   Tools: {', '.join(user.current_tools) or 'N/A'}")
    print(f"   Goals: {', '.join(user.goals) or 'N/A'}")

    # Get recommendations
    paths = recommender.recommend(user)

    print(f"\n📚 Recommended Learning Paths: {len(paths)}")
    print("=" * 60)

    for i, path in enumerate(paths, 1):
        print(f"\n{i}. {path.name}")
        print(f"   {path.description}")
        print(f"   Difficulty: {path.difficulty} | Time: {path.total_time}")
        print(f"   Prerequisites: {', '.join(path.prerequisites)}")

        if args.verbose:
            print("   Steps:")
            for step in path.steps:
                print(f"      {step.step_number}. [{step.doc_type}] {step.title}")
                print(f"         Reason: {step.reason} | Time: {step.estimated_time}")


def cmd_stats(args):
    """Show knowledge base statistics."""
    repo_root = args.repo_root or "."
    index_path = args.index or "knowledge_index.json"

    # Load or build index
    if Path(index_path).exists():
        from src.knowledge_index import KnowledgeIndex

        index = KnowledgeIndex.load(index_path)
    else:
        index = build_index(repo_root, index_path)

    # Calculate stats
    methodology = sum(1 for d in index.documents if d.type == "methodology")
    cases = sum(1 for d in index.documents if d.type == "case_study")
    adrs = sum(1 for d in index.documents if d.type == "adr")

    # Category breakdown
    categories = {}
    for doc in index.documents:
        cat = doc.category
        categories[cat] = categories.get(cat, 0) + 1

    print("\n📊 Knowledge Base Statistics")
    print("=" * 60)
    print("\nDocument Types:")
    print(f"   - Methodology: {methodology}")
    print(f"   - Case Studies: {cases}")
    print(f"   - ADRs: {adrs}")
    print(f"   - Total: {len(index.documents)}")

    print("\nCategories:")
    for cat, count in sorted(categories.items(), key=lambda x: -x[1]):
        print(f"   - {cat}: {count}")


def main():
    parser = argparse.ArgumentParser(
        description="AI Navigation - Knowledge Navigation System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Build index
  python cli.py build

  # Query (single)
  python cli.py query "如何用 Cursor 重构代码?"

  # Query (interactive)
  python cli.py query --interactive --role 前端工程师

  # Recommend learning paths
  python cli.py recommend --role 后端工程师 --goals "提升效率,学习 RAG"

  # Show stats
  python cli.py stats
        """,
    )

    parser.add_argument("--repo-root", default=".", help="Repository root directory")
    parser.add_argument(
        "--index", default="knowledge_index.json", help="Index file path"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Build command
    subparsers.add_parser("build", help="Build knowledge index")

    # Query command
    query_parser = subparsers.add_parser("query", help="Query knowledge base")
    query_parser.add_argument("question", nargs="?", help="Question to ask")
    query_parser.add_argument(
        "--interactive", "-i", action="store_true", help="Interactive mode"
    )
    query_parser.add_argument("--role", help="User role (e.g., 前端工程师)")
    query_parser.add_argument("--experience", help="Experience level (e.g., 3年)")
    query_parser.add_argument("--json", action="store_true", help="Output as JSON")

    # Recommend command
    rec_parser = subparsers.add_parser("recommend", help="Recommend learning paths")
    rec_parser.add_argument("--role", default="全栈工程师", help="User role")
    rec_parser.add_argument("--experience", default="3年", help="Experience level")
    rec_parser.add_argument("--tools", help="Comma-separated tools used")
    rec_parser.add_argument("--goals", help="Comma-separated learning goals")
    rec_parser.add_argument(
        "--verbose", "-v", action="store_true", help="Show detailed steps"
    )

    # Stats command
    subparsers.add_parser("stats", help="Show knowledge base statistics")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    # Dispatch
    commands = {
        "build": cmd_build,
        "query": cmd_query,
        "recommend": cmd_recommend,
        "stats": cmd_stats,
    }

    commands[args.command](args)


if __name__ == "__main__":
    main()

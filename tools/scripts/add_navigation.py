#!/usr/bin/env python3
"""
Add navigation sections to efficiency docs.

Adds a standard navigation section at the end of each doc
with links to related docs in the same category.
"""
import re
from pathlib import Path

# Category to related docs mapping
CATEGORY_DOCS = {
    "效率层": [
        ("full-cycle-workflow", "全周期工作流"),
        ("automated-bug-fixing", "自动化修复"),
        ("anti-patterns", "反模式"),
        ("context-engineering", "上下文工程"),
        ("token-optimization", "Token 优化"),
        ("multi-agent-patterns", "多 Agent 编排"),
        ("metrics-framework", "度量体系"),
    ],
    "治理层": [
        ("ai-code-generation-quality", "代码质量"),
        ("ai-model-selection", "模型选型"),
        ("ai-sdlc", "SDLC"),
        ("ai-code-review-checklist", "代码审查"),
        ("ai-nondeterministic-testing", "非确定性测试"),
        ("ai-hallucination-mitigation", "幻觉缓解"),
        ("ai-context-window-management", "上下文管理"),
    ],
    "认知层": [
        ("product-thinking", "产品思维"),
        ("solo-founder-loop", "独立开发"),
        ("ai-to-market-checklist", "市场发布"),
        ("team-adoption", "团队采用"),
    ],
    "学习层": [
        ("ai-learning-method", "AI 学习法"),
        ("knowledge-internalization", "知识内化"),
        ("prompt-engineering", "Prompt 工程"),
    ],
}


def get_navigation(doc_path: Path, content: str) -> str:
    """Generate navigation section for a doc."""
    # Extract category from frontmatter
    cat_match = re.search(r"^category:\s*(.+)$", content, re.MULTILINE)
    if not cat_match:
        return ""

    category = cat_match.group(1).strip()
    doc_name = doc_path.stem

    # Get related docs from same category
    related = CATEGORY_DOCS.get(category, [])
    related_links = []
    for slug, title in related:
        if slug != doc_name:
            related_links.append(f"- [[docs/efficiency/{slug}|{title}]]")

    if not related_links:
        return ""

    # Build navigation section
    nav_lines = [
        "\n---\n",
        "## 导航\n",
        f"**分类**: {category}\n",
        "**相关文档**:\n",
    ]
    nav_lines.extend(related_links[:5])  # Limit to 5 related docs
    nav_lines.append("")

    return "\n".join(nav_lines)


def add_navigation_to_doc(doc_path: Path) -> bool:
    """Add navigation section to a doc if missing."""
    content = doc_path.read_text(encoding="utf-8")

    # Skip if navigation already exists
    if "## 导航" in content:
        return False

    nav = get_navigation(doc_path, content)
    if not nav:
        return False

    # Append navigation section
    doc_path.write_text(content + nav, encoding="utf-8")
    return True


def main() -> None:
    """Add navigation to all efficiency docs."""
    docs_dir = Path("docs/efficiency")
    updated = 0

    for doc in sorted(docs_dir.glob("*.md")):
        if add_navigation_to_doc(doc):
            print(f"✅ {doc.name}")
            updated += 1

    print(f"📊 已更新 {updated} 个文档")


if __name__ == "__main__":
    main()

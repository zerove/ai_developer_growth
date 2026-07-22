#!/usr/bin/env python3
"""
jcode Skill Runner - 治理文档验证器

用法:
    python .jcode/scripts/governance-docs-validator.py validate
    python .jcode/scripts/governance-docs-validator.py check-index
    python .jcode/scripts/governance-docs-validator.py sync-refs
    python .jcode/scripts/governance-docs-validator.py full
"""

import re
import sys
from pathlib import Path


GOVERNANCE_DOCS = [
    "docs/efficiency/ai-code-generation-quality.md",
    "docs/efficiency/ai-model-selection.md",
    "docs/efficiency/ai-sdlc.md",
    "docs/efficiency/ai-code-review-checklist.md",
    "docs/efficiency/ai-nondeterministic-testing.md",
    "docs/efficiency/ai-hallucination-mitigation.md",
    "docs/efficiency/ai-code-licensing.md",
    "docs/efficiency/ai-dev-environment.md",
    "docs/efficiency/ai-context-window-management.md",
    "docs/efficiency/ai-performance-benchmarks.md",
    "docs/efficiency/ai-debugging-standards.md",
    "docs/efficiency/ai-version-control.md",
    "docs/efficiency/ai-deployment-operations.md",
    "docs/efficiency/ai-developer-training.md",
    "docs/efficiency/ai-dev-toolchain.md",
]

REQUIRED_FIELDS = ["title", "description", "category", "tags", "difficulty"]


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """提取 YAML frontmatter"""
    if not content.startswith("---"):
        return {}, content

    end_idx = content.find("---", 3)
    if end_idx == -1:
        return {}, content

    fm_str = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()

    frontmatter = {}
    for line in fm_str.split("\n"):
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = value.strip().strip('"').strip("'")

    return frontmatter, body


def validate() -> int:
    """验证治理层文档格式完整性"""
    print("📋 验证治理层文档格式完整性...")
    issues = []

    for doc_path in GOVERNANCE_DOCS:
        path = Path(doc_path)
        if not path.exists():
            issues.append(f"Missing: {doc_path}")
            continue

        content = path.read_text(encoding="utf-8")
        fm, body = extract_frontmatter(content)

        # 检查 frontmatter
        if not fm:
            issues.append(f"{doc_path}: Missing or empty frontmatter")
            continue

        # 检查必需字段
        for field in REQUIRED_FIELDS:
            if field not in fm:
                issues.append(f"{doc_path}: Missing field '{field}'")

        # 检查标题格式
        if "title" in fm:
            title = fm["title"]
            if not title.endswith(")"):
                issues.append(f"{doc_path}: Title missing English suffix in parentheses")

        # 检查分类
        valid_categories = ["认知层", "学习层", "效率层", "工具层", "治理层"]
        if "category" in fm and fm["category"] not in valid_categories:
            issues.append(f"{doc_path}: Invalid category '{fm['category']}'")

        if "## 导航" not in body and "## Navigation" not in body:
            issues.append(f"{doc_path}: Missing navigation section")

        # 检查相关文档
        if "相关文档" not in body and "See Also" not in body:
            issues.append(f"{doc_path}: Missing related docs section")

        # 检查内容长度（至少有3个二级标题）
        h2_count = len(re.findall(r"^## ", body, re.MULTILINE))
        if h2_count < 3:
            issues.append(f"{doc_path}: Only {h2_count} sections (minimum 3 required)")

    if issues:
        print(f"\n❌ 发现 {len(issues)} 个问题:")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print(f"✅ {len(GOVERNANCE_DOCS)} 个治理文档验证通过")
        return 0


def check_index() -> int:
    """验证治理层索引完整性"""
    print("📑 验证治理层索引完整性...")
    issues = []

    # 检查 GOVERNANCE.md
    governance_path = Path("GOVERNANCE.md")
    if governance_path.exists():
        content = governance_path.read_text(encoding="utf-8")
        for doc_path in GOVERNANCE_DOCS:
            doc_name = Path(doc_path).stem
            if doc_name not in content:
                issues.append(f"GOVERNANCE.md: Missing reference to {doc_name}")
    else:
        issues.append("GOVERNANCE.md not found")

    # 检查 INDEX.md
    index_path = Path("INDEX.md")
    if index_path.exists():
        content = index_path.read_text(encoding="utf-8")
        for doc_path in GOVERNANCE_DOCS:
            doc_name = Path(doc_path).stem
            if doc_name not in content:
                issues.append(f"INDEX.md: Missing reference to {doc_name}")
    else:
        issues.append("INDEX.md not found")

    # 检查 CLAUDE.md
    claude_path = Path("CLAUDE.md")
    if claude_path.exists():
        content = claude_path.read_text(encoding="utf-8")
        for doc_path in GOVERNANCE_DOCS:
            doc_name = Path(doc_path).stem
            if doc_name not in content:
                issues.append(f"CLAUDE.md: Missing reference to {doc_name}")
    else:
        issues.append("CLAUDE.md not found")

    if issues:
        print(f"\n❌ 索引验证失败 ({len(issues)} 个问题):")
        for issue in issues:
            print(f"  - {issue}")
        return 1
    else:
        print("✅ 所有索引引用完整")
        return 0


def sync_refs() -> int:
    """同步治理文档引用"""
    print("🔗 同步治理文档引用...")
    fixed = 0

    # 检查每个治理文档的交叉引用
    for doc_path in GOVERNANCE_DOCS:
        path = Path(doc_path)
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")
        modified = False

        # 确保有指向 GOVERNANCE.md 的引用
        if "GOVERNANCE.md" not in content:
            # 在相关文档部分添加
            if "相关文档" in content:
                content = content.replace(
                    "相关文档",
                    "相关文档\n- [[GOVERNANCE|通用治理标准]]"
                )
                modified = True
            elif "See Also" in content:
                content = content.replace(
                    "See Also",
                    "See Also\n- [[GOVERNANCE|通用治理标准]]"
                )
                modified = True

        if modified:
            path.write_text(content, encoding="utf-8")
            fixed += 1
            print(f"  Fixed: {doc_path}")

    print(f"✅ 同步完成，修复了 {fixed} 个文件")
    return 0


def full() -> int:
    """运行完整验证"""
    print("🚀 运行治理文档完整验证...")
    print("=" * 50)

    results = []
    results.append(("文档格式验证", validate()))
    results.append(("索引完整性检查", check_index()))

    print("\n" + "=" * 50)
    failed = [name for name, code in results if code != 0]
    if failed:
        print(f"❌ 以下检查失败: {', '.join(failed)}")
        return 1
    else:
        print("✅ 所有检查通过")
        return 0


def main() -> None:
    if len(sys.argv) < 2:
        print("用法: governance-docs-validator.py <action>")
        print("Actions: validate, check-index, sync-refs, full")
        sys.exit(1)

    action = sys.argv[1]
    actions = {
        "validate": validate,
        "check-index": check_index,
        "sync-refs": sync_refs,
        "full": full,
    }

    if action in actions:
        sys.exit(actions[action]())
    else:
        print(f"未知 action: {action}")
        print("可用 actions: " + ", ".join(actions.keys()))
        sys.exit(1)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""批量补全文档元数据"""

import os
import re
from pathlib import Path

# 目录到分类的映射
DIR_CATEGORY_MAP = {
    "docs/mindset": ("心态层", ["AI思维", "工程师文化"]),
    "docs/learning": ("学习层", ["技术学习", "能力提升"]),
    "docs/efficiency": ("效率层", ["AI效率", "开发效率"]),
    "docs/tools": ("工具层", ["开发工具", "AI工具"]),
    "docs/governance": ("治理层", ["代码规范", "团队协作"]),
    "docs/frameworks": ("工具层", ["框架", "技术栈"]),
    "docs/database": ("工具层", ["数据库", "数据存储"]),
    "docs/caching": ("工具层", ["缓存", "性能优化"]),
    "docs/devops": ("工具层", ["DevOps", "部署"]),
    "docs/security": ("治理层", ["安全", "DevSecOps"]),
    "docs/testing": ("工具层", ["测试", "质量保证"]),
    "docs/monitoring": ("工具层", ["监控", "可观测性"]),
    "docs/message-queue": ("工具层", ["消息队列", "异步处理"]),
    "docs/integration": ("工具层", ["集成", "API"]),
    "docs/specs": ("治理层", ["规范", "标准"]),
    "docs/specialization": ("学习层", ["专业领域", "深度学习"]),
    "docs/api": ("工具层", ["API设计", "接口规范"]),
    "docs/agent-dev": ("治理层", ["Agent开发", "AI系统"]),
    "docs/adr": ("治理层", ["架构决策", "ADR"]),
    "docs/moc": ("治理层", ["知识图谱", "MOC"]),
}


def get_category_from_path(filepath: str) -> tuple[str, list[str]]:
    """根据文件路径推断分类"""
    path = Path(filepath)

    for dir_path, category in DIR_CATEGORY_MAP.items():
        if dir_path in str(path):
            return category

    return ("效率层", ["AI开发", "技术文档"])


def infer_title_from_content(content: str, filepath: str) -> str:
    """从内容推断标题"""
    # 尝试从第一个标题提取
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()

    # 从文件名推断
    filename = Path(filepath).stem
    return filename.replace("-", " ").replace("_", " ").title()


def infer_difficulty(content: str) -> str:
    """推断难度"""
    content_lower = content.lower()
    if any(word in content_lower for word in ["高级", "深入", "复杂", "advanced", "expert"]):
        return "高级"
    elif any(word in content_lower for word in ["中级", "进阶", "intermediate"]):
        return "中级"
    return "初级"


def infer_tags(content: str, filepath: str) -> list[str]:
    """推断标签"""
    tags = set()

    # 从文件路径提取
    filename = Path(filepath).stem
    if "-" in filename:
        tags.update(filename.split("-")[:3])

    # 从内容提取关键词
    keywords = {
        "python": "Python",
        "javascript": "JavaScript",
        "typescript": "TypeScript",
        "react": "React",
        "vue": "Vue",
        "angular": "Angular",
        "docker": "Docker",
        "kubernetes": "Kubernetes",
        "k8s": "Kubernetes",
        "ai": "AI",
        "llm": "LLM",
        "gpt": "GPT",
        "api": "API",
        "rest": "REST",
        "graphql": "GraphQL",
        "database": "数据库",
        "sql": "SQL",
        "nosql": "NoSQL",
        "test": "测试",
        "testing": "测试",
        "deploy": "部署",
        "ci/cd": "CI/CD",
        "security": "安全",
        "performance": "性能",
    }

    content_lower = content.lower()
    for key, tag in keywords.items():
        if key in content_lower or key in filename.lower():
            tags.add(tag)

    return list(tags)[:5] or ["技术文档"]


def generate_metadata(filepath: str) -> str:
    """生成元数据"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    category, default_tags = get_category_from_path(filepath)
    title = infer_title_from_content(content, filepath)
    difficulty = infer_difficulty(content)
    tags = infer_tags(content, filepath)

    # 生成描述
    desc_match = re.search(r"^#\s+.+\n\n(.+?)(?:\n\n|\n#)", content, re.MULTILINE)
    if desc_match:
        description = desc_match.group(1).strip()[:100]
    else:
        description = f"{title} - 技术文档"

    metadata = f"""---
title: {title}
description: {description}
category: {category}
tags: {tags}
difficulty: {difficulty}
reading_time: 10 分钟
updated: 2026-07-21
---

"""
    return metadata


def process_file(filepath: str) -> bool:
    """处理单个文件"""
    with open(filepath, encoding="utf-8") as f:
        content = f.read()

    # 如果已经有完整的元数据，跳过
    if content.startswith("---"):
        parts = content.split("---", 2)
        if len(parts) >= 3:
            frontmatter = parts[1]
            required_fields = ["title", "description", "category", "tags", "difficulty"]
            if all(field + ":" in frontmatter for field in required_fields):
                return False

    # 如果没有元数据，添加
    if not content.startswith("---"):
        metadata = generate_metadata(filepath)
        new_content = metadata + content
    else:
        # 如果有但不完整，替换
        parts = content.split("---", 2)
        metadata = generate_metadata(filepath)
        new_content = metadata + parts[2] if len(parts) >= 3 else metadata + content

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(new_content)

    return True


def main() -> None:
    docs_dir = "docs"
    fixed_count = 0

    for root, dirs, files in os.walk(docs_dir):
        for f in files:
            if f.endswith(".md"):
                filepath = os.path.join(root, f)
                if process_file(filepath):
                    fixed_count += 1
                    print(f"✓ {filepath}")

    print(f"\n完成! 修复了 {fixed_count} 个文件")


if __name__ == "__main__":
    main()

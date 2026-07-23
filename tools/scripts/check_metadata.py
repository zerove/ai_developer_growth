#!/usr/bin/env python3
"""
检查文档元数据完整性
"""

from pathlib import Path


def extract_frontmatter(content: str) -> tuple[dict, str]:
    """提取 YAML frontmatter"""
    if content.startswith("---"):
        end_idx = content.find("---", 3)
        if end_idx != -1:
            frontmatter_str = content[3:end_idx].strip()
            body = content[end_idx + 3 :].strip()

            # 简单解析 YAML
            frontmatter = {}
            for line in frontmatter_str.split("\n"):
                if ":" in line:
                    key, value = line.split(":", 1)
                    frontmatter[key.strip()] = value.strip()

            return frontmatter, body

    return {}, content


def check_metadata(file_path: Path) -> list[str]:
    """检查单个文件的元数据"""
    issues = []

    try:
        content = file_path.read_text(encoding="utf-8")
        frontmatter, body = extract_frontmatter(content)

        # 检查必填字段
        required_fields = ["title", "description", "category", "tags", "difficulty"]
        for field in required_fields:
            if field not in frontmatter:
                issues.append(f"Missing required field: {field}")

        # 检查分类
        valid_categories = ["认知层", "学习层", "效率层", "工具层", "治理层"]
        if "category" in frontmatter:
            if frontmatter["category"] not in valid_categories:
                issues.append(f"Invalid category: {frontmatter['category']}")

        # 检查难度
        valid_difficulties = ["入门", "基础", "进阶", "高级", "专家"]
        if "difficulty" in frontmatter:
            if frontmatter["difficulty"] not in valid_difficulties:
                issues.append(f"Invalid difficulty: {frontmatter['difficulty']}")

        # 检查描述长度
        if "description" in frontmatter:
            if len(frontmatter["description"]) > 50:
                issues.append(f"Description too long: {len(frontmatter['description'])} chars")

    except Exception as e:
        issues.append(f"Error reading file: {e}")

    return issues


def scan_directory(directory: Path) -> dict[str, list[str]]:
    """扫描目录中的所有 Markdown 文件"""
    results = {}

    for md_file in directory.rglob("*.md"):
        # 跳过某些目录
        if any(skip in str(md_file) for skip in [".git", "node_modules", "__pycache__"]):
            continue

        issues = check_metadata(md_file)
        if issues:
            results[str(md_file)] = issues

    return results


def main() -> None:
    """主函数"""
    # 扫描 docs 目录
    docs_dir = Path("docs")
    if not docs_dir.exists():
        print("Error: docs directory not found")
        return

    print("Scanning docs directory...")
    results = scan_directory(docs_dir)

    # 扫描 case-studies 目录
    case_studies_dir = Path("case-studies")
    if case_studies_dir.exists():
        case_results = scan_directory(case_studies_dir)
        results.update(case_results)

    # 输出结果
    if results:
        print(f"\nFound {len(results)} files with metadata issues:\n")
        for file_path, issues in results.items():
            print(f"📄 {file_path}")
            for issue in issues:
                print(f"   - {issue}")
            print()
    else:
        print("\n✅ All files have valid metadata!")


if __name__ == "__main__":
    main()

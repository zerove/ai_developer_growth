#!/usr/bin/env python3
"""
检查文档元数据完整性
"""

from pathlib import Path


def extract_frontmatter(content: str) -> tuple[dict[str, str], str]:
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


def _check_required_fields(frontmatter: dict[str, str], is_adr: bool) -> list[str]:
    """检查必填字段 (title/description/category/tags/difficulty).

    V2.18 P3-9 拆分: 从 check_metadata (C=13) 抽出.
    ADR 文档使用独立模板, 跳过 5 字段规范.
    """
    if is_adr:
        return []
    required_fields = ["title", "description", "category", "tags", "difficulty"]
    return [f"Missing required field: {f}" for f in required_fields if f not in frontmatter]


def _check_category(frontmatter: dict[str, str], file_path: Path) -> list[str]:
    """检查 category 字段是否在合法值列表.

    V2.18 P3-9 拆分: 从 check_metadata (C=13) 抽出.
    案例研究是独立分类, 单独追加到合法值列表.
    """
    valid_categories = ["认知层", "学习层", "效率层", "工具层", "治理层"]
    if "case-studies" in str(file_path):
        valid_categories.append("案例研究")
    if "category" in frontmatter and frontmatter["category"] not in valid_categories:
        return [f"Invalid category: {frontmatter['category']}"]
    return []


def _check_difficulty(frontmatter: dict[str, str]) -> list[str]:
    """检查 difficulty 字段是否在合法值列表.

    V2.18 P3-9 拆分: 从 check_metadata (C=13) 抽出.
    """
    valid_difficulties = ["入门", "基础", "进阶", "高级", "专家"]
    if "difficulty" in frontmatter and frontmatter["difficulty"] not in valid_difficulties:
        return [f"Invalid difficulty: {frontmatter['difficulty']}"]
    return []


def _check_description_length(frontmatter: dict[str, str]) -> list[str]:
    """检查 description 长度 (≤ 50 字符).

    V2.18 P3-9 拆分: 从 check_metadata (C=13) 抽出.
    """
    if "description" in frontmatter and len(frontmatter["description"]) > 50:
        return [f"Description too long: {len(frontmatter['description'])} chars"]
    return []


def check_metadata(file_path: Path) -> list[str]:
    """检查单个文件的元数据 (orchestrator).

    V2.18 P3-9 拆分: 从 C=13 / 60 行主函数拆出 4 个 field checker helper.
    主函数仅负责: 读文件 → 提取 frontmatter → 委托 4 个 checker → 汇总.
    """
    issues: list[str] = []

    try:
        content = file_path.read_text(encoding="utf-8")
    except Exception as e:
        return [f"Error reading file: {e}"]

    frontmatter, _ = extract_frontmatter(content)
    is_adr = "docs/adr" in str(file_path) and file_path.name != "ADR.md"

    issues.extend(_check_required_fields(frontmatter, is_adr))
    issues.extend(_check_category(frontmatter, file_path))
    issues.extend(_check_difficulty(frontmatter))
    issues.extend(_check_description_length(frontmatter))

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


def _scan_known_dirs() -> dict[str, list[str]]:
    """扫描 docs/ + case-studies/ 目录, 合并结果.

    V2.19 P3-42 拆分: 从 main (B=6) 抽出.
    docs 目录必扫, case-studies 目录可选.
    """
    docs_dir = Path("docs")
    if not docs_dir.exists():
        return {}
    print("Scanning docs directory...")
    results = scan_directory(docs_dir)

    case_studies_dir = Path("case-studies")
    if case_studies_dir.exists():
        case_results = scan_directory(case_studies_dir)
        results.update(case_results)
    return results


def _print_metadata_results(results: dict[str, list[str]]) -> None:
    """打印元数据检查结果 (含空态).

    V2.19 P3-42 拆分: 从 main (B=6) 抽出.
    """
    if results:
        print(f"\nFound {len(results)} files with metadata issues:\n")
        for file_path, issues in results.items():
            print(f"📄 {file_path}")
            for issue in issues:
                print(f"   - {issue}")
            print()
    else:
        print("\n✅ All files have valid metadata!")


def main() -> None:
    """主函数 (orchestrator).

    V2.19 P3-42 拆分: 从 B=6 / 28 行 main 拆出 2 个 helper.
    主函数仅负责: 委托 scan + print.
    """
    if not Path("docs").exists():
        print("Error: docs directory not found")
        return
    results = _scan_known_dirs()
    _print_metadata_results(results)


if __name__ == "__main__":
    main()

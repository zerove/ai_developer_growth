#!/usr/bin/env python3
"""
检查 UBIQUITOUS_LANGUAGE.md 中的术语是否在文档中被使用
"""

import re
import sys
from pathlib import Path


def extract_terms(ubiquitous_file: Path) -> list:
    """从 UBIQUITOUS_LANGUAGE.md 提取术语"""
    terms = []
    content = ubiquitous_file.read_text(encoding="utf-8")
    # 匹配表格行 | 术语 | 英文 | 定义 | ...
    for line in content.split("\n"):
        if line.startswith("| ") and not line.startswith("| 术语") and not line.startswith("|---"):
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                term = parts[1].strip()
                if term and term not in ["英文", "定义", "使用场景", "来源"]:
                    terms.append(term)
    return terms


def check_term_usage(term: str, docs_dir: Path) -> int:
    """检查术语在文档中的使用次数"""
    count = 0
    for md_file in docs_dir.rglob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8")
            # 简单的词边界匹配
            count += len(re.findall(rf"\b{re.escape(term)}\b", content))
        except (UnicodeDecodeError, OSError):
            pass
    return count


def main() -> None:
    ubiquitous_file = Path("UBIQUITOUS_LANGUAGE.md")
    docs_dir = Path("docs")

    if not ubiquitous_file.exists():
        print(f"FAIL: {ubiquitous_file} not found")
        return 1

    terms = extract_terms(ubiquitous_file)
    print(f"Found {len(terms)} terms in UBIQUITOUS_LANGUAGE.md")

    missing = []
    for term in terms:
        count = check_term_usage(term, docs_dir)
        if count == 0:
            missing.append(term)
            print(f"  WARN: '{term}' not used in docs/")
        else:
            print(f"  OK: '{term}' used {count} times")

    if missing:
        print(f"\nWARN: {len(missing)} terms not referenced in docs/")
        return 0  # 警告不阻塞
    else:
        print("\nPASS: All terms referenced in docs/")
        return 0


if __name__ == "__main__":
    sys.exit(main())

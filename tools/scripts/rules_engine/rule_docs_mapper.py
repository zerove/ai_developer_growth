"""
Rule-to-Docs Mapping — 知识库-规则联动模块

为每条规则推荐相关文档（docs/ 目录下的指南、案例、最佳实践）。
在 checker.py 输出中附加 `related_docs` 字段，帮助开发者速查。

用法:
    python rule_docs_mapper.py --rebuild    # 重建映射索引
    python rule_docs_mapper.py --query py-bare-except  # 查询规则的关联文档
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# ─────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
DOCS_DIR = PROJECT_ROOT / "docs"
CASE_STUDIES_DIR = PROJECT_ROOT / "case-studies"
MAPPING_CACHE = PROJECT_ROOT / ".jcode" / "rule-docs-mapping.json"

# 规则 ID → docs 关键词映射
# 自动生成的映射将会补充这些内置映射
BUILTIN_MAPPINGS: dict[str, list[dict[str, str]]] = {
    "py-bare-except": [
        {"path": "docs/learning/python-basics.md", "reason": "Python 异常处理最佳实践"},
        {"path": "docs/mindset/error-handling.md", "reason": "错误处理思维方式"},
    ],
    "py-eval-exec": [
        {"path": "docs/security/secure-coding.md", "reason": "安全编码指南"},
        {"path": "docs/mindset/security-mindset.md", "reason": "安全思维方式"},
    ],
    "py-assert-instead-of-if": [
        {"path": "docs/learning/python-basics.md", "reason": "assert 用法注意事项"},
    ],
    "ts-any-usage": [
        {"path": "docs/learning/typescript-best-practices.md", "reason": "TypeScript 类型安全最佳实践"},
    ],
    "ts-ignore-comment": [
        {"path": "docs/learning/typescript-best-practices.md", "reason": "@ts-ignore 替代方案"},
    ],
    "rs-unsafe-code": [
        {"path": "docs/learning/rust-safety.md", "reason": "Rust 安全编程"},
    ],
    "sql-injection": [
        {"path": "docs/security/secure-coding.md", "reason": "SQL 注入防护"},
    ],
}


def extract_keywords_from_docs(docs_dir: Path) -> dict[str, list[str]]:
    """
    扫描 docs/ 目录，提取每篇文档的关键词。
    关键词来自标题、tags frontmatter、一级/二级标题。
    """
    doc_keywords: dict[str, list[str]] = {}

    for md_file in sorted(docs_dir.rglob("*.md")):
        rel_path = md_file.relative_to(PROJECT_ROOT)
        keywords: list[str] = []
        content = md_file.read_text(encoding="utf-8", errors="ignore")

        # 从 frontmatter 提取 tags
        fm_match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        if fm_match:
            fm_text = fm_match.group(1)
            for line in fm_text.split("\n"):
                if line.strip().startswith("tags:"):
                    tags_part = line[5:].strip()
                    if tags_part.startswith("["):
                        try:
                            tags = json.loads(tags_part)
                            keywords.extend(t if isinstance(t, str) else str(t) for t in tags)
                        except json.JSONDecodeError:
                            pass
                    else:
                        keywords.extend(t.strip().strip('"').strip("'") for t in tags_part.split(",") if t.strip())
                elif ":" in line and not line.strip().startswith("#"):
                    k, v = line.split(":", 1)
                    k = k.strip().lower()
                    if k in ("category", "topic", "domain", "language", "framework"):
                        keywords.append(v.strip().strip('"').strip("'"))

        # 从标题提取
        for h_match in re.finditer(r"^#{1,3}\s+(.+)$", content, re.MULTILINE):
            title = h_match.group(1).strip().lower()
            keywords.append(title)
            # 拆分标题中的关键词
            for word in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", title):
                if len(word) > 3:
                    keywords.append(word.lower())

        # 文件名也是关键词
        stem = md_file.stem.lower()
        keywords.extend(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", stem))

        if keywords:
            doc_keywords[str(rel_path)] = list(set(keywords))

    return doc_keywords


def extract_keywords_from_rule(rule_id: str, rule_data: dict[str, Any]) -> list[str]:
    """从规则中提取关键词，用于匹配文档。"""
    keywords = []

    # 规则 ID: py-bare-except → ["py", "bare", "except", "python"]
    parts = rule_id.replace("-", " ").replace("_", " ").split()
    for p in parts:
        keywords.append(p.lower())
        # 语言映射
        lang_map = {"py": "python", "ts": "typescript", "rs": "rust", "js": "javascript"}
        if p.lower() in lang_map:
            keywords.append(lang_map[p.lower()])

    # 规则字段
    for field in ("name", "message", "category", "fix_hint"):
        val = rule_data.get(field, "")
        if isinstance(val, str):
            for w in re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", val):
                if len(w) > 3:
                    keywords.append(w.lower())
        elif isinstance(val, list):
            for item in val:
                if isinstance(item, str):
                    keywords.extend(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]+", item.lower()))

    return list(set(keywords))


def _load_rules_from_yml(filepath: Path) -> list[dict[str, Any]]:
    """Load anti-pattern rules from a YAML file."""
    if not filepath.exists():
        return []
    try:
        import yaml
        data = yaml.safe_load(filepath.read_text(encoding="utf-8"))
        return data.get("anti_patterns", []) if data else []
    except ImportError:
        # Minimal parser fallback
        return _simple_parse_rules(filepath)
    except Exception:
        return []


def _simple_parse_rules(filepath: Path) -> list[dict[str, Any]]:
    """Minimal YAML parser for anti_patterns.yml (no PyYAML needed)."""
    rules: list[dict[str, Any]] = []
    current: dict[str, Any] | None = None
    for line in filepath.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- id:"):
            if current:
                rules.append(current)
            current = {"id": stripped.split(":", 1)[1].strip()}
            continue
        if current and ":" in stripped and not stripped.startswith("-"):
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip().strip("'\"")
            if key in ("name", "severity", "category", "pattern", "message", "fix_hint"):
                current[key] = val
    if current:
        rules.append(current)
    return rules


def build_mapping(
    rule_dir: Path | None = None,
    docs_dir: Path = DOCS_DIR,
    case_studies: bool = True,
) -> dict[str, list[dict[str, str]]]:
    """
    构建完整的规则→文档映射。
    对每条规则，通过关键词匹配找出最相关的 1-3 篇文档。
    """

    # 1. 扫描文档关键词
    doc_keywords = extract_keywords_from_docs(docs_dir)
    if case_studies and CASE_STUDIES_DIR.exists():
        cs_keywords = extract_keywords_from_docs(CASE_STUDIES_DIR)
        doc_keywords.update(cs_keywords)

    # 2. 加载所有规则（直接解析 YAML）
    all_rules: dict[str, dict[str, Any]] = {}
    rule_path = rule_dir or (PROJECT_ROOT / "ai-dev-framework" / "languages")

    for lang_dir in sorted(rule_path.iterdir()) if rule_path.exists() else []:
        if not lang_dir.is_dir():
            continue
        rules_file = lang_dir / "rules.d" / "anti_patterns.yml"
        if rules_file.exists():
            for rule in _load_rules_from_yml(rules_file):
                rule_id = rule.get("id", "")
                if rule_id:
                    all_rules[rule_id] = rule

    # Also load framework rules
    framework_dir = PROJECT_ROOT / "ai-dev-framework" / "frameworks"
    if framework_dir.exists():
        for fw_dir in sorted(framework_dir.iterdir()):
            rules_file = fw_dir / "rules.d" / "anti_patterns.yml"
            if rules_file.exists():
                for rule in _load_rules_from_yml(rules_file):
                    rule_id = rule.get("id", "")
                    if rule_id:
                        all_rules[rule_id] = rule

    # 3. 匹配：规则关键词 vs 文档关键词
    mapping: dict[str, list[dict[str, str]]] = {}
    for rule_id, rule_data in all_rules.items():
        rule_keywords = set(extract_keywords_from_rule(rule_id, rule_data))
        scored_docs: list[tuple[int, str, str]] = []  # (score, path, reason)

        for doc_path, kw_list in doc_keywords.items():
            doc_kw_set = set(kw_list)
            overlap = rule_keywords & doc_kw_set
            if overlap:
                reason_keywords = list(overlap)[:3]
                scored_docs.append((len(overlap), doc_path, f"关联关键词: {', '.join(reason_keywords)}"))

        # 取前 3
        scored_docs.sort(key=lambda x: -x[0])
        top_docs = [
            {"path": doc_path, "reason": reason}
            for score, doc_path, reason in scored_docs[:3]
            if score >= 2  # 至少 2 个关键词重叠
        ]

        # 合并内置映射
        builtin = BUILTIN_MAPPINGS.get(rule_id, [])
        seen_paths = {d["path"] for d in top_docs}
        for b in builtin:
            if b["path"] not in seen_paths:
                top_docs.append(b)
                seen_paths.add(b["path"])

        if top_docs:
            mapping[rule_id] = top_docs

    return mapping


def rebuild_mapping(
    rule_dir: Path | None = None,
    output_path: Path = MAPPING_CACHE,
) -> None:
    """重建映射索引并写入缓存。"""
    print(f"Building rule-docs mapping...")
    mapping = build_mapping(rule_dir=rule_dir)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"✅ Mapping saved: {output_path} ({len(mapping)} rules mapped)")
    return mapping


def query_mapping(rule_id: str, mapping_path: Path = MAPPING_CACHE) -> list[dict[str, str]]:
    """查询单条规则的关联文档。"""
    if not mapping_path.exists():
        print(f"Mapping not found. Run with --rebuild first.")
        return []
    mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
    return mapping.get(rule_id, [])


# ─────────────────────────────────────────────────────────────
# CLI
# ─────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule-to-Docs mapping tool")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild mapping index")
    parser.add_argument("--query", type=str, help="Query docs for a rule ID")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if args.rebuild:
        mapping = rebuild_mapping()
        if args.json:
            print(json.dumps(mapping, ensure_ascii=False, indent=2))
        return 0

    if args.query:
        results = query_mapping(args.query)
        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
            return 0

        if not results:
            print(f"No docs found for rule: {args.query}")
            return 1
        print(f"\n📚 Docs related to '{args.query}':\n")
        for i, doc in enumerate(results, 1):
            print(f"  {i}. {doc['path']}")
            print(f"     ↳ {doc['reason']}")
        print()
        return 0

    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

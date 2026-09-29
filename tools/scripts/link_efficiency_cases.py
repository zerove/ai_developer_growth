#!/usr/bin/env python3
"""效率文档 ↔ 案例双向链接补全脚本 (V2.15 Phase 18)。

双向交叉引用的目的:
- 治理层方法论文档 (docs/efficiency/ai-*.md) 引用真实案例
  → 增强可验证性，避免"空谈方法论"
- 案例库 (case-studies/*.md) 引用相关方法论
  → 增强可发现性，方便查阅原理

策略 (保守, 仅追加不修改):
1. 解析每个效率文档的 frontmatter tags/keywords
2. 扫描 case-studies 标题和 tags 找匹配
3. 追加 \"**相关案例**: [name](case-studies/xxx.md)\" 段
4. 同样在案例文档追加 \"**相关方法论**: [name](docs/efficiency/ai-xxx.md)\" 段
5. 已有引用则跳过 (不重复)

不做的事:
- 不强制 1:1 映射 (有 0 或多个匹配都允许)
- 不删现有内容
- 不创建新文件
- 不使用 LLM/embedding (纯字符串匹配, 离线可跑)
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EFFICIENCY_DIR = REPO_ROOT / "docs" / "efficiency"
CASE_STUDIES_DIR = REPO_ROOT / "docs" / "case-studies"

# 关键词映射 (保守: 用词形变化做模糊匹配, 不依赖 embedding)
KEYWORD_ALIASES = {
    "review": ["review", "code-review", "审查"],
    "fix": ["fix", "auto-fix", "修复", "auto_fix"],
    "test": ["test", "tdd", "测试", "coverage"],
    "context": ["context", "上下文", "window"],
    "prompt": ["prompt", "提示", "提示词"],
    "debug": ["debug", "调试", "diagnose"],
    "performance": ["performance", "perf", "性能", "benchmark"],
    "migration": ["migration", "迁移", "migrate"],
    "documentation": ["doc", "documentation", "文档"],
    "deployment": ["deploy", "deployment", "部署", "cicd"],
    "refactor": ["refactor", "重构"],
    "architecture": ["architecture", "架构", "design", "微服务", "microservice"],
    "rule": ["rule", "规则", "governance", "治理"],
    "data": ["data", "数据", "pipeline", "etl"],
    "api": ["api", "接口", "rest", "graphql"],
    "database": ["database", "db", "数据库", "sql"],
    "frontend": ["frontend", "前端", "web", "ui"],
    "mobile": ["mobile", "移动", "移动端", "app"],
    "devops": ["devops", "运维", "ci"],
    "ml": ["ml", "machine-learning", "机器学习", "model", "ai模型"],
    "agent": ["agent", "代理", "多agent", "multi-agent", "多-agent", "多 agent"],
    "scraping": ["scraping", "爬虫", "抓取", "crawler"],
    "service": ["service", "服务", "customer", "客服"],
}


def _extract_keywords(filepath: Path) -> set[str]:
    """从 markdown 文件提取关键词 (frontmatter tags + 标题 + description)。

    V2.21 P5-8 拆分: 抽 _parse_frontmatter_keywords 收口 frontmatter 解析,
    _parse_h1_keywords 收口 H1 标题解析,
    主函数仅 try/except + 2 委托.
    """
    keywords: set[str] = set()
    try:
        content = filepath.read_text(encoding="utf-8")
    except Exception:
        return keywords
    keywords.update(_parse_frontmatter_keywords(content))
    keywords.update(_parse_h1_keywords(content))
    return keywords


def _parse_frontmatter_keywords(content: str) -> set[str]:
    """从 markdown frontmatter 提取 keywords (tags + description, 模块级 helper).

    Args:
        content: 完整 markdown 内容

    Returns:
        keyword 集合
    """
    keywords: set[str] = set()
    fm_match = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not fm_match:
        return keywords
    fm = fm_match.group(1)
    # tags: ['a', 'b']
    for tag in re.findall(r"tags:\s*\[([^\]]*)\]", fm):
        for t in re.split(r"[,\s]+", tag):
            t = t.strip().strip("'\"")
            if t:
                keywords.add(t.lower())
    # description: 中文长句, 按词切
    desc_match = re.search(r"description:\s*[\"']?(.+?)[\"']?\s*$", fm, re.MULTILINE)
    if desc_match:
        for word in re.split(r"[\s,;:，。；：、\.\?!]+", desc_match.group(1)):
            w = word.strip().lower()
            if w and len(w) > 1:
                keywords.add(w)
    return keywords


def _parse_h1_keywords(content: str) -> set[str]:
    """从 markdown H1 标题提取 keywords (模块级 helper).

    Args:
        content: 完整 markdown 内容

    Returns:
        keyword 集合
    """
    keywords: set[str] = set()
    for h1 in re.findall(r"^#\s+(.+)$", content, re.MULTILINE):
        for word in re.split(r"[\s,;:，。；：、\.\?!]+", h1):
            w = word.strip().lower()
            if w and len(w) > 1:
                keywords.add(w)
    return keywords


def _match_score(ai_kws: set[str], case_kws: set[str]) -> int:
    """两个关键词集合的重叠分数 (含 alias 展开)。"""
    score = 0
    for k in ai_kws:
        k_lower = k.lower()
        for ck in case_kws:
            ck_lower = ck.lower()
            if k_lower == ck_lower:
                score += 2
            else:
                # alias 匹配
                for alias_group in KEYWORD_ALIASES.values():
                    if k_lower in alias_group and ck_lower in alias_group:
                        score += 1
                        break
    return score


def _has_link(content: str, target_name: str) -> bool:
    """检查内容是否已引用 target_name。"""
    return target_name in content


def _collect_ai_to_case_links(
    ai_files: dict[Path, set[str]],
    case_files: dict[Path, set[str]],
    min_score: int,
) -> list[tuple[Path, str, str]]:
    """收集 ai-*.md → case-studies/*.md 链接 (相关案例)。

    ADR-014: 从 main 拆出。返回 (file_to_modify, header, link_line) 列表。
    """
    changes: list[tuple[Path, str, str]] = []
    for ai_path, ai_kws in ai_files.items():
        for case_path, case_kws in case_files.items():
            if _should_skip(case_path):
                continue
            score = _match_score(ai_kws, case_kws)
            if score < min_score:
                continue
            case_name = case_path.stem
            if _has_link(ai_path.read_text(encoding="utf-8", errors="ignore"), case_name):
                continue
            link_line = (
                f"- **相关案例**: [{case_name}]({os.path.relpath(case_path, EFFICIENCY_DIR).replace(os.sep, '/')})"
            )
            changes.append((ai_path, "## 相关案例", link_line))
    return changes


def _collect_case_to_ai_links(
    ai_files: dict[Path, set[str]],
    case_files: dict[Path, set[str]],
    min_score: int,
) -> list[tuple[Path, str, str]]:
    """收集 case-studies/*.md → ai-*.md 链接 (相关方法论)。

    ADR-014: 从 main 拆出。
    """
    changes: list[tuple[Path, str, str]] = []
    for case_path, case_kws in case_files.items():
        if _should_skip(case_path):
            continue
        for ai_path, ai_kws in ai_files.items():
            score = _match_score(ai_kws, case_kws)
            if score < min_score:
                continue
            ai_name = ai_path.stem
            if _has_link(case_path.read_text(encoding="utf-8", errors="ignore"), ai_name):
                continue
            link_line = (
                f"- **相关方法论**: [{ai_name}]({os.path.relpath(ai_path, case_path.parent).replace(os.sep, '/')})"
            )
            changes.append((case_path, "## 相关方法论", link_line))
    return changes


def _should_skip(case_path: Path) -> bool:
    """跳过模板/索引文件。"""
    return case_path.stem.startswith("TEMPLATE") or case_path.stem == "README"


def _print_plan(
    changes: list[tuple[Path, str, str]],
    ai_count: int,
    case_count: int,
) -> None:
    """打印补全计划。"""
    print(f"将补全 {len(changes)} 处交叉引用 ({ai_count} ai-docs × {case_count} cases):")
    for f, _header, line in changes[:10]:
        rel = f.relative_to(REPO_ROOT)
        print(f"  + {rel}: {line[:80]}")
    if len(changes) > 10:
        print(f"  ... 还有 {len(changes) - 10} 条")


def _apply_changes(changes: list[tuple[Path, str, str]]) -> int:
    """应用链接补全: 按文件分组, 追加段 + 链接。"""
    by_file: dict[Path, list[tuple[str, str]]] = {}
    for f, header, line in changes:
        by_file.setdefault(f, []).append((header, line))

    modified = 0
    for f, items in by_file.items():
        content = f.read_text(encoding="utf-8")
        for header, _ in items:
            if header not in content:
                content += f"\n\n{header}\n\n"
        for header, line in items:
            if line not in content:
                content = content.replace(header, f"{header}\n\n{line}", 1)
        f.write_text(content, encoding="utf-8")
        modified += 1
    return modified


def main() -> int:
    """CLI 入口: 解析参数 + 调度。"""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只打印计划, 不修改文件",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        default=2,
        help="最低匹配分数, 默认 2 (避免噪声链接)",
    )
    args = parser.parse_args()

    if not EFFICIENCY_DIR.exists() or not CASE_STUDIES_DIR.exists():
        print(f"❌ 目录不存在: {EFFICIENCY_DIR} 或 {CASE_STUDIES_DIR}")
        return 1

    ai_files = {f: _extract_keywords(f) for f in EFFICIENCY_DIR.glob("ai-*.md")}
    case_files = {f: _extract_keywords(f) for f in CASE_STUDIES_DIR.glob("*.md")}

    changes = _collect_ai_to_case_links(ai_files, case_files, args.min_score)
    changes.extend(_collect_case_to_ai_links(ai_files, case_files, args.min_score))

    if not changes:
        print("✅ 全部已交叉引用, 无需补全")
        return 0

    _print_plan(changes, len(ai_files), len(case_files))

    if args.dry_run:
        print("\n--dry-run 模式, 未修改文件")
        return 0

    modified = _apply_changes(changes)
    print(f"\n✅ 修改 {modified} 个文件")
    return 0


if __name__ == "__main__":
    sys.exit(main())

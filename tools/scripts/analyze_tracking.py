#!/usr/bin/env python3
"""
用户行为追踪数据分析工具

分析从 MkDocs 站点导出的 tracking JSON 数据:
- 搜索查询频率和成功率
- 页面热度和阅读时长
- 用户行为模式

用法:
    python -m tools.scripts.analyze_tracking <tracking.json>
    python -m tools.scripts.analyze_tracking <tracking.json> --top 20
    python -m tools.scripts.analyze_tracking <tracking.json> --export-synonyms
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


def load_tracking_data(filepath: str) -> dict[str, Any]:
    """加载追踪数据文件"""
    with open(filepath, encoding="utf-8") as f:
        result: dict[str, Any] = json.load(f)
        return result


def analyze_searches(data: dict[str, Any], top_n: int = 10) -> dict[str, Any]:
    """分析搜索查询"""
    searches = data.get("searches", [])
    if not searches:
        return {"total": 0, "unique": 0, "top": [], "zero_result": []}

    query_counter: Counter[str] = Counter()
    zero_result_queries = []

    for s in searches:
        q = s.get("q", "").strip()
        if q:
            query_counter[q] += 1
            if s.get("results", 0) == 0:
                zero_result_queries.append(q)

    return {
        "total": len(searches),
        "unique": len(query_counter),
        "top": query_counter.most_common(top_n),
        "zero_result": Counter(zero_result_queries).most_common(top_n),
    }


def analyze_pageviews(data: dict[str, Any], top_n: int = 10) -> dict[str, Any]:
    """分析页面访问"""
    pageviews = data.get("pageviews", [])
    if not pageviews:
        return {"total": 0, "unique": 0, "top": []}

    page_counter: Counter[str] = Counter()
    for pv in pageviews:
        page_counter[pv.get("page", "/")] += 1

    return {
        "total": len(pageviews),
        "unique": len(page_counter),
        "top": page_counter.most_common(top_n),
    }


def analyze_reading_time(data: dict[str, Any], top_n: int = 10) -> dict[str, Any]:
    """分析阅读时长"""
    reading_time = data.get("reading_time", {})
    if not reading_time:
        return {"total_seconds": 0, "total_minutes": 0, "top": []}

    sorted_pages = sorted(reading_time.items(), key=lambda x: x[1], reverse=True)
    total = sum(reading_time.values())

    return {
        "total_seconds": total,
        "total_minutes": round(total / 60, 1),
        "top": sorted_pages[:top_n],
    }


def _build_word_to_queries(queries: list[str]) -> dict[str, set[str]]:
    """建立 token (词根) → 共享该 token 的查询集合 索引.

    V2.19 P3-25 拆分: 从 suggest_synonym_groups (B=9) 抽出.
    仅保留长度 > 2 的 token, 过滤助词/短词.
    """
    word_to_queries: dict[str, set[str]] = {}
    for q in queries:
        tokens = set(q.lower().split())
        for token in tokens:
            if len(token) > 2:
                word_to_queries.setdefault(token, set()).add(q)
    return word_to_queries


def _group_by_shared_word(
    word_to_queries: dict[str, set[str]],
) -> list[list[str]]:
    """按共享 token 分组查询, 优先选 token 关联查询多的入组, 标记 visited 去重.

    V2.19 P3-25 拆分: 从 suggest_synonym_groups (B=9) 抽出.
    排序: 按 token 关联查询数倒序, 保证最大组优先.
    """
    visited: set[str] = set()
    groups: list[list[str]] = []
    for _word, q_set in sorted(word_to_queries.items(), key=lambda x: -len(x[1])):
        if len(q_set) < 2:
            continue
        group = sorted(q_set - visited)
        if len(group) >= 2:
            groups.append(group)
            visited.update(group)
    return groups


def suggest_synonym_groups(searches: list[tuple[str, int]]) -> list[list[str]]:
    """基于搜索查询建议同义词组 (orchestrator).

    V2.19 P3-25 拆分: 从 B=9 / 33 行函数拆出 2 个 helper.
    策略: 将查询分词 → 按共享词根分组.
    例如 "python tutorial" 和 "python guide" 共享 "python"，归为一组.
    """
    if not searches:
        return []
    queries = [q for q, _ in searches]
    word_to_queries = _build_word_to_queries(queries)
    return _group_by_shared_word(word_to_queries)


def _print_search_analysis(searches: dict[str, Any], top_n: int) -> None:
    """Print search analysis section."""
    print("\n  搜索查询")
    print(f"  总搜索次数: {searches['total']}")
    print(f"  唯一查询数: {searches['unique']}")
    if searches["top"]:
        print(f"\n  热门搜索 (Top {top_n}):")
        for q, count in searches["top"]:
            print(f"    {count:>4}x  {q}")
    if searches["zero_result"]:
        print("\n  零结果查询 (需关注):")
        for q, count in searches["zero_result"]:
            print(f"    {count:>4}x  {q}")


def _print_page_analysis(pageviews: dict[str, Any], top_n: int) -> None:
    """Print page analysis section."""
    print("\n  页面访问")
    print(f"  总访问量: {pageviews['total']}")
    print(f"  独立页面数: {pageviews['unique']}")
    if pageviews["top"]:
        print(f"\n  热门页面 (Top {top_n}):")
        for p, count in pageviews["top"]:
            print(f"    {count:>4}x  {p}")


def _print_reading_analysis(reading: dict[str, Any], top_n: int) -> None:
    """Print reading time analysis section."""
    print("\n  阅读时长")
    print(f"  总阅读时间: {reading['total_minutes']} 分钟")
    if reading["top"]:
        print(f"\n  最长阅读 (Top {top_n}):")
        for p, seconds in reading["top"]:
            mins = round(seconds / 60, 1)
            print(f"    {mins:>6.1f}min  {p}")


def _print_synonym_suggestions(searches: dict[str, Any]) -> None:
    """Print synonym group suggestions."""
    if searches["top"]:
        groups = suggest_synonym_groups(searches["top"])
        if groups:
            print("\n  同义词组建议 (基于搜索模式):")
            for g in groups:
                print(f"    {' / '.join(g)}")


def print_report(data: dict[str, Any], top_n: int = 10) -> None:
    """打印分析报告"""
    searches = analyze_searches(data, top_n)
    pageviews = analyze_pageviews(data, top_n)
    reading = analyze_reading_time(data, top_n)

    print("=" * 60)
    print("  AI Developer Growth - 用户行为分析报告")
    print("=" * 60)

    _print_search_analysis(searches, top_n)
    _print_page_analysis(pageviews, top_n)
    _print_reading_analysis(reading, top_n)
    _print_synonym_suggestions(searches)

    print("\n" + "=" * 60)


def main() -> None:
    parser = argparse.ArgumentParser(description="分析用户行为追踪数据")
    parser.add_argument("file", help="追踪数据 JSON 文件路径")
    parser.add_argument("--top", type=int, default=10, help="显示前 N 条结果")
    parser.add_argument(
        "--export-synonyms",
        action="store_true",
        help="导出同义词组为 JSON",
    )
    args = parser.parse_args()

    if not Path(args.file).exists():
        print(f"错误: 文件不存在 {args.file}", file=sys.stderr)
        sys.exit(1)

    data = load_tracking_data(args.file)

    if args.export_synonyms:
        searches = analyze_searches(data, 50)
        groups = suggest_synonym_groups(searches["top"])
        print(json.dumps(groups, ensure_ascii=False, indent=2))
    else:
        print_report(data, args.top)


if __name__ == "__main__":
    main()

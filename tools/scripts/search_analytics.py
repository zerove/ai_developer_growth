#!/usr/bin/env python3
"""检索查询日志分析器（消费侧证据链 P0-2）。

聚合 logs/search-queries.jsonl，输出：
- 总查询量与日均
- TOP 高频查询（用户真实需求画像）
- 零召回查询清单（检索质量改进的直接输入）
- 平均耗时

用法：
    python tools/scripts/search_analytics.py                 # 全量汇总
    python tools/scripts/search_analytics.py --days 7        # 最近 7 天
    python tools/scripts/search_analytics.py --zero-only     # 只看零召回
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_LOG = ROOT / "logs" / "search-queries.jsonl"

_TS_FORMATS = ("%Y-%m-%dT%H:%M:%S%z", "%Y%m%dT%H%M%S%z", "%Y-%m-%dT%H:%M:%S")


def _parse_ts(ts: str) -> float | None:
    """解析日志时间戳（兼容 ISO 带连字符与紧凑两种格式），失败返回 None。"""
    for fmt in _TS_FORMATS:
        try:
            return time.mktime(time.strptime(ts, fmt))
        except ValueError:
            continue
    return None


def load_records(path: Path, days: int | None) -> list[dict[str, object]]:
    """加载日志记录，按天数过滤。"""
    if not path.exists():
        return []
    cutoff = time.time() - days * 86400 if days else None
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        if cutoff is not None:
            ts = _parse_ts(rec.get("ts", ""))
            if ts is not None and ts < cutoff:
                continue
        records.append(rec)
    return records


def analyze(records: list[dict[str, object]], top_n: int = 10) -> dict[str, object]:
    """核心聚合逻辑（独立函数便于测试）。"""
    total = len(records)
    zero_recall = [str(r["query"]) for r in records if r.get("total", 0) == 0]
    queries = [str(r["query"]) for r in records]
    times: list[float] = []
    for r in records:
        raw = r.get("time_ms", 0.0)
        if isinstance(raw, (int, float)):
            times.append(float(raw))
    return {
        "total": total,
        "unique": len(set(queries)),
        "avg_time_ms": round(sum(times) / len(times), 2) if times else 0.0,
        "zero_recall_count": len(zero_recall),
        "zero_recall_rate": round(len(zero_recall) / total * 100, 1) if total else 0.0,
        "top_queries": [{"query": q, "count": c} for q, c in Counter(queries).most_common(top_n)],
        "zero_queries": [{"query": q, "count": c} for q, c in Counter(zero_recall).most_common(top_n)],
    }


def render(report: dict[str, object], days: int | None) -> str:
    """渲染为文本周报。"""
    lines = ["=" * 50, "知识库检索查询分析报告", f"范围: 最近 {days} 天" if days else "范围: 全部", "=" * 50]
    lines.append(f"总查询: {report['total']}  唯一查询: {report['unique']}  平均耗时: {report['avg_time_ms']}ms")
    lines.append(f"零召回: {report['zero_recall_count']} 次 ({report['zero_recall_rate']}%)")
    top_queries = report.get("top_queries", [])
    zero_queries = report.get("zero_queries", [])
    if isinstance(top_queries, list):
        lines.append("\n── TOP 查询 ──")
        for item in top_queries:
            if isinstance(item, dict):
                lines.append(f"  {item.get('count', 0):4d}  {item.get('query', '')}")
    if isinstance(zero_queries, list):
        lines.append("\n── 零召回查询（建议补同义词/检查分词）──")
        for item in zero_queries:
            if isinstance(item, dict):
                lines.append(f"  {item.get('count', 0):4d}  {item.get('query', '')}")
    lines.append("=" * 50)
    return "\n".join(lines)


def export_zero_recall_synonyms(report: dict[str, object], out_path: Path) -> int:
    """P0-3：零召回查询导出为同义词典候选格式，供人工确认后合并。"""
    raw_zero = report.get("zero_queries", [])
    zero_items = [item for item in raw_zero if isinstance(item, dict)] if isinstance(raw_zero, list) else []
    entries = [
        {"query": item.get("query", ""), "suggested_action": "加入 SynonymDictionary 或检查 jieba 分词"}
        for item in zero_items
    ]
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(entries, ensure_ascii=False, indent=2), encoding="utf-8")
    return len(entries)


def main() -> int:
    parser = argparse.ArgumentParser(description="检索查询日志分析")
    parser.add_argument("--log", type=Path, default=DEFAULT_LOG)
    parser.add_argument("--days", type=int, default=None, help="只统计最近 N 天")
    parser.add_argument("--top", type=int, default=10)
    parser.add_argument("--zero-only", action="store_true")
    parser.add_argument("--export-zero", type=Path, default=None, help="零召回清单导出路径（同义词典候选）")
    args = parser.parse_args()

    records = load_records(args.log, args.days)
    report = analyze(records, args.top)
    print(render(report, args.days))

    if args.export_zero:
        count = export_zero_recall_synonyms(report, args.export_zero)
        print(f"\n已导出 {count} 条零召回候选 → {args.export_zero}")

    if args.zero_only and report["zero_recall_count"] == 0:
        print("无零召回记录。")
    return 0


if __name__ == "__main__":
    sys.exit(main())

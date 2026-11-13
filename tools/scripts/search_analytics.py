#!/usr/bin/env python3
"""检索查询日志分析器（消费侧证据链 P0-2）。

聚合 logs/search-queries.jsonl，输出：
- 总查询量与日均
- TOP 高频查询（用户真实需求画像）
- 零召回查询清单（检索质量改进的直接输入）
- 平均耗时

用法：
    python -m tools.scripts.search_analytics                 # 全量汇总
    python -m tools.scripts.search_analytics --days 7        # 最近 7 天
    python -m tools.scripts.search_analytics --zero-only     # 只看零召回
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


def _parse_line(line: str) -> dict[str, object] | None:
    """解析单行 JSON, 失败或空行返回 None.

    V2.19 P3-23 拆分: 从 load_records (B=9) 抽出.
    """
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except json.JSONDecodeError:
        return None


def _is_after_cutoff(rec: dict[str, object], cutoff: float | None) -> bool:
    """检查 rec 是否应保留 (cutoff 过滤后).

    V2.19 P3-23 拆分: 从 load_records (B=9) 抽出.
    返回 True 表示保留:
    - cutoff 为 None (不需过滤) → 保留
    - ts 解析失败 (None) → 保守保留 (不过滤, 避免误删)
    - ts >= cutoff → 保留
    - ts < cutoff → 剔除
    """
    if cutoff is None:
        return True
    raw_ts = rec.get("ts", "")
    if not isinstance(raw_ts, str):
        return True
    ts = _parse_ts(raw_ts)
    if ts is None:
        return True  # 无效 ts 保守保留
    return ts >= cutoff


def _compute_cutoff(days: int | None) -> float | None:
    """根据 days 计算 cutoff 时间戳 (None 表示不需过滤).

    V2.19 P3-45 拆分: 从 load_records (B=6) 抽出.
    """
    if not days:
        return None
    return time.time() - days * 86400


def load_records(path: Path, days: int | None) -> list[dict[str, object]]:
    """加载日志记录, 按天数过滤 (orchestrator).

    V2.19 P3-45 拆分: 从 B=6 / 17 行函数拆出 _compute_cutoff.
    主函数仅负责: 守卫文件存在 → 委托 cutoff 计算 → 委托行解析 + 判定 → 收集.
    """
    if not path.exists():
        return []
    cutoff = _compute_cutoff(days)
    records: list[dict[str, object]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = _parse_line(line)
        if rec is None:
            continue
        if not _is_after_cutoff(rec, cutoff):
            continue
        records.append(rec)
    return records


def _collect_query_times(records: list[dict[str, object]]) -> list[float]:
    """收集每条记录的有效 time_ms (int/float 转 float).

    V2.19 P3-22 拆分: 从 analyze (B=10) 抽出.
    """
    times: list[float] = []
    for r in records:
        raw = r.get("time_ms", 0.0)
        if isinstance(raw, (int, float)):
            times.append(float(raw))
    return times


def _top_n_counts(items: list[str], top_n: int) -> list[dict[str, object]]:
    """统计 items 出现次数并取 top_n, 返回 [{query, count}] 列表.

    V2.19 P3-22 拆分: 从 analyze (B=10) 抽出.
    """
    return [{"query": q, "count": c} for q, c in Counter(items).most_common(top_n)]


def _count_unique_queries(queries: list[str]) -> int:
    """统计唯一查询数 (集合大小).

    V2.19 P3-44 拆分: 从 analyze (B=6) 抽出.
    """
    return len(set(queries))


def _calc_zero_recall_rate(zero_count: int, total: int) -> float:
    """计算零召回率 (%), 空记录返 0.0.

    V2.19 P3-44 拆分: 从 analyze (B=6) 抽出.
    """
    if not total:
        return 0.0
    return round(zero_count / total * 100, 1)


def analyze(records: list[dict[str, object]], top_n: int = 10) -> dict[str, object]:
    """核心聚合逻辑 (orchestrator).

    V2.19 P3-44 拆分: 从 B=6 / 20 行函数拆出 2 个 helper.
    主函数仅负责: 基础计数 + 委托 2 helper + 装配 result dict.
    """
    total = len(records)
    queries = [str(r["query"]) for r in records]
    zero_recall = [str(r["query"]) for r in records if r.get("total", 0) == 0]
    times = _collect_query_times(records)

    return {
        "total": total,
        "unique": _count_unique_queries(queries),
        "avg_time_ms": round(sum(times) / len(times), 2) if times else 0.0,
        "zero_recall_count": len(zero_recall),
        "zero_recall_rate": _calc_zero_recall_rate(len(zero_recall), total),
        "top_queries": _top_n_counts(queries, top_n),
        "zero_queries": _top_n_counts(zero_recall, top_n),
    }


def _render_header(days: int | None) -> list[str]:
    """渲染报告 header (标题 + 范围).

    V2.19 P3-24 拆分: 从 render (B=8) 抽出.
    """
    return [
        "=" * 50,
        "知识库检索查询分析报告",
        f"范围: 最近 {days} 天" if days else "范围: 全部",
        "=" * 50,
    ]


def _render_query_list(
    items: object,
    title: str,
) -> list[str]:
    """渲染查询列表段 (TOP/零召回) 文本.

    V2.19 P3-24 拆分: 从 render (B=8) 抽出.
    items 应为 list[dict], 非 list 防御性跳过.
    """
    if not isinstance(items, list):
        return []
    lines = ["", f"── {title} ──"]
    for item in items:
        if isinstance(item, dict):
            count = item.get("count", 0)
            query = item.get("query", "")
            lines.append(f"  {count:4d}  {query}")
    return lines


def render(report: dict[str, object], days: int | None) -> str:
    """渲染为文本周报 (orchestrator).

    V2.19 P3-24 拆分: 从 B=8 / 20 行函数拆出 2 个 helper.
    主函数仅负责: 拼装 header + summary + 2 段列表 + footer.
    """
    lines = _render_header(days)
    lines.append(f"总查询: {report['total']}  唯一查询: {report['unique']}  平均耗时: {report['avg_time_ms']}ms")
    lines.append(f"零召回: {report['zero_recall_count']} 次 ({report['zero_recall_rate']}%)")
    lines.extend(_render_query_list(report.get("top_queries", []), "TOP 查询"))
    lines.extend(
        _render_query_list(
            report.get("zero_queries", []),
            "零召回查询（建议补同义词/检查分词）",
        )
    )
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

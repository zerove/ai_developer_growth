#!/usr/bin/env python3
"""Rule Effectiveness Tracking (#5): track rule hit rates, false positives, fix rates.

Records validation results and provides analytics.

Usage:
    python tools/scripts/rule_tracker.py record --file results.json
    python tools/scripts/rule_tracker.py report
    python tools/scripts/rule_tracker.py report --lang python
    python tools/scripts/rule_tracker.py report --days 30
    python tools/scripts/rule_tracker.py export --format csv
    python tools/scripts/rule_tracker.py prune --keep 100
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _data_dir() -> Path:
    d = Path.home() / ".ai-rules-tracking"
    d.mkdir(exist_ok=True)
    return d


def _records_file() -> Path:
    return _data_dir() / "records.jsonl"


def cmd_record(args: argparse.Namespace) -> None:
    """Record validation results from a JSON file or stdin."""
    if args.file == "-":
        data = json.load(sys.stdin)
    else:
        with open(args.file) as f:
            data = json.load(f)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "project": args.project or "unknown",
        "results": data.get("results", []),
        "health_score": data.get("health_score"),
        "summary": {
            "total_files": len(data.get("results", [])),
            "total_issues": sum(len(r.get("issues", [])) for r in data.get("results", [])),
            "by_severity": _count_by_severity(data.get("results", [])),
            "by_rule": _count_by_rule(data.get("results", [])),
        },
    }

    with open(_records_file(), "a") as f:
        f.write(json.dumps(record) + "\n")

    print(f"Recorded: {record['summary']['total_issues']} issues in {record['summary']['total_files']} files")


def _count_by_severity(results: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in results:
        for issue in r.get("issues", []):
            counts[issue.get("severity", "unknown")] += 1
    return dict(counts)


def _count_by_rule(results: list[Any]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for r in results:
        for issue in r.get("issues", []):
            counts[issue.get("rule_id", "unknown")] += 1
    return dict(counts)


def _parse_record_line(line: str) -> dict[str, Any] | None:
    """解析单行 JSON 记录, 失败或空行返回 None.

    V2.19 P3-28 拆分: 从 _load_records (B=8) 抽出.
    """
    line = line.strip()
    if not line:
        return None
    try:
        return json.loads(line)
    except (json.JSONDecodeError, KeyError):
        return None


def _is_within_window(record: dict[str, Any], cutoff: float | None) -> bool:
    """检查 record 时间戳是否在 cutoff 之后.

    V2.19 P3-28 拆分: 从 _load_records (B=8) 抽出.
    返回 True 表示保留:
    - cutoff 为 None (不需过滤) → 保留
    - 缺 timestamp / ts 解析失败 / ts < cutoff → 剔除 (原 KeyError 行为)
    - ts >= cutoff → 保留
    """
    if cutoff is None:
        return True
    raw_ts = record.get("timestamp", "")
    if not isinstance(raw_ts, str):
        return False  # 缺 timestamp 严格剔除 (匹配原 KeyError 行为)
    try:
        ts = datetime.fromisoformat(raw_ts).timestamp()
    except ValueError:
        return False
    return ts >= cutoff


def _load_records(days: int | None = None) -> list[dict[str, Any]]:
    """Load records, optionally filtered by days (orchestrator).

    V2.19 P3-28 拆分: 从 B=8 / 22 行函数拆出 2 个 helper.
    主函数仅负责: 守卫文件存在 → 委托行解析 + 时间窗口判定 → 收集.
    """
    if not _records_file().exists():
        return []
    cutoff: float | None = None
    if days:
        cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)

    records: list[dict[str, Any]] = []
    with open(_records_file()) as f:
        for line in f:
            record = _parse_record_line(line)
            if record is None:
                continue
            if not _is_within_window(record, cutoff):
                continue
            records.append(record)
    return records


def _aggregate_record(
    rec: dict[str, Any],
    rule_counts: dict[str, int],
    severity_counts: dict[str, int],
    lang_counts: dict[str, int],
) -> int:
    """聚合单条记录到 3 个 dict 累加器, 返回 total_issues 增量.

    V2.19 P3-29 拆分: 从 _aggregate_records (B=6) 抽出.
    """
    summary = rec.get("summary", {})
    total = summary.get("total_issues", 0)

    for rule_id, count in summary.get("by_rule", {}).items():
        rule_counts[rule_id] += count
    for sev, count in summary.get("by_severity", {}).items():
        severity_counts[sev] += count

    # lang_counts: 从 rule_id 前缀提取 (e.g. "py-E501" -> "py")
    for rule_id, count in summary.get("by_rule", {}).items():
        parts = rule_id.split("-")
        if len(parts) >= 2:
            lang_counts[parts[0]] += count

    return int(total)


def _build_trend_point(rec: dict[str, Any]) -> tuple[str, int]:
    """构造 (date_str, total_issues) trend 点.

    V2.19 P3-29 拆分: 从 _aggregate_records (B=6) 抽出.
    date_str 取 timestamp 前 10 字符 (YYYY-MM-DD).
    """
    summary = rec.get("summary", {})
    return rec["timestamp"][:10], int(summary.get("total_issues", 0))


def _aggregate_records(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate statistics from records (orchestrator).

    V2.19 P3-29 拆分: 从 B=6 / 33 行函数拆出 2 个 helper.
    主函数仅负责: 初始化累加器 → 委托聚合 + trend → 装配 result.
    """
    total_issues = 0
    rule_counts: dict[str, int] = defaultdict(int)
    severity_counts: dict[str, int] = defaultdict(int)
    lang_counts: dict[str, int] = defaultdict(int)
    trend: list[tuple[str, int]] = []

    for rec in records:
        total_issues += _aggregate_record(rec, rule_counts, severity_counts, lang_counts)
        trend.append(_build_trend_point(rec))

    return {
        "total_issues": total_issues,
        "rule_counts": rule_counts,
        "severity_counts": severity_counts,
        "lang_counts": lang_counts,
        "trend": trend,
        "records_count": len(records),
    }


def _print_json_report(stats: dict[str, Any]) -> None:
    """Print report in JSON format."""
    print(
        json.dumps(
            {
                "records": stats["records_count"],
                "total_issues": stats["total_issues"],
                "by_rule": dict(sorted(stats["rule_counts"].items(), key=lambda x: -int(x[1]))),
                "by_severity": dict(stats["severity_counts"]),
                "by_language": dict(sorted(stats["lang_counts"].items(), key=lambda x: -int(x[1]))),
            },
            indent=2,
        )
    )


def _print_text_report(stats: dict[str, Any], args: argparse.Namespace) -> None:
    """Print report in text format."""
    print("Rule Effectiveness Report")
    print(f"{'=' * 50}")
    print(f"Period: {stats['records_count']} records")
    if args.days:
        print(f"  (last {args.days} days)")
    print(f"Total issues found: {stats['total_issues']}")
    print()

    # Top rules
    print("Top 10 Most-Triggered Rules:")
    print(f"  {'Rule ID':<35} {'Count':<8} {'%'}")
    print(f"  {'-' * 55}")
    for rule_id, count in sorted(stats["rule_counts"].items(), key=lambda x: -x[1])[:10]:
        pct = (count / stats["total_issues"] * 100) if stats["total_issues"] else 0
        print(f"  {rule_id:<35} {count:<8} {pct:.1f}%")
    print()

    # By language
    print("Issues by Language:")
    for lang, count in sorted(stats["lang_counts"].items(), key=lambda x: -x[1]):
        print(f"  {lang:<15} {count}")
    print()

    # By severity
    print("By Severity:")
    for sev, count in sorted(stats["severity_counts"].items()):
        print(f"  {sev:<10} {count}")


def cmd_report(args: argparse.Namespace) -> None:
    """Generate effectiveness report."""
    records = _load_records(args.days)

    if not records:
        print("No records found. Run 'record' first.")
        return

    stats = _aggregate_records(records)

    if args.json:
        _print_json_report(stats)
    else:
        _print_text_report(stats, args)


def cmd_export(args: argparse.Namespace) -> None:
    """Export records as CSV."""
    records = _load_records(args.days)

    if not records:
        print("No records found.")
        return

    print("timestamp,project,total_files,total_issues,health_score")
    for rec in records:
        summary = rec.get("summary", {})
        print(
            f"{rec['timestamp']},{rec.get('project', '')},"
            f"{summary.get('total_files', 0)},{summary.get('total_issues', 0)},"
            f"{rec.get('health_score', '')}"
        )


def cmd_prune(args: argparse.Namespace) -> None:
    """Keep only the last N records."""
    records = _load_records()

    if len(records) <= args.keep:
        print(f"Only {len(records)} records, nothing to prune.")
        return

    # Keep most recent
    records = records[-args.keep :]

    with open(_records_file(), "w") as f:
        for rec in records:
            f.write(json.dumps(rec) + "\n")

    print(f"Pruned to {args.keep} records")


def main() -> int:
    parser = argparse.ArgumentParser(description="Rule Effectiveness Tracking")
    sub = parser.add_subparsers(dest="command")

    rec_p = sub.add_parser("record", help="Record validation results")
    rec_p.add_argument("--file", type=str, required=True, help="JSON results file (or - for stdin)")
    rec_p.add_argument("--project", type=str, help="Project name")

    rep_p = sub.add_parser("report", help="Generate report")
    rep_p.add_argument("--lang", type=str, help="Filter by language")
    rep_p.add_argument("--days", type=int, help="Last N days")
    rep_p.add_argument("--json", action="store_true", help="JSON output")

    exp_p = sub.add_parser("export", help="Export as CSV")
    exp_p.add_argument("--days", type=int, help="Last N days")

    pru_p = sub.add_parser("prune", help="Prune old records")
    pru_p.add_argument("--keep", type=int, default=100, help="Number of records to keep")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    commands = {
        "record": cmd_record,
        "report": cmd_report,
        "export": cmd_export,
        "prune": cmd_prune,
    }

    commands[args.command](args)
    return 0


if __name__ == "__main__":
    sys.exit(main())

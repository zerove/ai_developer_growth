"""审计台账趋势分析。

读取 hash 链台账 (.quality-trends/audit_ledger.jsonl)，提供:
1. 链完整性校验（防篡改）
2. 按事件类型统计与按天聚合
3. 异常检测: 最近 24h 事件量显著高于历史水平时告警

用法:
    python tools/scripts/audit_trends.py            # 文本报告
    python tools/scripts/audit_trends.py --json     # JSON 输出（供 CI/看板消费）
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from tools.scripts._common import get_project_root

# 异常检测阈值: 最近24h事件数需同时满足绝对下限与相对倍数才告警，避免小样本误报
ALERT_MIN_COUNT = 5
ALERT_MULTIPLIER = 3.0


def _load_entries(ledger_file: Path) -> list[dict[str, Any]]:
    if not ledger_file.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in ledger_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


def verify_chain(entries: list[dict[str, Any]]) -> tuple[bool, str]:
    """校验 hash 链连续性: prev_hash 必须等于前一条 current_hash。"""
    prev = "0" * 64
    for i, entry in enumerate(entries):
        if entry.get("prev_hash") != prev:
            return False, f"第 {i + 1} 条记录链断裂 (prev_hash 不匹配)"
        prev = entry.get("current_hash", "")
    return True, f"链完整: {len(entries)} 条记录"


def _parse_timestamp(entry: dict[str, Any]) -> datetime | None:
    raw = entry.get("timestamp")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(str(raw))
    except ValueError:
        return None


def analyze(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """统计与异常检测。"""
    type_counts: Counter[str] = Counter()
    daily: dict[str, Counter[str]] = defaultdict(Counter)
    now = datetime.now(timezone.utc)
    last_24h: Counter[str] = Counter()

    for entry in entries:
        etype = str(entry.get("event_type", "UNKNOWN"))
        type_counts[etype] += 1
        ts = _parse_timestamp(entry)
        if ts is None:
            continue
        day = ts.astimezone(timezone.utc).date().isoformat()
        daily[day][etype] += 1
        if now - ts <= timedelta(hours=24):
            last_24h[etype] += 1

    # 历史日均（按有记录的天数计算）
    num_days = max(len(daily), 1)
    alerts: list[str] = []
    for etype, recent in last_24h.items():
        historical_daily = (type_counts[etype] - recent) / num_days
        if recent < ALERT_MIN_COUNT:
            continue
        if historical_daily == 0:
            alerts.append(f"{etype}: 最近24h {recent} 次（新出现的事件类型且超过下限 {ALERT_MIN_COUNT}）")
        elif recent > historical_daily * ALERT_MULTIPLIER:
            alerts.append(f"{etype}: 最近24h {recent} 次，历史日均 {historical_daily:.1f} 次（>{ALERT_MULTIPLIER}x）")

    return {
        "total": len(entries),
        "by_type": dict(type_counts),
        "daily": {day: dict(c) for day, c in sorted(daily.items())},
        "last_24h": dict(last_24h),
        "alerts": alerts,
        "undated_entries": sum(1 for e in entries if _parse_timestamp(e) is None),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="审计台账趋势分析")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--root", type=Path, default=None, help="项目根目录")
    args = parser.parse_args()

    root = args.root or get_project_root()
    ledger_file = root / ".quality-trends" / "audit_ledger.jsonl"
    entries = _load_entries(ledger_file)

    chain_ok, chain_desc = verify_chain(entries)
    report = analyze(entries)

    if args.json:
        print(json.dumps({"chain_ok": chain_ok, "chain_desc": chain_desc, **report}, ensure_ascii=False, indent=2))
    else:
        print(f"📊 审计台账趋势 ({ledger_file})")
        print(f"   链校验: {'✅ ' + chain_desc if chain_ok else '❌ ' + chain_desc}")
        print(f"   总条目: {report['total']}（无时间戳旧条目 {report['undated_entries']} 条）")
        print("   按类型:")
        for etype, count in sorted(report["by_type"].items(), key=lambda kv: -kv[1]):
            print(f"     - {etype}: {count}")
        if report["last_24h"]:
            print(f"   最近24h: {report['last_24h']}")
        if report["alerts"]:
            print("   ⚠️  异常:")
            for a in report["alerts"]:
                print(f"     - {a}")
        else:
            print("   ✅ 无异常波动")

    if not chain_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

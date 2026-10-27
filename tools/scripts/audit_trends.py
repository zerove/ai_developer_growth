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

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts._common import get_project_root  # noqa: E402

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


def _build_event_counters(
    entries: list[dict[str, Any]], now: datetime
) -> tuple[Counter[str], dict[str, Counter[str]], Counter[str]]:
    """构建 3 项 Counter: 总数 / 按天 / 最近 24h.

    V2.18 P3-13 拆分: 从 analyze (C=11) 抽出.
    返回 (type_counts, daily, last_24h).
    """
    type_counts: Counter[str] = Counter()
    daily: dict[str, Counter[str]] = defaultdict(Counter)
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

    return type_counts, dict(daily), last_24h


def _detect_alerts(
    type_counts: Counter[str],
    last_24h: Counter[str],
    num_days: int,
) -> list[str]:
    """检测 24h 异常波动.

    V2.18 P3-13 拆分: 从 analyze (C=11) 抽出.
    触发条件: 最近 24h 数 >= ALERT_MIN_COUNT 且 > 历史日均 * ALERT_MULTIPLIER.
    """
    alerts: list[str] = []
    for etype, recent in last_24h.items():
        historical_daily = (type_counts[etype] - recent) / num_days
        if recent < ALERT_MIN_COUNT:
            continue
        if historical_daily == 0:
            alerts.append(f"{etype}: 最近24h {recent} 次（新出现的事件类型且超过下限 {ALERT_MIN_COUNT}）")
        elif recent > historical_daily * ALERT_MULTIPLIER:
            alerts.append(f"{etype}: 最近24h {recent} 次，历史日均 {historical_daily:.1f} 次（>{ALERT_MULTIPLIER}x）")
    return alerts


def analyze(entries: list[dict[str, Any]]) -> dict[str, Any]:
    """统计与异常检测 (orchestrator).

    V2.18 P3-13 拆分: 从 C=11 / 45 行主函数拆出 2 个 helper.
    主函数仅负责: 加载数据 → 委托 counters/alerts → 汇总.
    """
    now = datetime.now(timezone.utc)
    type_counts, daily, last_24h = _build_event_counters(entries, now)

    num_days = max(len(daily), 1)
    alerts = _detect_alerts(type_counts, last_24h, num_days)

    return {
        "total": len(entries),
        "by_type": dict(type_counts),
        "daily": {day: dict(c) for day, c in sorted(daily.items())},
        "last_24h": dict(last_24h),
        "alerts": alerts,
        "undated_entries": sum(1 for e in entries if _parse_timestamp(e) is None),
    }


def _render_json_report(
    chain_ok: bool,
    chain_desc: str,
    report: dict[str, Any],
) -> None:
    """渲染 JSON 格式报告.

    V2.19 P3-27 拆分: 从 main (B=9) 抽出.
    """
    print(
        json.dumps(
            {"chain_ok": chain_ok, "chain_desc": chain_desc, **report},
            ensure_ascii=False,
            indent=2,
        )
    )


def _render_chain_status(chain_ok: bool, chain_desc: str) -> None:
    """渲染链校验状态行.

    V2.19 P3-27 拆分: 从 main (B=9) 抽出.
    """
    prefix = "✅ " if chain_ok else "❌ "
    print(f"   链校验: {prefix}{chain_desc}")


def _render_alerts(alerts: list[str]) -> None:
    """渲染异常告警段 (含空态).

    V2.19 P3-27 拆分: 从 main (B=9) 抽出.
    """
    if alerts:
        print("   ⚠️  异常:")
        for a in alerts:
            print(f"     - {a}")
    else:
        print("   ✅ 无异常波动")


def _render_text_report(
    ledger_file: Path,
    chain_ok: bool,
    chain_desc: str,
    report: dict[str, Any],
) -> None:
    """渲染 text 格式报告 (含 header + summary + by_type + last_24h + alerts).

    V2.19 P3-43 拆分: 从 main (B=6) 抽出.
    """
    print(f"📊 审计台账趋势 ({ledger_file})")
    _render_chain_status(chain_ok, chain_desc)
    print(f"   总条目: {report['total']}（无时间戳旧条目 {report['undated_entries']} 条）")
    print("   按类型:")
    for etype, count in sorted(report["by_type"].items(), key=lambda kv: -kv[1]):
        print(f"     - {etype}: {count}")
    if report["last_24h"]:
        print(f"   最近24h: {report['last_24h']}")
    _render_alerts(report["alerts"])


def _build_main_parser() -> argparse.ArgumentParser:
    """构造 CLI 参数解析器.

    V2.19 P3-43 拆分: 从 main (B=6) 抽出.
    """
    parser = argparse.ArgumentParser(description="审计台账趋势分析")
    parser.add_argument("--json", action="store_true", help="输出 JSON 格式")
    parser.add_argument("--root", type=Path, default=None, help="项目根目录")
    return parser


def main() -> int:
    """CLI 入口 (orchestrator).

    V2.19 P3-43 拆分: 从 B=6 / 37 行 main 拆出 2 个 helper.
    主函数仅负责: 解析参数 → 加载数据 → 委托 JSON/text 渲染 → 返回 exit code.
    """
    args = _build_main_parser().parse_args()

    root = args.root or get_project_root()
    ledger_file = root / ".quality-trends" / "audit_ledger.jsonl"
    entries = _load_entries(ledger_file)

    chain_ok, chain_desc = verify_chain(entries)
    report = analyze(entries)

    if args.json:
        _render_json_report(chain_ok, chain_desc, report)
    else:
        _render_text_report(ledger_file, chain_ok, chain_desc, report)

    if not chain_ok:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

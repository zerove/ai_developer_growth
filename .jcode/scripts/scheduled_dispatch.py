#!/usr/bin/env python3
"""scheduled hooks 到期调度器。

读取 hooks.json 的 scheduled 触发器，用 croniter 判断（或内置简化 cron 解析）
哪些任务在本次调用时到期，逐个执行并记录 last-run 时间戳防重复。
配合 systemd timer 每小时调用一次：
    python3 .jcode/scripts/scheduled_dispatch.py --due-now
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path
from time import struct_time
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
CONFIG = ROOT / ".jcode" / "hooks.json"
STATE = ROOT / ".jcode" / ".scheduled-last-run.json"


def load_state() -> dict[str, float]:
    if STATE.exists():
        try:
            return {k: float(v) for k, v in json.loads(STATE.read_text()).items()}
        except (json.JSONDecodeError, ValueError):
            return {}
    return {}


def save_state(state: dict[str, float]) -> None:
    STATE.write_text(json.dumps(state, indent=2))


def parse_cron(expr: str) -> tuple[set[int], set[int], set[int], set[int], set[int]]:
    """解析 '分 时 日 月 周'，返回 (分钟, 小时, 日, 月, 周) 五个取值集合。

    早前只展开分/时两个字段，日/月/周 split 进 fields 后从未求值，导致
    hooks.json 里 5 条 `0 9 * * 1`（每周一）实际每天触发、2 条
    `0 9 1 * *`（每月 1 日）实际每天触发——定期任务频率被放大 7~30 倍。

    星期沿用 cron 约定：0 与 7 均表示周日，同时接受 0-6。
    """
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"bad cron: {expr}")

    def expand(field: str, low: int, high: int) -> set[int]:
        vals: set[int] = set()
        for part in field.split(","):
            if part == "*":
                vals.update(range(low, high + 1))
            elif "-" in part:
                a, b = part.split("-", 1)
                start, end = int(a), int(b)
                if start > end:
                    raise ValueError(f"bad cron range {part!r} in {expr!r}")
                vals.update(range(start, end + 1))
            else:
                vals.add(int(part))
        # 越界值会永远不匹配（定时任务静默从不执行），必须显式拒绝
        out_of_range = sorted(v for v in vals if not low <= v <= high)
        if out_of_range:
            raise ValueError(f"cron value out of range {out_of_range} in {expr!r} (allowed {low}-{high})")
        return vals

    minutes = expand(fields[0], 0, 59)
    hours = expand(fields[1], 0, 23)
    days = expand(fields[2], 1, 31)
    months = expand(fields[3], 1, 12)
    weekdays = expand(fields[4], 0, 7)
    if 7 in weekdays:  # cron 里 7 与 0 都表示周日
        weekdays.discard(7)
        weekdays.add(0)
    return minutes, hours, days, months, weekdays


def _py_weekday_to_cron(tm_wday: int) -> int:
    """struct_time.tm_wday（周一=0）转 cron 星期（周日=0、周一=1）。"""
    return (tm_wday + 1) % 7


def is_due(hook: dict[str, Any], now: struct_time | None = None, state: dict[str, float] | None = None) -> bool:
    """判断 hook 是否到期：启用中、时间匹配 cron 且本小时尚未执行过。"""
    if not hook.get("enabled", True):
        return False
    now = now or time.localtime()
    state = state or {}
    expr = hook["schedule"]
    minutes, hours, days, months, weekdays = parse_cron(expr)
    if now.tm_min not in minutes or now.tm_hour not in hours or now.tm_mon not in months:
        return False

    # cron 标准语义：日与周都受限则取"或"（任一匹配即触发）；
    # 仅其一受限则必须匹配该字段；两者皆为 * 则不参与判定。
    fields = expr.split()
    day_restricted = fields[2] != "*"
    week_restricted = fields[4] != "*"
    if day_restricted and week_restricted:
        if now.tm_mday not in days and _py_weekday_to_cron(now.tm_wday) not in weekdays:
            return False
    elif day_restricted:
        if now.tm_mday not in days:
            return False
    elif week_restricted:
        if _py_weekday_to_cron(now.tm_wday) not in weekdays:
            return False

    name = hook["name"]
    last = state.get(name, 0)
    # 按小时去重（用 %Y%m%d%H）：cron 最小精度为分钟，若按日去重会把
    # 每小时的 hook（0 * * * *）压成每天仅一次。
    return time.strftime("%Y%m%d%H", now) != time.strftime("%Y%m%d%H", time.localtime(last))


def dispatch(dry_run: bool = False) -> int:
    config = json.loads(CONFIG.read_text())
    hooks = config.get("hooks", {}).get("scheduled", [])
    state = load_state()
    failed = 0
    for hook in hooks:
        if not hook.get("enabled", True):
            continue
        if not is_due(hook, state=state):
            continue
        name = hook["name"]
        print(f"[dispatch] 执行 {name} (skill={hook['skill']} action={hook['action']})")
        cmd = [
            sys.executable,
            str(ROOT / ".jcode" / "scripts" / f"{hook['skill']}.py"),
            hook["action"],
        ]
        result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
        ok = result.returncode == 0
        print(f"[dispatch] {name}: {'OK' if ok else f'FAILED (exit={result.returncode})'}")
        if not ok:
            print(result.stdout[-500:])
            failed += 1
        state[name] = time.time()
    if not dry_run:
        save_state(state)
    return failed


if __name__ == "__main__":
    sys.exit(dispatch("--dry-run" in sys.argv))

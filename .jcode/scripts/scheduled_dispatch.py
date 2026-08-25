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


def parse_cron(expr: str) -> tuple[set[int], set[int]]:
    """解析 '分 时 日 月 周' 中分/时字段，支持 *、数字、逗号、范围。返回 (分钟集, 小时集)。"""
    fields = expr.split()
    if len(fields) != 5:
        raise ValueError(f"bad cron: {expr}")

    def expand(field: str, low: int, high: int) -> set[int]:
        vals: set[int] = set()
        for part in field.split(","):
            if part == "*":
                vals.update(range(low, high + 1))
            elif "-" in part:
                a, b = part.split("-")
                vals.update(range(int(a), int(b) + 1))
            else:
                vals.add(int(part))
        return vals

    minutes = expand(fields[0], 0, 59)
    hours = expand(fields[1], 0, 23)
    return minutes, hours


def is_due(hook: dict, now: struct_time | None = None, state: dict[str, float] | None = None) -> bool:
    """判断 hook 是否到期：启用中、时间匹配 cron 且距上次执行超过安全间隔。"""
    if not hook.get("enabled", True):
        return False
    now = now or time.localtime()
    state = state or {}
    minutes, hours = parse_cron(hook["schedule"])
    if now.tm_min not in minutes or now.tm_hour not in hours:
        return False
    name = hook["name"]
    last = state.get(name, 0)
    # 同一天内已跑过则跳过（按 cron 精度，日级去重）
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

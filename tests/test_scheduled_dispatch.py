"""scheduled_dispatch 单元测试（N1：scheduled hooks 真实排程）。"""

from __future__ import annotations

import importlib.util
from pathlib import Path
from time import localtime, mktime, strptime, struct_time

import pytest

ROOT = Path(__file__).resolve().parent.parent
_spec = importlib.util.spec_from_file_location("scheduled_dispatch", ROOT / ".jcode/scripts/scheduled_dispatch.py")
assert _spec and _spec.loader
sd = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(sd)


def _ts(minute: int, hour: int) -> struct_time:
    return strptime(f"2026-08-25 {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")


class TestParseCron:
    def test_wildcard(self) -> None:
        minutes, hours = sd.parse_cron("* * * * *")
        assert len(minutes) == 60 and len(hours) == 24

    def test_fixed(self) -> None:
        minutes, hours = sd.parse_cron("0 9 * * 1")
        assert minutes == {0} and hours == {9}

    def test_range_and_list(self) -> None:
        minutes, hours = sd.parse_cron("0,30 9-11 * * *")
        assert minutes == {0, 30} and hours == {9, 10, 11}

    def test_bad_expr_raises(self) -> None:
        with pytest.raises(ValueError):
            sd.parse_cron("not a cron")


class TestIsDue:
    def test_due_when_matches_and_never_ran(self) -> None:
        hook = {"name": "w", "schedule": "0 9 * * *"}
        # 用当前真实时间的分钟/小时构造 cron，保证命中
        now = localtime()
        hook["schedule"] = f"{now.tm_min} {now.tm_hour} * * *"
        assert sd.is_due(hook, now=now, state={})

    def test_not_due_when_hour_mismatch(self) -> None:
        hook = {"name": "w", "schedule": "0 3 * * *"}  # 凌晨 3 点
        now = _ts(0, 12)
        assert not sd.is_due(hook, now=now, state={})

    def test_dedup_within_same_hour(self) -> None:
        hook = {"name": "w", "schedule": "0 9 * * *"}
        now = _ts(0, 9)
        last_run = mktime(strptime("2026-08-25 09:00:30", "%Y-%m-%d %H:%M:%S"))
        assert not sd.is_due(hook, now=now, state={"w": last_run})

    def test_disabled_never_due(self) -> None:
        hook = {"name": "w", "schedule": "* * * * *", "enabled": False}
        now = localtime()
        hook["schedule"] = f"{now.tm_min} {now.tm_hour} * * *"
        assert not sd.is_due(hook, now=now, state={})

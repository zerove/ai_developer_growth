"""测试 .jcode/scripts/scheduled_dispatch.py（此前仅 57%，为 .jcode/scripts 最低）。

该脚本由 systemd timer 每小时调用，读取 hooks.json 的 scheduled 触发器并
执行到期任务。**它决定定期治理任务的真实执行频率**，判错会让"每周一次"
的审计变成每天一次。

本轮补测试时发现并修复的真实缺陷（见 TestScheduleFieldsAreEvaluated）：
parse_cron 只展开分/时两个字段，日/月/周 split 进 fields 后从未求值。
hooks.json 里 5 条 `0 9 * * 1`（每周一）实际每天触发、2 条 `0 9 1 * *`
（每月 1 日）实际每天触发。

隔离要求：STATE 指向 tmp_path，subprocess.run 打桩，禁止真实执行任务与
写入 .jcode/.scheduled-last-run.json。
"""

from __future__ import annotations

import importlib.util
import json
import sys
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = ROOT / ".jcode" / "scripts"


@pytest.fixture
def sd(tmp_path: Path):
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location("jcode_sched_dispatch", _SCRIPTS / "scheduled_dispatch.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    mod.STATE = tmp_path / ".scheduled-last-run.json"  # 绝不能写真实状态文件
    return mod


def at(mo: int, day: int, hour: int, minute: int = 0) -> time.struct_time:
    return time.strptime(f"2026-{mo:02d}-{day:02d} {hour:02d}:{minute:02d}:00", "%Y-%m-%d %H:%M:%S")


# ── parse_cron ──────────────────────────────────────────────────────


class TestParseCron:
    def test_all_five_fields_returned(self, sd) -> None:
        assert len(sd.parse_cron("0 9 1 * 1")) == 5

    def test_wildcards(self, sd) -> None:
        m, h, d, mo, w = sd.parse_cron("* * * * *")
        assert m == set(range(60)) and h == set(range(24))
        assert d == set(range(1, 32)) and mo == set(range(1, 13))
        assert w == set(range(0, 7)), "周日 0/7 归一后应为 7 个取值"

    def test_numbers_and_lists(self, sd) -> None:
        m, h, *_ = sd.parse_cron("5,10 3 * * *")
        assert m == {5, 10} and h == {3}

    def test_ranges(self, sd) -> None:
        m, h, *_ = sd.parse_cron("0-3 9-11 * * *")
        assert m == {0, 1, 2, 3} and h == {9, 10, 11}

    def test_sunday_is_0_and_7(self, sd) -> None:
        """cron 约定 0 与 7 均为周日，须归一到同一个值。"""
        assert sd.parse_cron("0 9 * * 7")[4] == sd.parse_cron("0 9 * * 0")[4] == {0}

    @pytest.mark.parametrize("expr", ["0 9 * *", "0 9 * * * *", ""])
    def test_bad_field_count_raises(self, sd, expr: str) -> None:
        with pytest.raises(ValueError):
            sd.parse_cron(expr)

    @pytest.mark.parametrize(
        "expr", ["70 9 * * *", "0 24 * * *", "0 9 32 * *", "0 9 0 * *", "0 9 * 13 *", "0 9 * 0 *", "0 9 * * 8"]
    )
    def test_out_of_range_rejected(self, sd, expr: str) -> None:
        """越界值会永远不匹配 —— 定时任务静默从不执行，必须显式拒绝。"""
        with pytest.raises(ValueError, match="out of range"):
            sd.parse_cron(expr)

    def test_inverted_range_rejected(self, sd) -> None:
        with pytest.raises(ValueError):
            sd.parse_cron("10-5 * * * *")

    def test_hooks_json_schedules_all_parse(self, sd) -> None:
        """仓库真实配置必须全部可解析。"""
        hooks = json.loads((ROOT / ".jcode" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["scheduled"]
        assert hooks, "hooks.json 无 scheduled 触发器"
        for h in hooks:
            sd.parse_cron(h["schedule"])  # 不抛异常即通过


# ── 星期换算 ────────────────────────────────────────────────────────


class TestWeekdayConversion:
    def test_monday(self, sd) -> None:
        assert sd._py_weekday_to_cron(0) == 1

    def test_sunday(self, sd) -> None:
        assert sd._py_weekday_to_cron(6) == 0


# ── is_due：日/月/周字段必须真正生效（本轮修复核心） ────────────────


class TestScheduleFieldsAreEvaluated:
    def test_weekly_hook_only_fires_on_that_weekday(self, sd) -> None:
        """回归防护：早前 `0 9 * * 1` 每天触发。"""
        hook = {"name": "w", "schedule": "0 9 * * 1"}
        assert sd.is_due(hook, now=at(10, 5, 9), state={}) is True  # 2026-10-05 是周一
        assert sd.is_due(hook, now=at(10, 6, 9), state={}) is False
        assert sd.is_due(hook, now=at(10, 7, 9), state={}) is False

    def test_monthly_hook_only_fires_on_that_day(self, sd) -> None:
        """回归防护：早前 `0 9 1 * *` 每天触发。"""
        hook = {"name": "m", "schedule": "0 9 1 * *"}
        assert sd.is_due(hook, now=at(10, 1, 9), state={}) is True
        assert sd.is_due(hook, now=at(10, 2, 9), state={}) is False
        assert sd.is_due(hook, now=at(10, 15, 9), state={}) is False

    def test_day_and_week_restricted_is_or(self, sd) -> None:
        """日与周都受限取"或"（cron 标准语义）。"""
        hook = {"name": "x", "schedule": "0 9 15 * 1"}
        assert sd.is_due(hook, now=at(10, 5, 9), state={}) is True  # 周一
        assert sd.is_due(hook, now=at(10, 15, 9), state={}) is True  # 15 日
        assert sd.is_due(hook, now=at(10, 7, 9), state={}) is False  # 周三且非 15 日

    def test_month_restriction_enforced(self, sd) -> None:
        hook = {"name": "m2", "schedule": "0 9 1 10 *"}
        assert sd.is_due(hook, now=at(10, 1, 9), state={}) is True
        assert sd.is_due(hook, now=at(11, 1, 9), state={}) is False

    def test_wrong_hour_not_due(self, sd) -> None:
        assert sd.is_due({"name": "w", "schedule": "0 9 * * 1"}, now=at(10, 5, 10), state={}) is False

    def test_wrong_minute_not_due(self, sd) -> None:
        assert sd.is_due({"name": "w", "schedule": "0 9 * * 1"}, now=at(10, 5, 9, 30), state={}) is False

    def test_hourly_hook_fires_every_hour(self, sd) -> None:
        """去重必须是小时级；按日去重会把每小时 hook 压成每天一次。"""
        hook = {"name": "h", "schedule": "0 * * * *"}
        for h in (9, 10, 11):
            assert sd.is_due(hook, now=at(10, 5, h), state={}) is True, f"{h} 时应触发"

    def test_disabled_never_due(self, sd) -> None:
        hook = {"name": "w", "schedule": "0 9 * * 1", "enabled": False}
        assert sd.is_due(hook, now=at(10, 5, 9), state={}) is False


# ── 状态读写（隔离到 tmp_path） ─────────────────────────────────────


class TestState:
    def test_missing_state_is_empty(self, sd) -> None:
        assert sd.load_state() == {}

    def test_roundtrip(self, sd) -> None:
        sd.save_state({"a": 100.5})
        assert sd.load_state() == {"a": 100.5}

    def test_corrupt_state_degrades_to_empty(self, sd) -> None:
        """损坏的状态文件必须退化为空，不得抛异常中断调度。"""
        sd.STATE.write_text("{ not json", encoding="utf-8")
        assert sd.load_state() == {}

    def test_same_hour_is_deduped(self, sd) -> None:
        hook = {"name": "w", "schedule": "0 9 * * 1"}
        now = at(10, 5, 9, 30)
        assert sd.is_due(hook, now=now, state={"w": time.mktime(now)}) is False

    def test_next_hour_runs_again(self, sd) -> None:
        hook = {"name": "h", "schedule": "0 * * * *"}
        last = time.mktime(at(10, 5, 9))
        assert sd.is_due(hook, now=at(10, 5, 10), state={"h": last}) is True


# ── dispatch（打桩子进程） ──────────────────────────────────────────


class TestDispatch:
    def _config(self, sd, tmp_path: Path, hooks: list) -> None:
        sd.CONFIG = tmp_path / "hooks.json"
        sd.CONFIG.write_text(json.dumps({"hooks": {"scheduled": hooks}}), encoding="utf-8")

    def test_dry_run_does_not_persist_state(self, sd, tmp_path: Path) -> None:
        self._config(sd, tmp_path, [{"name": "a", "schedule": "* * * * *", "skill": "x", "action": "y"}])
        with patch.object(sd, "is_due", return_value=True), patch.object(sd.subprocess, "run") as run:
            run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            assert sd.dispatch(dry_run=True) == 0
        run.assert_called_once()
        assert not sd.STATE.exists(), "dry-run 不得写状态文件"

    def test_failure_counted(self, sd, tmp_path: Path) -> None:
        self._config(
            sd,
            tmp_path,
            [
                {"name": "a", "schedule": "* * * * *", "skill": "x", "action": "y"},
                {"name": "b", "schedule": "* * * * *", "skill": "x", "action": "z"},
            ],
        )
        with patch.object(sd, "is_due", return_value=True), patch.object(sd.subprocess, "run") as run:
            run.side_effect = [
                MagicMock(returncode=0, stdout="", stderr=""),
                MagicMock(returncode=3, stdout="boom", stderr=""),
            ]
            assert sd.dispatch() == 1

    def test_state_persisted_after_real_run(self, sd, tmp_path: Path) -> None:
        self._config(sd, tmp_path, [{"name": "a", "schedule": "* * * * *", "skill": "x", "action": "y"}])
        with patch.object(sd, "is_due", return_value=True), patch.object(sd.subprocess, "run") as run:
            run.return_value = MagicMock(returncode=0, stdout="", stderr="")
            sd.dispatch()
        assert "a" in sd.load_state()

    def test_disabled_hook_skipped(self, sd, tmp_path: Path) -> None:
        self._config(
            sd,
            tmp_path,
            [{"name": "a", "schedule": "* * * * *", "skill": "x", "action": "y", "enabled": False}],
        )
        with patch.object(sd.subprocess, "run") as run:
            assert sd.dispatch() == 0
        run.assert_not_called()

    def test_real_config_dispatch_is_parseable(self, sd) -> None:
        """真实 hooks.json 的每条 scheduled 都必须能被 parse_cron 接受。"""
        hooks = json.loads((ROOT / ".jcode" / "hooks.json").read_text(encoding="utf-8"))["hooks"]["scheduled"]
        for h in hooks:
            assert set(h) >= {"name", "schedule", "skill", "action"}, f"缺少必要字段: {h}"
            sd.parse_cron(h["schedule"])

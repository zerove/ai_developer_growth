"""cmd_pattern_learner 单元测试。

该模块是 PatternLearner 的 CLI 薄封装, 此前无直接覆盖(实测 14.3%)。
重点覆盖: json/非 json 两条输出分支、min_occurrences 透传、以及
模式字典字段缺失时的 .get 兜底。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tools.scripts.adg_cli.commands.cmd import cmd_pattern_learner as mod


def _args(**kw) -> argparse.Namespace:
    base = {"path": ".", "json": False, "min_occurrences": 3}
    base.update(kw)
    return argparse.Namespace(**base)


@pytest.fixture
def learner():
    """替换 PatternLearner, 返回 (mock 类, 捕获的实例)。"""
    with patch("tools.scripts.rules_engine.pattern_learner.PatternLearner") as cls:
        inst = cls.return_value
        inst.learn_from_directory.return_value = []
        yield cls, inst


class TestReturnCode:
    def test_returns_zero(self, learner, capsys) -> None:
        _, inst = learner
        assert mod.cmd_pattern_learner(_args()) == 0
        capsys.readouterr()

    def test_uses_resolved_path(self, learner, tmp_path, capsys) -> None:
        _, inst = learner
        mod.cmd_pattern_learner(_args(path=str(tmp_path)))
        called = inst.learn_from_directory.call_args[0][0]
        assert isinstance(called, Path)
        assert called.is_absolute()
        capsys.readouterr()


class TestMinOccurrences:
    def test_default_is_three(self, learner, capsys) -> None:
        _, inst = learner
        mod.cmd_pattern_learner(_args())
        assert inst.MIN_OCCURRENCES == 3
        capsys.readouterr()

    def test_explicit_value_passed_through(self, learner, capsys) -> None:
        _, inst = learner
        mod.cmd_pattern_learner(_args(min_occurrences=7))
        assert inst.MIN_OCCURRENCES == 7
        capsys.readouterr()

    def test_missing_attribute_falls_back_to_three(self, learner, capsys) -> None:
        """args 无 min_occurrences 字段时不能崩 —— getattr 默认值在此生效。"""
        _, inst = learner
        args = argparse.Namespace(path=".", json=False)
        assert mod.cmd_pattern_learner(args) == 0
        assert inst.MIN_OCCURRENCES == 3
        capsys.readouterr()


class TestJsonOutput:
    def test_json_flag_emits_valid_json(self, learner, capsys) -> None:
        _, inst = learner
        inst.learn_from_directory.return_value = [{"type": "naming", "message": "m", "confidence": 0.9}]
        mod.cmd_pattern_learner(_args(json=True))
        payload = json.loads(capsys.readouterr().out)
        assert payload == [{"type": "naming", "message": "m", "confidence": 0.9}]

    def test_json_output_keeps_unicode(self, learner, capsys) -> None:
        _, inst = learner
        inst.learn_from_directory.return_value = [{"message": "中文建议"}]
        mod.cmd_pattern_learner(_args(json=True))
        assert "中文建议" in capsys.readouterr().out


class TestHumanOutput:
    def test_summary_line_reports_count(self, learner, capsys) -> None:
        _, inst = learner
        inst.learn_from_directory.return_value = [
            {"type": "naming", "message": "a", "frequency": 3, "confidence": 0.8, "suggested_action": "do-x"},
        ]
        mod.cmd_pattern_learner(_args())
        out = capsys.readouterr().out
        assert "发现 1 个模式和建议" in out
        assert "[naming] a" in out
        assert "80%" in out

    def test_empty_result_still_summarizes(self, learner, capsys) -> None:
        _, inst = learner
        inst.learn_from_directory.return_value = []
        mod.cmd_pattern_learner(_args())
        assert "发现 0 个模式和建议" in capsys.readouterr().out

    def test_zero_confidence_entries_are_omitted(self, learner, capsys) -> None:
        """freq 与 conf 均为 0 的条目不应打印 —— 否则刷屏无信息量的模式。"""
        _, inst = learner
        inst.learn_from_directory.return_value = [
            {"type": "x", "message": "silent", "frequency": 0, "confidence": 0, "suggested_action": ""},
            {"type": "y", "message": "shown", "frequency": 2, "confidence": 0.5, "suggested_action": "z"},
        ]
        mod.cmd_pattern_learner(_args())
        out = capsys.readouterr().out
        assert "silent" not in out
        assert "shown" in out

    def test_missing_optional_keys_do_not_crash(self, learner, capsys) -> None:
        """缺 type/message/frequency/confidence/suggested_action 时靠 .get 兜底。"""
        _, inst = learner
        inst.learn_from_directory.return_value = [{}]
        assert mod.cmd_pattern_learner(_args()) == 0
        assert "发现 1 个模式和建议" in capsys.readouterr().out

    def test_confidence_only_entry_is_printed(self, learner, capsys) -> None:
        _, inst = learner
        inst.learn_from_directory.return_value = [{"message": "only-conf", "confidence": 0.42}]
        mod.cmd_pattern_learner(_args())
        out = capsys.readouterr().out
        assert "only-conf" in out
        assert "42%" in out


class TestLearnerFailurePropagates:
    def test_learner_exception_is_not_swallowed(self, learner, capsys) -> None:
        """学习器抛错必须向上传播 —— 静默返回 0 会把"没学到"伪装成"学完了"。"""
        _, inst = learner
        inst.learn_from_directory.side_effect = RuntimeError("boom")
        with pytest.raises(RuntimeError, match="boom"):
            mod.cmd_pattern_learner(_args())
        capsys.readouterr()

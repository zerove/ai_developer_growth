"""补测 .jcode/scripts/self-correction-loop.py 的 CLI 与报告路径。

同目录已有 tests/test_self_correction_shim.py 覆盖策略链接线（15 个测试），
本文件专补其未覆盖部分：argparse 子命令接线、main() 分派、_report 写盘。

本轮补测时发现并修复的真实缺陷（见 TestReportCreatesParentDirs）：
`--output-json reports/run.json` 在父目录不存在时抛 FileNotFoundError 崩溃，
而这是最常见的写法之一。

隔离要求：一切写盘指向 tmp_path；CorrectionLoop / run_tests 必须打桩，
不得真实执行测试套件。
"""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = ROOT / ".jcode" / "scripts"


@pytest.fixture(scope="module")
def scl():
    if str(_SCRIPTS) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS))
    spec = importlib.util.spec_from_file_location("jcode_self_correction", _SCRIPTS / "self-correction-loop.py")
    assert spec is not None and spec.loader is not None
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _target(tmp_path: Path) -> str:
    """run/validate 都先做存在性检查，测试必须提供真实文件。"""
    f = tmp_path / "t.py"
    f.write_text("def f():\n    return 1\n", encoding="utf-8")
    return str(f)


@pytest.fixture
def result(scl):
    from results import CorrectionResult, CorrectionStatus

    return CorrectionResult(
        status=CorrectionStatus.SUCCESS, attempt=2, strategy="pattern", message="已修正", duration_s=1.5
    )


# ── _as_dict / _report ──────────────────────────────────────────────


class TestReportOutput:
    def test_as_dict_serialises_status_to_string(self, scl, result) -> None:
        """status 是 Enum，必须转成字符串才能 JSON 序列化。"""
        from results import CorrectionStatus

        data = scl._as_dict(result)
        # CorrectionStatus 用 auto()，.value 是 int；关键是不能残留 Enum
        # （Enum 不可 JSON 序列化），换成可序列化基元即可。
        assert not isinstance(data["status"], CorrectionStatus)
        assert data["status"] == result.status.value
        json.dumps(data)  # 不得抛 TypeError

    def test_report_without_json_path_writes_nothing(self, scl, result, tmp_path: Path) -> None:
        before = set(tmp_path.iterdir())
        scl._report(result, [result], None)
        assert set(tmp_path.iterdir()) == before

    def test_report_writes_valid_json(self, scl, result, tmp_path: Path) -> None:
        out = tmp_path / "r.json"
        scl._report(result, [result], str(out))
        payload = json.loads(out.read_text(encoding="utf-8"))
        assert payload["success"] is True
        assert payload["final_result"]["status"] == result.status.value
        assert len(payload["history"]) == 1

    def test_report_creates_parent_dirs(self, scl, result, tmp_path: Path) -> None:
        """回归防护：早前父目录不存在时抛 FileNotFoundError。"""
        out = tmp_path / "deep" / "nested" / "r.json"
        scl._report(result, [result], str(out))
        assert out.exists()
        json.loads(out.read_text(encoding="utf-8"))

    def test_report_handles_failure_result(self, scl, tmp_path: Path) -> None:
        from results import CorrectionResult, CorrectionStatus

        bad = CorrectionResult(
            status=CorrectionStatus.FAILURE, attempt=3, strategy="retry", message="仍失败", duration_s=0.2
        )
        out = tmp_path / "bad.json"
        scl._report(bad, [bad], str(out))
        assert json.loads(out.read_text(encoding="utf-8"))["success"] is False

    def test_report_with_empty_history(self, scl, result, tmp_path: Path) -> None:
        out = tmp_path / "empty.json"
        scl._report(result, [], str(out))
        assert json.loads(out.read_text(encoding="utf-8"))["history"] == []


# ── run_correction ──────────────────────────────────────────────────


class TestRunCorrection:
    def test_missing_target_returns_one(self, scl, tmp_path: Path) -> None:
        assert scl.run_correction(str(tmp_path / "nope.py")) == 1

    def test_success_returns_zero(self, scl, result, tmp_path: Path) -> None:
        loop = MagicMock()
        loop.run.return_value = result
        loop.history = [result]
        with patch.object(scl, "CorrectionLoop", return_value=loop):
            assert scl.run_correction(_target(tmp_path)) == 0

    def test_failure_returns_one(self, scl, tmp_path: Path) -> None:
        from results import CorrectionResult, CorrectionStatus

        bad = CorrectionResult(
            status=CorrectionStatus.FAILURE, attempt=3, strategy="retry", message="x", duration_s=0.1
        )
        loop = MagicMock()
        loop.run.return_value = bad
        loop.history = [bad]
        with patch.object(scl, "CorrectionLoop", return_value=loop):
            assert scl.run_correction(_target(tmp_path)) == 1

    def test_strategy_flags_forwarded_to_registry(self, scl, tmp_path: Path) -> None:
        """--no-llm / --no-pattern 必须真正传到 get_registry。"""
        loop = MagicMock()
        loop.run.return_value = MagicMock(is_success=True, attempt=1, strategy="retry", message="", history=[])
        with patch.object(scl, "CorrectionLoop", return_value=loop), patch.object(scl, "get_registry") as reg:
            reg.return_value = []
            scl.run_correction(_target(tmp_path), enable_retry=False, enable_pattern=True, enable_llm=False)
        kwargs = reg.call_args.kwargs
        assert kwargs["enable_retry"] is False
        assert kwargs["enable_llm"] is False
        assert kwargs["enable_pattern"] is True


# ── validate_correction ─────────────────────────────────────────────


class TestValidateCorrection:
    def test_missing_target_returns_one(self, scl, tmp_path: Path) -> None:
        assert scl.validate_correction(str(tmp_path / "nope.py")) == 1

    def test_passing_tests_returns_zero(self, scl, tmp_path: Path) -> None:
        with patch.object(scl, "run_tests", return_value=(0, "ok", "")):
            assert scl.validate_correction(_target(tmp_path)) == 0

    def test_failing_tests_returns_one(self, scl, tmp_path: Path) -> None:
        with patch.object(scl, "run_tests", return_value=(1, "out", "err")):
            assert scl.validate_correction(_target(tmp_path)) == 1

    def test_timeout_forwarded(self, scl, tmp_path: Path) -> None:
        with patch.object(scl, "run_tests", return_value=(0, "", "")) as rt:
            scl.validate_correction(_target(tmp_path), timeout=42)
        assert rt.call_args.kwargs["timeout"] == 42

    def test_runner_forwarded(self, scl, tmp_path: Path) -> None:
        with patch.object(scl, "run_tests", return_value=(0, "", "")) as rt:
            scl.validate_correction(_target(tmp_path), runner="pytest")
        assert rt.call_args.args[1] == "pytest"


# ── main() 分派与 argparse 接线 ─────────────────────────────────────


class TestMainDispatch:
    def _run(self, scl, *argv: str) -> int:
        with patch.object(sys, "argv", ["self-correction-loop.py", *argv]):
            with pytest.raises(SystemExit) as exc:
                scl.main()
        return exc.value.code or 0

    def test_no_command_exits(self, scl) -> None:
        assert self._run(scl) == 2

    def test_unknown_command_exits(self, scl) -> None:
        assert self._run(scl, "bogus") == 2

    def test_run_subcommand_routes_to_run_correction(self, scl) -> None:
        with patch.object(scl, "run_correction", return_value=0) as rc:
            assert self._run(scl, "run", "--target", "t.py") == 0
        assert rc.call_args.kwargs["target_file"] == "t.py"

    def test_validate_subcommand_routes_to_validate(self, scl) -> None:
        with patch.object(scl, "validate_correction", return_value=0) as vc:
            assert self._run(scl, "validate", "--target", "t.py") == 0
        assert vc.call_args.kwargs["target_file"] == "t.py"

    def test_run_target_is_required(self, scl) -> None:
        assert self._run(scl, "run") == 2

    @pytest.mark.parametrize(
        ("flag", "kwarg"),
        [("--no-retry", "enable_retry"), ("--no-pattern", "enable_pattern"), ("--no-llm", "enable_llm")],
    )
    def test_no_flags_invert_to_false(self, scl, flag: str, kwarg: str) -> None:
        with patch.object(scl, "run_correction", return_value=0) as rc:
            self._run(scl, "run", "--target", "t.py", flag)
        assert rc.call_args.kwargs[kwarg] is False

    def test_defaults_without_disable_flags(self, scl) -> None:
        with patch.object(scl, "run_correction", return_value=0) as rc:
            self._run(scl, "run", "--target", "t.py")
        kwargs = rc.call_args.kwargs
        assert kwargs["enable_retry"] is True
        assert kwargs["enable_pattern"] is True
        assert kwargs["enable_llm"] is True
        assert kwargs["max_attempts"] == 3
        assert kwargs["runner"] == "unittest"

    @pytest.mark.parametrize("runner", ["unittest", "pytest"])
    def test_both_runners_accepted(self, scl, runner: str) -> None:
        """CLI 声明支持两种 runner，底层 run_tests 也须支持 pytest。"""
        with patch.object(scl, "run_correction", return_value=0) as rc:
            self._run(scl, "run", "--target", "t.py", "--runner", runner)
        assert rc.call_args.kwargs["runner"] == runner

    def test_invalid_runner_rejected(self, scl) -> None:
        assert self._run(scl, "run", "--target", "t.py", "--runner", "nose") == 2

    def test_max_attempts_and_llm_model_forwarded(self, scl) -> None:
        with patch.object(scl, "run_correction", return_value=0) as rc:
            self._run(scl, "run", "--target", "t.py", "--max-attempts", "7", "--llm-model", "gpt-x")
        kwargs = rc.call_args.kwargs
        assert kwargs["max_attempts"] == 7
        assert kwargs["llm_model"] == "gpt-x"

    def test_output_json_forwarded(self, scl) -> None:
        with patch.object(scl, "run_correction", return_value=0) as rc:
            self._run(scl, "run", "--target", "t.py", "--output-json", "o.json")
        assert rc.call_args.kwargs["output_json"] == "o.json"

    def test_validate_timeout_forwarded(self, scl) -> None:
        with patch.object(scl, "validate_correction", return_value=0) as vc:
            self._run(scl, "validate", "--target", "t.py", "--timeout", "11")
        assert vc.call_args.kwargs["timeout"] == 11

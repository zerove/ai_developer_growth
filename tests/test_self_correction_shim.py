"""测试 .jcode/scripts/self-correction-loop.py（skill 入口 shim）。

该脚本本身零测试覆盖，但它被 hooks.json 的 on_pr/self-correction 直接调用，
且实现已改为复用 examples/self-correction-loop/src，因此这里锁定：
1. 契约：子命令与参数名不变（hook 依赖 `validate --target X --tests Y`）
2. 复用：确实加载 examples 包，而不是自带一份实现
3. JSON 报告：CorrectionStatus 枚举必须可序列化（曾因 asdict() 直接丢枚举而崩）
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

_SCRIPTS_DIR = Path(__file__).resolve().parent.parent / ".jcode" / "scripts"
_EXAMPLE_SRC = Path(__file__).resolve().parent.parent / "examples" / "self-correction-loop" / "src"


def _load_shim():
    if str(_SCRIPTS_DIR) not in sys.path:
        sys.path.insert(0, str(_SCRIPTS_DIR))
    spec = importlib.util.spec_from_file_location("jcode_self_correction", _SCRIPTS_DIR / "self-correction-loop.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def shim():
    return _load_shim()


def _success_status():
    from results import CorrectionStatus

    return CorrectionStatus.SUCCESS


class TestReusesExamplePackage:
    def test_loads_shared_implementation(self, shim) -> None:
        """实现必须来自 examples 包，shim 只负责 CLI 与报告。"""
        assert shim.CorrectionLoop.__module__ == "runner"
        assert Path(shim.EXAMPLE_SRC).resolve() == _EXAMPLE_SRC.resolve()
        assert str(_EXAMPLE_SRC) in shim.sys.path

    def test_does_not_redefine_core_types(self, shim) -> None:
        """shim 不得自带 CorrectionLoop / get_registry 等实现。"""
        assert not hasattr(shim, "Pattern")
        assert not hasattr(shim, "StrategyRegistry")
        assert not hasattr(shim, "PatternStrategy")


class TestAsDictSerialization:
    def test_status_enum_becomes_serializable(self, shim) -> None:
        """Regression: asdict() 不会转换枚举，直接 json.dumps 会抛 TypeError。"""
        from enum import Enum

        result = shim.CorrectionResult(
            status=_success_status(),
            attempt=1,
            strategy="pattern",
            message="ok",
        )
        payload = shim._as_dict(result)
        json.dumps(payload)  # 不得抛异常
        assert not isinstance(payload["status"], Enum)
        assert payload["status"] == _success_status().value

    def test_asdict_keeps_other_fields(self, shim) -> None:
        result = shim.CorrectionResult(
            status=_success_status(),
            attempt=3,
            strategy="llm",
            message="done",
            duration_s=1.5,
        )
        payload = shim._as_dict(result)
        assert payload["attempt"] == 3
        assert payload["strategy"] == "llm"
        assert payload["duration_s"] == 1.5


class TestValidateCorrection:
    def test_missing_target_exits_nonzero(self, shim, tmp_path: Path) -> None:
        assert shim.validate_correction(str(tmp_path / "nope.py")) == 1

    def test_passing_tests_returns_zero(self, shim, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("x = 1\n", encoding="utf-8")
        with patch.object(shim, "run_tests", return_value=(0, "OK", "")):
            assert shim.validate_correction(str(target)) == 0

    def test_failing_tests_returns_nonzero(self, shim, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("x = 1\n", encoding="utf-8")
        with patch.object(shim, "run_tests", return_value=(1, "FAIL", "boom")):
            assert shim.validate_correction(str(target)) == 1

    def test_timeout_is_reported_not_raised(self, shim, tmp_path: Path) -> None:
        """run_tests 内部已吞掉 TimeoutExpired 并返回非零，不应向上抛。"""
        target = tmp_path / "code.py"
        target.write_text("x = 1\n", encoding="utf-8")
        with patch.object(shim, "run_tests", return_value=(1, "", "测试运行超时 (>300s)")):
            assert shim.validate_correction(str(target)) == 1


class TestRunCorrection:
    def test_missing_target_exits_nonzero(self, shim, tmp_path: Path) -> None:
        assert shim.run_correction(str(tmp_path / "nope.py")) == 1

    def test_success_writes_json_report(self, shim, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("x = 1\n", encoding="utf-8")
        out = tmp_path / "report.json"

        from results import CorrectionStatus, success_result

        ok = success_result(attempt=1, strategy="pattern", file_path=str(target), original_code="")
        assert ok.status == CorrectionStatus.SUCCESS
        loop = type("L", (), {"history": [ok], "run": lambda self: ok})()
        with patch.object(shim, "CorrectionLoop", lambda **kw: loop):
            assert shim.run_correction(str(target), output_json=str(out)) == 0
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["success"] is True
        assert data["final_result"]["status"] == ok.status.value
        assert len(data["history"]) == 1

    def test_failure_returns_nonzero(self, shim, tmp_path: Path) -> None:
        target = tmp_path / "code.py"
        target.write_text("x = 1\n", encoding="utf-8")

        from results import failure_result

        bad = failure_result(attempt=2, strategy="none", message="nope", file_path=str(target))
        loop = type("L", (), {"history": [bad], "run": lambda self: bad})()
        with patch.object(shim, "CorrectionLoop", lambda **kw: loop):
            assert shim.run_correction(str(target)) == 1


class TestCliContract:
    """hooks.json 依赖 `validate --target . --tests tests`，参数名不能变。"""

    def _run(self, shim, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(_SCRIPTS_DIR / "self-correction-loop.py"), *args],
            capture_output=True,
            text=True,
            check=False,
            timeout=120,
        )

    def test_help_lists_both_subcommands(self, shim) -> None:
        out = self._run(shim, "--help")
        assert out.returncode == 0
        assert "run" in out.stdout
        assert "validate" in out.stdout

    def test_validate_accepts_target_and_tests(self, shim) -> None:
        out = self._run(shim, "validate", "--help")
        assert out.returncode == 0
        assert "--target" in out.stdout
        assert "--tests" in out.stdout
        assert "--timeout" in out.stdout

    def test_run_accepts_strategy_toggles(self, shim) -> None:
        out = self._run(shim, "run", "--help")
        assert out.returncode == 0
        for flag in ("--no-retry", "--no-pattern", "--no-llm", "--output-json", "--max-attempts"):
            assert flag in out.stdout

    def test_missing_required_target_is_rejected(self, shim) -> None:
        out = self._run(shim, "validate")
        assert out.returncode != 0

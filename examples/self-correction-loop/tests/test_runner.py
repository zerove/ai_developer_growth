"""Unit tests for src.runner (test runner + CorrectionLoop)."""

from __future__ import annotations

import subprocess as _subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import runner as _runner_mod
from errors import FixError
from results import CorrectionResult
from runner import CorrectionLoop, run_tests
from strategies.base import Strategy, StrategyRegistry

# ── run_tests helper ───────────────────────────────────────────────────────


class TestRunTests:
    @patch.object(_subprocess, "run")
    def test_unittest_command(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="OK", stderr="")
        rc, out, err = run_tests("tests", "unittest")
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert "unittest" in " ".join(cmd)

    @patch.object(_subprocess, "run")
    def test_pytest_command(self, mock_run: MagicMock) -> None:
        mock_run.return_value = MagicMock(returncode=0, stdout="1 passed", stderr="")
        rc, out, err = run_tests("tests", "pytest")
        assert rc == 0
        cmd = mock_run.call_args[0][0]
        assert "pytest" in " ".join(cmd)


# ── CorrectionLoop ─────────────────────────────────────────────────────────


class _AlwaysPass(Strategy):
    """Test double: always returns the original code."""

    @property
    def name(self) -> str:
        return "always_pass"

    def fix(self, code: str, error_output: str, file_path: str | None = None) -> str:
        return code


class _NeverFixes(Strategy):
    """Test double: always returns None."""

    @property
    def name(self) -> str:
        return "never_fixes"

    def fix(self, code: str, error_output: str, file_path: str | None = None) -> None:
        return None


class TestCorrectionLoop:
    def _make_loop(
        self,
        tmp_path: Path,
        strategies: list[Strategy],
        max_attempts: int = 3,
    ) -> CorrectionLoop:
        target = tmp_path / "code.py"
        target.write_text("x = 1")
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        registry = StrategyRegistry(strategies)
        return CorrectionLoop(
            target_file=target,
            test_dir=str(test_dir),
            max_attempts=max_attempts,
            runner="unittest",
            registry=registry,
        )

    @patch.object(_runner_mod, "run_tests", return_value=(0, "OK", ""))
    def test_immediate_pass(self, _mock: MagicMock, tmp_path: Path) -> None:
        loop = self._make_loop(tmp_path, [_AlwaysPass()])
        result = loop.run()
        assert result.is_success
        assert result.attempt == 1

    @patch.object(_runner_mod, "run_tests", return_value=(1, "FAIL", "err"))
    def test_all_strategies_fail(self, _mock: MagicMock, tmp_path: Path) -> None:
        loop = self._make_loop(tmp_path, [_NeverFixes()], max_attempts=2)
        result = loop.run()
        assert not result.is_success
        assert len(loop.history) == 2

    def test_target_not_found(self, tmp_path: Path) -> None:
        loop = CorrectionLoop(
            target_file=tmp_path / "nonexistent.py",
            test_dir=str(tmp_path),
        )
        # Should not raise – loop reads file only after test failure
        with patch.object(_runner_mod, "run_tests", return_value=(0, "OK", "")):
            result = loop.run()
            assert result.is_success

    @patch.object(_runner_mod, "run_tests", return_value=(1, "FAIL", "err"))
    @patch.object(_runner_mod, "_write_code", side_effect=FixError("perm denied"))
    def test_write_failure(
        self, _write: MagicMock, _run: MagicMock, tmp_path: Path
    ) -> None:
        loop = self._make_loop(tmp_path, [_AlwaysPass()], max_attempts=1)
        result = loop.run()
        assert not result.is_success
        assert "perm denied" in result.message

    def test_history_populated(self, tmp_path: Path) -> None:
        loop = self._make_loop(tmp_path, [_NeverFixes()], max_attempts=2)
        with patch.object(_runner_mod, "run_tests", return_value=(1, "FAIL", "err")):
            loop.run()
            assert len(loop.history) == 2
            assert all(isinstance(r, CorrectionResult) for r in loop.history)

    def test_callback_invoked(self, tmp_path: Path) -> None:
        callback = MagicMock()
        loop = self._make_loop(tmp_path, [_NeverFixes()], max_attempts=1)
        loop._on_attempt = callback
        with patch.object(_runner_mod, "run_tests", return_value=(1, "FAIL", "err")):
            loop.run()
            assert callback.call_count == 1

    @patch.object(_runner_mod, "_write_code")
    @patch.object(_runner_mod, "run_tests")
    def test_strategy_chain_priority(
        self, mock_run: MagicMock, _write: MagicMock, tmp_path: Path
    ) -> None:
        """First strategy in the chain wins."""
        mock_run.side_effect = [
            (1, "FAIL", "err"),
            (0, "OK", ""),
        ]

        class A(Strategy):
            @property
            def name(self) -> str:
                return "first"

            def fix(self, code: str, error_output: str, file_path: str | None = None) -> str:
                return "fixed_by_a"

        class B(Strategy):
            @property
            def name(self) -> str:
                return "second"

            def fix(self, code: str, error_output: str, file_path: str | None = None) -> str:
                return "fixed_by_b"

        loop = self._make_loop(tmp_path, [A(), B()])
        result = loop.run()
        assert result.is_success
        assert result.strategy == "first"

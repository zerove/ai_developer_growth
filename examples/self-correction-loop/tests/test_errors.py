"""Unit tests for src.errors exception hierarchy."""

from __future__ import annotations

from errors import CorrectionError, FixError, StrategyError, TestFailure


class TestCorrectionError:
    """Base exception."""

    def test_is_exception(self) -> None:
        assert issubclass(CorrectionError, Exception)

    def test_message(self) -> None:
        exc = CorrectionError("boom")
        assert str(exc) == "boom"


class TestTestFailureExc:
    def test_basic(self) -> None:
        exc = TestFailure("tests failed", stdout="out", stderr="err", returncode=1)
        assert exc.stdout == "out"
        assert exc.stderr == "err"
        assert exc.returncode == 1
        assert exc.combined_output == "out\nerr"

    def test_combined_output_strips_whitespace(self) -> None:
        exc = TestFailure("f", stdout="", stderr="  \n")
        assert exc.combined_output == ""

    def test_defaults(self) -> None:
        exc = TestFailure("f")
        assert exc.stdout == ""
        assert exc.stderr == ""
        assert exc.returncode == 1

    def test_is_correction_error(self) -> None:
        assert issubclass(TestFailure, CorrectionError)


class TestFixError:
    def test_basic(self) -> None:
        exc = FixError("write failed", file_path="/tmp/x.py", reason="perm")
        assert exc.file_path == "/tmp/x.py"
        assert exc.reason == "perm"

    def test_is_correction_error(self) -> None:
        assert issubclass(FixError, CorrectionError)


class TestStrategyError:
    def test_basic(self) -> None:
        exc = StrategyError("no fix", strategy_name="pattern")
        assert exc.strategy_name == "pattern"

    def test_is_correction_error(self) -> None:
        assert issubclass(StrategyError, CorrectionError)

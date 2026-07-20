"""Unit tests for correction strategies."""

from __future__ import annotations

import textwrap
from unittest.mock import MagicMock, patch

import pytest

import runner as _runner_mod
from strategies.base import Strategy, StrategyKind, StrategyRegistry, get_registry
from strategies.llm import LLMStrategy, _mock_fix
from strategies.pattern import Pattern, PatternStrategy
from strategies.retry import RetryStrategy

# ── Strategy base / registry ────────────────────────────────────────────────


class TestStrategyRegistry:
    def test_empty_registry_returns_none(self) -> None:
        reg = StrategyRegistry()
        code, strat = reg.fix("x = 1", "AssertionError")
        assert code is None
        assert strat is None

    def test_first_winning_strategy_returns(self) -> None:
        class Fixed(Strategy):
            @property
            def name(self) -> str:
                return "fixed"

            def fix(self, code: str, error_output: str, file_path: str | None = None) -> str:
                return "FIXED"

        class Decline(Strategy):
            @property
            def name(self) -> str:
                return "decline"

            def fix(self, code: str, error_output: str, file_path: str | None = None) -> None:
                return None

        reg = StrategyRegistry([Decline(), Fixed()])
        code, strat = reg.fix("original", "err")
        assert code == "FIXED"
        assert strat.name == "fixed"

    def test_add_appends(self) -> None:
        reg = StrategyRegistry()

        class S(Strategy):
            @property
            def name(self) -> str:
                return "s"

            def fix(self, code: str, error_output: str, file_path: str | None = None) -> None:
                return None

        reg.add(S())
        assert len(reg.strategies) == 1

    def test_strategy_kind_registration(self) -> None:
        assert StrategyKind.RETRY in Strategy._registry
        assert StrategyKind.PATTERN in Strategy._registry
        assert StrategyKind.LLM in Strategy._registry

    def test_create_by_kind(self) -> None:
        s = Strategy.create(StrategyKind.RETRY)
        assert isinstance(s, RetryStrategy)

    def test_create_unknown_kind_raises(self) -> None:
        with pytest.raises(ValueError, match="No strategy registered"):
            Strategy.create(StrategyKind.CUSTOM)


class TestGetRegistry:
    def test_all_enabled(self) -> None:
        reg = get_registry()
        names = [s.name for s in reg.strategies]
        assert "retry" in names
        assert "pattern" in names
        assert "llm" in names

    def test_disable_retry(self) -> None:
        reg = get_registry(enable_retry=False)
        names = [s.name for s in reg.strategies]
        assert "retry" not in names

    def test_disable_all(self) -> None:
        reg = get_registry(enable_retry=False, enable_pattern=False, enable_llm=False)
        assert len(reg.strategies) == 0


# ── RetryStrategy ──────────────────────────────────────────────────────────


class TestRetryStrategy:
    def test_name(self) -> None:
        assert RetryStrategy().name == "retry"

    @patch.object(_runner_mod, "run_tests", return_value=(0, "OK", ""))
    def test_pass_through_on_green(self, _mock: MagicMock) -> None:
        s = RetryStrategy()
        result = s.fix("original code", "some error", file_path="src/x.py")
        assert result == "original code"

    @patch.object(_runner_mod, "run_tests", return_value=(1, "FAIL", "err"))
    def test_decline_on_still_failing(self, _mock: MagicMock) -> None:
        s = RetryStrategy()
        result = s.fix("code", "error", file_path="src/x.py")
        assert result is None

    def test_no_file_path_returns_none(self) -> None:
        s = RetryStrategy()
        result = s.fix("code", "error", file_path=None)
        assert result is None


# ── PatternStrategy ────────────────────────────────────────────────────────


class TestPattern:
    def test_matches_error(self) -> None:
        p = Pattern(
            name="test",
            error_regex=r"AssertionError",
            code_pattern=r"a",
            code_replacement=r"b",
        )
        assert p.matches_error("AssertionError at line 5") is True
        assert p.matches_error("TypeError: int") is False

    def test_apply_substitutes(self) -> None:
        p = Pattern(
            name="test",
            error_regex=r"err",
            code_pattern=r"old",
            code_replacement=r"new",
        )
        assert p.apply("old code old") == "new code new"

    def test_apply_no_match(self) -> None:
        p = Pattern(
            name="test",
            error_regex=r"err",
            code_pattern=r"zzz",
            code_replacement=r"new",
        )
        assert p.apply("nothing here") is None


class TestPatternStrategy:
    def test_name(self) -> None:
        assert PatternStrategy().name == "pattern"

    def test_builtin_patterns_loaded(self) -> None:
        s = PatternStrategy()
        assert len(s.patterns) >= 3

    def test_off_by_one_fix(self) -> None:
        code = textwrap.dedent("""\
            def calculate_sum(numbers):
                total = 0
                for i in range(len(numbers) - 1):
                    total += numbers[i]
                return total
        """)
        error = "AssertionError: 5 != 6"
        s = PatternStrategy()
        result = s.fix(code, error)
        assert result is not None
        assert "range(len(numbers))" in result
        assert "range(len(numbers) - 1)" not in result

    def test_no_matching_pattern_returns_none(self) -> None:
        code = "x = 1"
        error = "SomethingUnrelatedError"
        s = PatternStrategy()
        result = s.fix(code, error)
        assert result is None

    def test_custom_patterns(self) -> None:
        custom = [
            Pattern(
                name="custom",
                error_regex=r"CustomError",
                code_pattern=r"bad",
                code_replacement=r"good",
            )
        ]
        s = PatternStrategy(patterns=custom)
        result = s.fix("bad code", "CustomError occurred")
        assert result == "good code"


# ── LLMStrategy / Mock ────────────────────────────────────────────────────


class TestMockFix:
    def test_off_by_one_detected(self) -> None:
        code = "for i in range(len(nums) - 1):"
        error = "AssertionError expected len"
        result = _mock_fix(code, error)
        assert result is not None
        assert "range(len(nums))" in result

    def test_unrelated_error_returns_none(self) -> None:
        result = _mock_fix("x = 1", "SomeOtherError")
        assert result is None


class TestLLMStrategy:
    def test_name(self) -> None:
        assert LLMStrategy().name == "llm"

    def test_falls_back_to_mock_without_api_key(self) -> None:
        code = "for i in range(len(nums) - 1):"
        error = "AssertionError expected len"
        with patch.dict("os.environ", {}, clear=True):
            s = LLMStrategy()
            result = s.fix(code, error)
            # Should get the mock fix
            assert result is not None
            assert "range(len(nums))" in result

    def test_declines_when_mock_declines(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            s = LLMStrategy()
            result = s.fix("x = 1", "SomethingRandom")
            assert result is None

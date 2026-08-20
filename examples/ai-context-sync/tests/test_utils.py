"""Tests for utils module."""

from src.utils import retry_on_failure


class TestRetryOnFailure:
    def test_success_on_first_attempt(self):
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0, label="test")
        def succeed():
            nonlocal call_count
            call_count += 1
            return "ok"

        result = succeed()
        assert result == "ok"
        assert call_count == 1

    def test_success_after_retries(self):
        call_count = 0

        @retry_on_failure(max_retries=3, delay=0, label="test")
        def fail_then_succeed():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                return None
            return "ok"

        result = fail_then_succeed()
        assert result == "ok"
        assert call_count == 3

    def test_all_retries_exhausted(self):
        @retry_on_failure(max_retries=2, delay=0, label="test")
        def always_fail():
            return None

        result = always_fail()
        assert result is None

    def test_fallback_on_exhaustion(self):
        @retry_on_failure(max_retries=2, delay=0, fallback="fallback", label="test")
        def always_fail():
            return None

        result = always_fail()
        assert result == "fallback"

    def test_custom_validate(self):
        call_count = 0

        @retry_on_failure(
            max_retries=3,
            delay=0,
            validate=lambda x: x is not None and x > 0,
            label="test",
        )
        def negative_then_positive():
            nonlocal call_count
            call_count += 1
            return call_count - 2  # -1, 0, 1

        result = negative_then_positive()
        assert result == 1
        assert call_count == 3

    def test_preserves_function_name(self):
        @retry_on_failure(max_retries=1, delay=0)
        def my_function():
            """My docstring."""
            return 42

        assert my_function.__name__ == "my_function"
        assert my_function.__doc__ == "My docstring."

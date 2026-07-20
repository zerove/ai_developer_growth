"""Unit tests for src.results result types."""

from __future__ import annotations

from results import (
    CorrectionResult,
    CorrectionStatus,
    failure_result,
    success_result,
)


class TestCorrectionStatus:
    def test_values(self) -> None:
        assert CorrectionStatus.SUCCESS.value == 1
        assert CorrectionStatus.FAILURE.value == 2
        assert CorrectionStatus.SKIPPED.value == 3


class TestCorrectionResult:
    def test_success_result(self) -> None:
        r = success_result(
            attempt=1,
            strategy="pattern",
            file_path="src/foo.py",
            original_code="old",
            fixed_code="new",
        )
        assert r.is_success is True
        assert r.code_changed is True
        assert r.attempt == 1
        assert r.strategy == "pattern"

    def test_failure_result(self) -> None:
        r = failure_result(
            attempt=2,
            strategy="llm",
            message="no fix",
        )
        assert r.is_success is False
        assert r.code_changed is False

    def test_code_changed_when_same(self) -> None:
        r = success_result(
            attempt=1,
            strategy="retry",
            file_path="x.py",
            original_code="same",
            fixed_code="same",
        )
        assert r.code_changed is False

    def test_code_changed_when_none(self) -> None:
        r = CorrectionResult(
            status=CorrectionStatus.FAILURE,
            attempt=1,
        )
        assert r.code_changed is False

    def test_summary_format(self) -> None:
        r = success_result(
            attempt=1,
            strategy="pattern",
            file_path="x.py",
            original_code="a",
            fixed_code="b",
            test_output="pass",
        )
        s = r.summary()
        assert "Attempt 1" in s
        assert "SUCCESS" in s
        assert "pattern" in s

    def test_timestamp_populated(self) -> None:
        r = success_result(
            attempt=1, strategy="retry", file_path="x.py",
            original_code="", fixed_code="",
        )
        assert r.timestamp  # non-empty ISO string

    def test_frozen(self) -> None:
        r = success_result(
            attempt=1, strategy="x", file_path="x.py",
            original_code="", fixed_code="",
        )
        try:
            r.attempt = 99  # type: ignore[misc]
            raise AssertionError("Should be frozen")
        except AttributeError:
            pass

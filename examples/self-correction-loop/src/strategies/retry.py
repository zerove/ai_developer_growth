"""Retry strategy: re-run tests with adjusted parameters.

Some failures are transient (race conditions, resource contention).  This
strategy re-invokes the test suite once to confirm the failure is deterministic.
If the re-run passes, the fix is a no-op "pass-through"; otherwise it declines.
"""

from __future__ import annotations

from src.strategies.base import Strategy, StrategyKind


@Strategy.register(StrategyKind.RETRY)
class RetryStrategy(Strategy):
    """Re-run the failing tests to rule out transient failures.

    This strategy does **not** modify source code.  It simply re-invokes the
    test runner; if the re-run passes it returns the original code unchanged
    (a "pass-through" success).  Otherwise it returns ``None`` so the next
    strategy in the chain can try.
    """

    def __init__(self) -> None:
        self._runner: object | None = None  # injected lazily

    @property
    def name(self) -> str:
        return "retry"

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        """Re-run the test suite once.

        Returns the original *code* unchanged if the re-run passes, otherwise
        ``None``.
        """
        if file_path is None:
            return None

        from src.runner import run_tests  # noqa: PLC0415

        return_code, _stdout, _stderr = run_tests(test_dir=test_dir, runner=runner)
        if return_code == 0:
            return code  # pass-through – tests now pass
        return None  # still failing – let the next strategy handle it

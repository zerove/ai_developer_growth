"""Correction loop runner: orchestrate test → fix → verify cycles."""

from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

from errors import FixError
from results import CorrectionResult, failure_result, success_result
from strategies.base import StrategyRegistry, get_registry


def run_tests(
    test_dir: str = "tests",
    runner: str = "unittest",
) -> tuple[int, str, str]:
    """Execute the test suite and return ``(returncode, stdout, stderr)``."""
    if runner == "pytest":
        cmd = [sys.executable, "-m", "pytest", test_dir, "-q"]
    else:
        cmd = [sys.executable, "-m", "unittest", "discover", test_dir]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    return result.returncode, result.stdout, result.stderr


def _read_code(file_path: Path) -> str:
    return file_path.read_text(encoding="utf-8")


def _write_code(file_path: Path, code: str) -> None:
    try:
        file_path.write_text(code, encoding="utf-8")
    except OSError as exc:
        raise FixError(
            f"Cannot write to {file_path}",
            file_path=str(file_path),
            reason=str(exc),
        ) from exc


class CorrectionLoop:
    """Run test → detect failure → apply fix → verify, up to *max_attempts*.

    Parameters:
        target_file: Path to the source file under repair.
        test_dir: Directory containing the test suite.
        max_attempts: Maximum correction iterations (default 3).
        runner: ``'unittest'`` or ``'pytest'``.
        registry: The strategy chain to use.  If ``None``, the default
            registry is built with all strategies enabled.
        on_attempt: Optional callback invoked with each
            :class:`CorrectionResult` after every attempt.
    """

    def __init__(
        self,
        target_file: str | Path,
        test_dir: str = "tests",
        max_attempts: int = 3,
        runner: str = "unittest",
        registry: StrategyRegistry | None = None,
        on_attempt: object | None = None,
    ) -> None:
        self._target_file = Path(target_file)
        self._test_dir = test_dir
        self._max_attempts = max_attempts
        self._runner = runner
        self._registry = registry or get_registry()
        self._on_attempt = on_attempt
        self._history: list[CorrectionResult] = []

    @property
    def history(self) -> list[CorrectionResult]:
        return list(self._history)

    @property
    def succeeded(self) -> bool:
        return bool(self._history) and self._history[-1].is_success

    def run(self) -> CorrectionResult:
        """Execute the full correction loop. Returns the final result."""
        self._history.clear()

        for attempt in range(1, self._max_attempts + 1):
            result = self._attempt(attempt)
            self._history.append(result)
            self._notify(result)

            if result.is_success:
                return result

        return self._history[-1] if self._history else failure_result(
            attempt=self._max_attempts,
            strategy="none",
            message=f"Exhausted {self._max_attempts} attempts without a fix.",
            file_path=str(self._target_file),
        )

    def _run_verification(self) -> tuple[bool, str]:
        """Run tests and return ``(passed, combined_output)``."""
        return_code, stdout, stderr = run_tests(self._test_dir, self._runner)
        return return_code == 0, f"{stdout}\n{stderr}".strip()

    def _try_strategies(
        self, original_code: str, error_output: str
    ) -> tuple[str | None, Strategy | None]:  # noqa: F821
        """Delegate to the strategy registry to find a fix."""
        return self._registry.fix(
            original_code, error_output, str(self._target_file),
            test_dir=self._test_dir, runner=self._runner,
        )

    def _apply_fix(self, target_file: Path, fixed_code: str) -> tuple[bool, str]:
        """Write *fixed_code* to *target_file* and re-run tests.

        Returns ``(passed, combined_output)``.
        Raises :class:`FixError` if the file cannot be written.
        """
        _write_code(target_file, fixed_code)
        return_code, stdout, stderr = run_tests(self._test_dir, self._runner)
        return return_code == 0, f"{stdout}\n{stderr}".strip()

    def _attempt(self, attempt: int) -> CorrectionResult:
        t0 = time.monotonic()
        passed, test_output = self._run_verification()
        if passed:
            return success_result(
                attempt=attempt, strategy="none",
                file_path=str(self._target_file), original_code="",
                test_output=test_output, duration_s=time.monotonic() - t0,
            )
        original_code = _read_code(self._target_file)
        fixed_code, strategy = self._try_strategies(original_code, test_output)
        if fixed_code is None or strategy is None:
            return failure_result(
                attempt=attempt, strategy="none",
                message="No strategy could produce a fix.",
                file_path=str(self._target_file), original_code=original_code,
                test_output=test_output, duration_s=time.monotonic() - t0,
            )
        try:
            passed, verify_output = self._apply_fix(self._target_file, fixed_code)
        except FixError as exc:
            return failure_result(
                attempt=attempt, strategy=strategy.name, message=str(exc),
                file_path=str(self._target_file), original_code=original_code,
                fixed_code=fixed_code, test_output=test_output,
                duration_s=time.monotonic() - t0,
            )
        duration = time.monotonic() - t0
        if passed:
            return success_result(
                attempt=attempt, strategy=strategy.name,
                file_path=str(self._target_file), original_code=original_code,
                fixed_code=fixed_code, test_output=verify_output,
                duration_s=duration,
            )
        return failure_result(
            attempt=attempt, strategy=strategy.name,
            message=f"Fix via '{strategy.name}' did not resolve test failures.",
            file_path=str(self._target_file), original_code=original_code,
            fixed_code=fixed_code, test_output=verify_output,
            duration_s=duration,
        )

    def _notify(self, result: CorrectionResult) -> None:
        if self._on_attempt is not None:
            self._on_attempt(result)  # type: ignore[operator]

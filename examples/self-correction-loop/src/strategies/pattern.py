"""Pattern-based strategy: regex replacements for common Python errors."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from strategies.base import Strategy, StrategyKind


@dataclass(frozen=True)
class Pattern:
    """A single (pattern, replacement, description) triple.

    ``regex`` is compiled against the **error output** to decide whether the
    rule applies.  ``replacement`` is applied to the **source code**.
    """

    name: str
    error_regex: str
    code_pattern: str
    code_replacement: str
    description: str = ""

    # Compiled once at class level for performance.
    _compiled_error: re.Pattern[str] = field(init=False, repr=False)  # type: ignore[type-arg]

    def __post_init__(self) -> None:
        object.__setattr__(self, "_compiled_error", re.compile(self.error_regex, re.IGNORECASE))

    def matches_error(self, error_output: str) -> bool:
        """Return True if *error_output* matches the error-side regex."""
        return bool(self._compiled_error.search(error_output))

    def apply(self, code: str) -> str | None:
        """Attempt the code-side substitution.

        Returns the modified code or ``None`` if the code pattern was not found.
        """
        new_code, count = re.subn(self.code_pattern, self.code_replacement, code)
        if count > 0:
            return new_code
        return None


# ---------------------------------------------------------------------------
# Built-in pattern catalogue
# ---------------------------------------------------------------------------

_BUILTIN_PATTERNS: list[Pattern] = [
    Pattern(
        name="off-by-one-range",
        error_regex=r"AssertionError",
        code_pattern=r"range\(len\((\w+)\)\s*-\s*1\)",
        code_replacement=r"range(len(\1))",
        description="Fix off-by-one: range(len(x)-1) → range(len(x))",
    ),
    Pattern(
        name="off-by-one-iteration",
        error_regex=r"AssertionError",
        code_pattern=r"for\s+\w+\s+in\s+range\((\w+)\s*-\s*1\):",
        code_replacement=r"for i in range(len(\1)):",
        description="Fix iteration that skips the last element",
    ),
    Pattern(
        name="missing-import",
        error_regex=r"NameError:\s*name '(\w+)' is not defined",
        code_pattern=r"# missing import placeholder",
        code_replacement=r"# (import fix requires LLM strategy)",
        description="Detect undefined name errors (defers to LLM for import insertion)",
    ),
    Pattern(
        name="zero-division-guard",
        error_regex=r"ZeroDivisionError",
        code_pattern=r"(def\s+\w+\([^)]*\):)\s*\n(\s+)(.+)",
        code_replacement=r"\1\n\2if True:  # guard\n\3",
        description="Insert a division-by-zero guard (skeleton – LLM refines)",
    ),
]


@Strategy.register(StrategyKind.PATTERN)
class PatternStrategy(Strategy):
    """Match known error signatures and apply regex-based source-code fixes.

    The strategy walks through a catalogue of :class:`Pattern` objects.  For
    each pattern whose *error regex* matches the captured test output, it
    attempts the corresponding *code replacement*.  The first successful
    substitution wins.
    """

    def __init__(self, patterns: list[Pattern] | None = None) -> None:
        self._patterns: list[Pattern] = list(patterns or _BUILTIN_PATTERNS)

    @property
    def name(self) -> str:
        return "pattern"

    @property
    def patterns(self) -> list[Pattern]:
        """Expose the pattern catalogue (read-only copy)."""
        return list(self._patterns)

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        """Try each pattern; return the first successful code replacement."""
        for pattern in self._patterns:
            if pattern.matches_error(error_output):
                new_code = pattern.apply(code)
                if new_code is not None:
                    return new_code
        return None

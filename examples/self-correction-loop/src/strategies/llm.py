"""LLM-based correction strategy using OpenAI API."""

from __future__ import annotations

import os

from strategies.base import Strategy, StrategyKind

# Lazy import: openai may not be installed in demo mode.
_openai: object | None = None


def _get_openai() -> object:  # type: ignore[type-arg]
    """Import and cache the ``openai`` package."""
    global _openai  # noqa: PLW0603
    if _openai is None:
        try:
            import openai as _mod  # noqa: PLC0415

            _openai = _mod
        except ImportError as exc:
            raise ImportError(
                "The 'openai' package is required for the LLM strategy.  "
                "Install it with: pip install openai"
            ) from exc
    return _openai


# ---------------------------------------------------------------------------
# Mock fallback (original behaviour preserved)
# ---------------------------------------------------------------------------


def _mock_fix(code: str, error_output: str) -> str | None:
    """Deterministic mock that fixes the known off-by-one bug.

    Returns ``None`` when the error is not one the mock understands.
    """
    import re  # noqa: PLC0415

    if "range(len(" in code and re.search(r"-\s*1", code):
        fixed, count = re.subn(r"range\(len\((\w+)\)\s*-\s*1\)", r"range(len(\1))", code)
        if count > 0:
            return fixed
    return None


# ---------------------------------------------------------------------------
# Strategy implementation
# ---------------------------------------------------------------------------


def _build_prompt(code: str, error_output: str) -> str:
    """Construct the chat-completion prompt."""
    return (
        "The following Python code is failing a test.\n\n"
        f"Code:\n```\n{code}\n```\n\n"
        f"Error output:\n```\n{error_output}\n```\n\n"
        "Please provide ONLY the corrected Python code.  "
        "No explanations, no markdown fences, no extra text."
    )


@Strategy.register(StrategyKind.LLM)
class LLMStrategy(Strategy):
    """Send the failing code + error to an LLM and request a fix.

    If the ``openai`` package is not installed or ``OPENAI_API_KEY`` is
    unset, the strategy falls back to a deterministic mock that handles
    the known off-by-one bug.
    """

    def __init__(
        self,
        model: str = "gpt-4-turbo-preview",
        temperature: float = 0.0,
        max_retries: int = 1,
        **client_kwargs: object,
    ) -> None:
        self._model = model
        self._temperature = temperature
        self._max_retries = max_retries
        self._client_kwargs = client_kwargs

    @property
    def name(self) -> str:
        return "llm"

    def _call_llm(self, prompt: str) -> str | None:
        """Make a single OpenAI chat-completion call."""
        openai_mod = _get_openai()
        client = openai_mod.OpenAI(**self._client_kwargs)  # type: ignore[union-attr]
        response = client.chat.completions.create(
            model=self._model,
            temperature=self._temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.choices[0].message.content

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        """Request an LLM fix, falling back to the mock if unavailable."""
        api_key = os.environ.get("OPENAI_API_KEY")

        if openai_mod is None or api_key is None:
            return _mock_fix(code, error_output)

        prompt = _build_prompt(code, error_output)
        try:
            result: str | None = self._call_llm(prompt)
            return result.strip() if result else None
        except Exception:
            # Last resort: try the mock.
            return _mock_fix(code, error_output)


# Re-export for type-checkers.
try:
    import openai as openai_mod  # noqa: F401
except ImportError:
    openai_mod = None  # type: ignore[assignment]

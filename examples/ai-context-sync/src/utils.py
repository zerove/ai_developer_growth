import functools
import json
import re
import time
from typing import Any, Callable, List, Optional, TypeVar

from .logger import logger

T = TypeVar("T")


def parse_llm_json(text: str, label: str = "LLM response") -> Optional[List]:
    """Extract and parse a JSON array from LLM-generated text.

    Handles common LLM output patterns:
    - Plain JSON arrays: ``[{"key": "value"}]``
    - Markdown fenced code blocks: `````json [...]`````
    - Trailing commas before ``]``

    Args:
        text: Raw text returned by the LLM.
        label: Human-readable label for log messages.

    Returns:
        Parsed list, or ``None`` when parsing fails.
    """
    if not text:
        return None

    # Strip markdown code fences (```json ... ``` or ``` ... ```)
    fenced = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if fenced:
        text = fenced.group(1).strip()

    # Find the outermost JSON array using bracket counting (handles nested brackets)
    depth = 0
    start = -1
    for i, ch in enumerate(text):
        if ch == "[":
            if depth == 0:
                start = i
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0 and start != -1:
                candidate = text[start : i + 1]
                break
    else:
        logger.warning(f"⚠️ {label}: no JSON array found in response")
        return None

    # Remove trailing commas before ] or } (common LLM mistake)
    candidate = re.sub(r",\s*([}\]])", r"\1", candidate)

    try:
        result = json.loads(candidate)
        if not isinstance(result, list):
            logger.warning(f"⚠️ {label}: parsed JSON is not a list (got {type(result).__name__})")
            return None
        return result
    except json.JSONDecodeError as e:
        logger.error(f"❌ {label}: JSON parse failed — {e}")
        return None


def retry_on_failure(
    max_retries: int = 3,
    delay: float = 1.0,
    validate: Optional[Callable[[Any], bool]] = None,
    fallback: Optional[Any] = None,
    label: str = "operation",
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator that retries a function on failure with optional validation.

    Args:
        max_retries: Maximum number of retry attempts.
        delay: Seconds to wait between retries.
        validate: Callable that receives the result and returns True if valid.
                  If None, any non-falsy result is considered valid.
        fallback: Value to return when all retries are exhausted.
        label: Human-readable name for log messages.
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            last_result = None
            for attempt in range(1, max_retries + 1):
                last_result = func(*args, **kwargs)

                is_valid = validate(last_result) if validate else bool(last_result)
                if is_valid:
                    return last_result

                logger.warning(f"⚠️ {label} attempt {attempt}/{max_retries} returned invalid result. Retrying...")
                if attempt < max_retries:
                    time.sleep(delay)

            logger.warning(f"❌ {label}: all {max_retries} attempts exhausted.")
            return fallback if fallback is not None else last_result  # type: ignore[return-value]

        return wrapper

    return decorator

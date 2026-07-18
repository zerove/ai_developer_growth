import time
import functools
from typing import Callable, Optional, TypeVar, Any

from .logger import logger

T = TypeVar("T")


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

                is_valid = (
                    validate(last_result) if validate else bool(last_result)
                )
                if is_valid:
                    return last_result

                logger.warning(
                    f"⚠️ {label} attempt {attempt}/{max_retries} returned invalid result. Retrying..."
                )
                if attempt < max_retries:
                    time.sleep(delay)

            logger.warning(f"❌ {label}: all {max_retries} attempts exhausted.")
            return fallback if fallback is not None else last_result  # type: ignore[return-value]

        return wrapper

    return decorator

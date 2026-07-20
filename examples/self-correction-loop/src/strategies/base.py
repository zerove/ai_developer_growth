"""Strategy protocol and registry for correction strategies."""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import ClassVar


class StrategyKind(Enum):
    """Built-in strategy identifiers."""

    RETRY = auto()
    PATTERN = auto()
    LLM = auto()
    CUSTOM = auto()  # reserved for user-defined strategies


class Strategy(ABC):
    """Abstract base for all correction strategies.

    Subclasses must implement :meth:`name` and :meth:`fix`.
    """

    # Registry of concrete strategies keyed by kind.
    _registry: ClassVar[dict[StrategyKind, type[Strategy]]] = {}

    # ---- class helpers --------------------------------------------------

    @classmethod
    def register(cls, kind: StrategyKind) -> type[Strategy]:
        """Class decorator that registers a strategy under *kind*."""

        def decorator(subclass: type[Strategy]) -> type[Strategy]:
            cls._registry[kind] = subclass
            return subclass

        return decorator

    @classmethod
    def create(cls, kind: StrategyKind, **kwargs: object) -> Strategy:
        """Instantiate a registered strategy by *kind*."""
        factory = cls._registry.get(kind)
        if factory is None:
            raise ValueError(f"No strategy registered for {kind!r}")
        return factory(**kwargs)

    @classmethod
    def available_kinds(cls) -> list[StrategyKind]:
        """Return all registered strategy kinds."""
        return list(cls._registry)

    # ---- instance interface ---------------------------------------------

    @property
    @abstractmethod
    def name(self) -> str:
        """Short human-readable name (e.g. ``'pattern'``)."""

    @abstractmethod
    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> str | None:
        """Attempt to fix *code* given *error_output*.

        Returns the fixed source code string, or ``None`` if this strategy
        cannot handle the given error.
        """


class StrategyRegistry:
    """Lightweight container that resolves strategies by priority order.

    Strategies are tried in the order provided; the first one that returns
    a non-``None`` fix wins.
    """

    def __init__(self, strategies: list[Strategy] | None = None) -> None:
        self._strategies: list[Strategy] = list(strategies) if strategies else []

    def add(self, strategy: Strategy) -> None:
        """Append a strategy to the end of the chain."""
        self._strategies.append(strategy)

    @property
    def strategies(self) -> list[Strategy]:
        """Return the ordered list of strategies."""
        return list(self._strategies)

    def fix(
        self,
        code: str,
        error_output: str,
        file_path: str | None = None,
        test_dir: str = "tests",
        runner: str = "unittest",
    ) -> tuple[str | None, Strategy | None]:
        """Try each strategy in order.

        Returns ``(fixed_code, strategy_used)`` or ``(None, None)`` if all
        strategies declined.
        """
        for strategy in self._strategies:
            try:
                result = strategy.fix(
                    code, error_output, file_path,
                    test_dir=test_dir, runner=runner,
                )
            except TypeError:
                # Backward compatibility: strategy subclass doesn't accept
                # the new kwargs – fall back to the legacy signature.
                result = strategy.fix(code, error_output, file_path)
            if result is not None:
                return result, strategy
        return None, None


def get_registry(
    *,
    enable_retry: bool = True,
    enable_pattern: bool = True,
    enable_llm: bool = True,
    llm_model: str = "gpt-4-turbo-preview",
    **llm_kwargs: object,
) -> StrategyRegistry:
    """Build the default strategy chain.

    Args:
        enable_retry: Include the retry strategy (re-run with tuned params).
        enable_pattern: Include the pattern-matching strategy.
        enable_llm: Include the LLM-based strategy.
        llm_model: Model identifier for the LLM strategy.
        **llm_kwargs: Extra keyword args forwarded to :class:`LLMStrategy`.
    """
    from strategies.llm import LLMStrategy  # noqa: PLC0415
    from strategies.pattern import PatternStrategy  # noqa: PLC0415
    from strategies.retry import RetryStrategy  # noqa: PLC0415

    chain: list[Strategy] = []
    if enable_retry:
        chain.append(RetryStrategy())
    if enable_pattern:
        chain.append(PatternStrategy())
    if enable_llm:
        chain.append(LLMStrategy(model=llm_model, **llm_kwargs))  # type: ignore[arg-type]
    return StrategyRegistry(chain)

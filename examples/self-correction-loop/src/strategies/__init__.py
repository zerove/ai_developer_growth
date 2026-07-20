"""Correction strategies.

Each strategy knows how to produce a fixed version of the source code
given the original code and the test-suite error output.
"""  # noqa: N999

from strategies.base import Strategy, StrategyRegistry, get_registry
from strategies.llm import LLMStrategy
from strategies.pattern import PatternStrategy
from strategies.retry import RetryStrategy

__all__ = [
    "LLMStrategy",
    "PatternStrategy",
    "RetryStrategy",
    "Strategy",
    "StrategyRegistry",
    "get_registry",
]

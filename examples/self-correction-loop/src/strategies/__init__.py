"""Correction strategies.

Each strategy knows how to produce a fixed version of the source code
given the original code and the test-suite error output.
"""

from src.strategies.base import Strategy, StrategyRegistry, get_registry
from src.strategies.llm import LLMStrategy
from src.strategies.pattern import PatternStrategy
from src.strategies.retry import RetryStrategy

__all__ = [
    "LLMStrategy",
    "PatternStrategy",
    "RetryStrategy",
    "Strategy",
    "StrategyRegistry",
    "get_registry",
]

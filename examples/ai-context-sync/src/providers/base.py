"""Base class for LLM providers."""
from typing import Optional


class LLMProvider:
    """Base class for LLM providers."""

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None) -> None:
        self.api_key = api_key
        self.api_base = api_base

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        raise NotImplementedError

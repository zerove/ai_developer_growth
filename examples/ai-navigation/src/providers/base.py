"""Base class for LLM providers."""


class LLMProvider:
    """Base class for LLM providers."""

    def __init__(self, api_key: str | None = None, api_base: str | None = None) -> None:
        self.api_key = api_key
        self.api_base = api_base

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        raise NotImplementedError

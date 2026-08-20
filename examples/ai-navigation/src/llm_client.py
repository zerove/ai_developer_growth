"""
LLM Client with multi-provider support and caching.

Supported providers:
- openai: OpenAI API (GPT-4o, GPT-4, etc.)
- claude: Anthropic Claude API (Claude 3.5 Sonnet, etc.)
- ollama: Local Ollama server (llama3, mistral, etc.)
- system: Auto-detect from jcode/opencode environment
"""

import hashlib
import json
import os
import time

import requests

from .exceptions import LLMError
from .logger import logger

# Re-export all provider classes for backward compatibility
from .providers import (  # noqa: F401
    ClaudeProvider,
    GeminiProvider,
    LLMProvider,
    OllamaProvider,
    OpenAIProvider,
    SystemProvider,
)


class LLMCache:
    """Simple file-based cache for LLM responses."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(
        self, cache_dir: str = ".ai-sync-cache", ttl: int = DEFAULT_TTL
    ) -> None:
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)

    def _make_key(
        self, provider: str, model: str, prompt: str, system_prompt: str
    ) -> str:
        content = f"{provider}:{model}:{system_prompt}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(
        self, provider: str, model: str, prompt: str, system_prompt: str
    ) -> str | None:
        key = self._make_key(provider, model, prompt, system_prompt)
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) > self.ttl:
                os.remove(path)
                return None
            return str(data.get("response", ""))
        except (json.JSONDecodeError, OSError):
            return None

    def set(
        self, provider: str, model: str, prompt: str, system_prompt: str, response: str
    ) -> None:
        key = self._make_key(provider, model, prompt, system_prompt)
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"response": response, "timestamp": time.time()}, f)
        except OSError as e:
            logger.warning(f"Failed to write LLM cache: {e}")


PROVIDERS = {
    "openai": OpenAIProvider,
    "claude": ClaudeProvider,
    "anthropic": ClaudeProvider,
    "ollama": OllamaProvider,
    "gemini": GeminiProvider,
    "system": SystemProvider,
}


class LLMClient:
    """
    Multi-provider LLM client with caching.

    Supports OpenAI, Claude, and Ollama providers.
    Configure via .ai-sync.json or environment variables.
    """

    def __init__(
        self,
        provider: str = "openai",
        model: str = "gpt-4o",
        api_base: str | None = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
    ) -> None:
        self.provider_name = provider
        self.model = "auto" if provider == "system" else model
        self.api_key = os.getenv("AI_SYNC_KEY")

        provider_class = PROVIDERS.get(provider)
        if not provider_class:
            raise LLMError(
                f"Unsupported provider: {provider}. Supported: {list(PROVIDERS.keys())}"
            )

        self._provider = provider_class(api_key=self.api_key, api_base=api_base)
        self._cache = LLMCache(ttl=cache_ttl) if cache_enabled else None

        if not self.api_key and provider != "ollama":
            logger.warning("AI_SYNC_KEY environment variable not set.")

    def generate(
        self, prompt: str, system_prompt: str = "You are a helpful assistant."
    ) -> str | None:
        if self.provider_name == "system":
            pass
        elif not self.api_key and self.provider_name != "ollama":
            return f"[Mock Response] (API Key missing) Based on the prompt: {prompt[:50]}..."

        if self._cache:
            cached = self._cache.get(
                self.provider_name, self.model, prompt, system_prompt
            )
            if cached is not None:
                logger.debug(f"LLM cache hit for {self.provider_name}/{self.model}")
                return cached

        try:
            result = self._provider.generate(prompt, system_prompt, self.model)
            if self._cache and result:
                self._cache.set(
                    self.provider_name, self.model, prompt, system_prompt, result
                )
            return result
        except requests.RequestException as e:
            logger.error(f"Error calling LLM ({self.provider_name}): {e}")
            raise LLMError(f"LLM API call failed ({self.provider_name}): {e}") from e

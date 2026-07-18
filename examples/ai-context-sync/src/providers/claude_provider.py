"""Anthropic Claude API provider."""
import requests

from .base import LLMProvider


class ClaudeProvider(LLMProvider):
    """Anthropic Claude API provider."""

    DEFAULT_BASE_URL = "https://api.anthropic.com/v1"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/messages"
        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "max_tokens": 4096,
            "system": system_prompt,
            "messages": [
                {"role": "user", "content": prompt}
            ]
        }
        response = requests.post(url, json=payload, headers=headers, timeout=60)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()['content'][0]['text'])

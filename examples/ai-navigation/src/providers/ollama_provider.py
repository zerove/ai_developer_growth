"""Local Ollama server provider."""

import requests

from .base import LLMProvider


class OllamaProvider(LLMProvider):
    """Local Ollama server provider."""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/api/chat"
        payload = {
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}],
            "stream": False,
        }
        response = requests.post(url, json=payload, timeout=120)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()["message"]["content"])

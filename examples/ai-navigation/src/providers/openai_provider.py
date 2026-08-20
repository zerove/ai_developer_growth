"""OpenAI API provider."""

import requests

from .base import LLMProvider


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()["choices"][0]["message"]["content"])

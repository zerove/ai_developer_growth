"""Google Gemini API provider."""
import requests

from .base import LLMProvider


class GeminiProvider(LLMProvider):
    """Google Gemini API provider."""

    DEFAULT_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/models/{model}:generateContent?key={self.api_key}"
        payload = {
            "contents": [
                {"role": "user", "parts": [{"text": prompt}]}
            ],
            "systemInstruction": {
                "parts": [{"text": system_prompt}]
            },
            "generationConfig": {
                "temperature": 0.3
            }
        }
        response = requests.post(url, json=payload, timeout=60)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()['candidates'][0]['content']['parts'][0]['text'])

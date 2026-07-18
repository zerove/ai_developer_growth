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
from typing import Optional, Dict, Any
import requests

from .logger import logger
from .exceptions import LLMError


class LLMCache:
    """Simple file-based cache for LLM responses."""

    DEFAULT_TTL = 3600  # 1 hour

    def __init__(self, cache_dir: str = ".ai-sync-cache", ttl: int = DEFAULT_TTL) -> None:
        self.cache_dir = cache_dir
        self.ttl = ttl
        os.makedirs(cache_dir, exist_ok=True)

    def _make_key(self, provider: str, model: str, prompt: str, system_prompt: str) -> str:
        content = f"{provider}:{model}:{system_prompt}:{prompt}"
        return hashlib.sha256(content.encode()).hexdigest()

    def get(self, provider: str, model: str, prompt: str, system_prompt: str) -> Optional[str]:
        key = self._make_key(provider, model, prompt, system_prompt)
        path = os.path.join(self.cache_dir, f"{key}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if time.time() - data.get("timestamp", 0) > self.ttl:
                os.remove(path)
                return None
            return str(data.get("response", ""))
        except (json.JSONDecodeError, OSError):
            return None

    def set(self, provider: str, model: str, prompt: str, system_prompt: str, response: str) -> None:
        key = self._make_key(provider, model, prompt, system_prompt)
        path = os.path.join(self.cache_dir, f"{key}.json")
        try:
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"response": response, "timestamp": time.time()}, f)
        except OSError as e:
            logger.warning(f"Failed to write LLM cache: {e}")


class LLMProvider:
    """Base class for LLM providers."""

    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None) -> None:
        self.api_key = api_key
        self.api_base = api_base

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        raise NotImplementedError


class OpenAIProvider(LLMProvider):
    """OpenAI API provider."""

    DEFAULT_BASE_URL = "https://api.openai.com/v1"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.3
        }
        response = requests.post(url, json=payload, headers=headers, timeout=30)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()['choices'][0]['message']['content'])


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


class OllamaProvider(LLMProvider):
    """Local Ollama server provider."""

    DEFAULT_BASE_URL = "http://localhost:11434"

    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        url = f"{self.api_base or self.DEFAULT_BASE_URL}/api/chat"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "stream": False
        }
        response = requests.post(url, json=payload, timeout=120)  # type: ignore[arg-type]
        response.raise_for_status()
        return str(response.json()['message']['content'])


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


class SystemProvider(LLMProvider):
    """Auto-detect and use LLM from jcode/opencode environment.
    
    Detection priority: AI_SYNC_KEY > JCODE_PROVIDER_* > OPENAI/ANTHROPIC_API_KEY > jcode config > opencode config > Ollama
    """
    
    ENV_PATTERNS = {
        "openai": ["JCODE_PROVIDER_OPENAI_API_KEY", "OPENAI_API_KEY", "OPENAI_COMPAT_API_KEY"],
        "claude": ["JCODE_PROVIDER_ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY"],
        "gemini": ["JCODE_PROVIDER_GEMINI_API_KEY", "GEMINI_API_KEY"],
    }
    
    def __init__(self, api_key: Optional[str] = None, api_base: Optional[str] = None) -> None:
        super().__init__(api_key, api_base)
        self._detected_provider: Optional[str] = None
        self._detected_model: Optional[str] = None
        self._detected_api_key: Optional[str] = None
        self._detected_base_url: Optional[str] = None
        self._detect_environment()
    
    def _detect_environment(self) -> None:
        if self._load_jcode_config():
            return
        if self._load_opencode_config():
            return
        for provider, env_vars in self.ENV_PATTERNS.items():
            for env_var in env_vars:
                api_key = os.getenv(env_var)
                if api_key:
                    self._detected_provider = provider
                    self._detected_api_key = api_key
                    logger.info(f"Detected {provider} API key from {env_var}")
                    return
        try:
            response = requests.get("http://localhost:11434/api/tags", timeout=2)
            if response.status_code == 200:
                self._detected_provider = "ollama"
                logger.info("Detected Ollama server running locally")
        except requests.RequestException:
            pass
    
    def _load_jcode_config(self) -> bool:
        config_path = os.path.expanduser("~/.jcode/config.toml")
        if not os.path.exists(config_path):
            return False
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                content = f.read()
            provider = self._parse_toml_value(content, "default_provider")
            model = self._parse_toml_value(content, "default_model")
            if provider:
                self._detected_provider = provider
                self._detected_model = model
                env_file = os.path.expanduser(f"~/.config/jcode/{provider}.env")
                if os.path.exists(env_file):
                    with open(env_file, "r", encoding="utf-8") as f:
                        for line in f:
                            if line.startswith("API_KEY="):
                                self._detected_api_key = line.split("=", 1)[1].strip()
                                break
                logger.info(f"Loaded jcode config: provider={provider}, model={model}")
                return True
        except Exception as e:
            logger.debug(f"Failed to load jcode config: {e}")
        return False
    
    def _load_opencode_config(self) -> bool:
        config_paths = [
            os.path.expanduser("~/.opencode/config.json"),
            ".opencode/config.json",
            "opencode.json",
        ]
        for config_path in config_paths:
            if not os.path.exists(config_path):
                continue
            try:
                with open(config_path, "r", encoding="utf-8") as f:
                    config = json.load(f)
                provider = config.get("provider", config.get("model", {}).get("provider"))
                model = config.get("model", {}).get("name") if isinstance(config.get("model"), dict) else config.get("model")
                if provider:
                    self._detected_provider = provider
                    self._detected_model = model
                    logger.info(f"Loaded opencode config: provider={provider}, model={model}")
                    return True
            except Exception as e:
                logger.debug(f"Failed to load opencode config from {config_path}: {e}")
        return False
    
    def _parse_toml_value(self, content: str, key: str) -> Optional[str]:
        import re
        pattern = rf'^{key}\s*=\s*["\']?([^"\'\n]+)["\']?\s*$'
        match = re.search(pattern, content, re.MULTILINE)
        return match.group(1).strip() if match else None
    
    def generate(self, prompt: str, system_prompt: str, model: str) -> str:
        if not self._detected_provider:
            raise LLMError(
                "No LLM environment detected. Please configure one of:\n"
                "1. Set AI_SYNC_KEY environment variable\n"
                "2. Install and configure jcode (jcode login)\n"
                "3. Install and configure opencode\n"
                "4. Set OPENAI_API_KEY or ANTHROPIC_API_KEY\n"
                "5. Run Ollama locally"
            )
        
        provider = self._detected_provider
        if model and model != "auto":
            use_model = model
        elif self._detected_model:
            use_model = self._detected_model
        else:
            use_model = "gemini-2.5-flash" if provider == "gemini" else "gpt-4o"
        api_key = self.api_key or self._detected_api_key
        if not api_key and provider not in ("ollama",):
            raise LLMError(f"No API key found for provider: {provider}")
        
        if provider in ("openai", "openai-compatible"):
            provider_instance = OpenAIProvider(api_key=api_key, api_base=self._detected_base_url or self.api_base)
        elif provider in ("claude", "anthropic"):
            provider_instance = ClaudeProvider(api_key=api_key, api_base=self._detected_base_url or self.api_base)
        elif provider == "gemini":
            provider_instance = GeminiProvider(api_key=api_key, api_base=self._detected_base_url or self.api_base)
        elif provider == "ollama":
            provider_instance = OllamaProvider(api_base=self._detected_base_url or self.api_base)
        else:
            raise LLMError(f"Unsupported detected provider: {provider}")
        
        logger.info(f"Using detected provider: {provider}/{use_model}")
        try:
            return provider_instance.generate(prompt, system_prompt, use_model)
        except Exception as e:
            if provider == "ollama":
                raise
            logger.warning(f"Provider {provider} failed: {e}, trying Ollama fallback")
            try:
                ollama = OllamaProvider()
                return ollama.generate(prompt, system_prompt, use_model)
            except Exception:
                raise LLMError(f"All providers failed. Last error: {e}") from e


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
        api_base: Optional[str] = None,
        cache_enabled: bool = True,
        cache_ttl: int = 3600,
    ) -> None:
        self.provider_name = provider
        self.model = "auto" if provider == "system" else model
        self.api_key = os.getenv("AI_SYNC_KEY")
        
        provider_class = PROVIDERS.get(provider)
        if not provider_class:
            raise LLMError(f"Unsupported provider: {provider}. Supported: {list(PROVIDERS.keys())}")
        
        self._provider = provider_class(api_key=self.api_key, api_base=api_base)
        self._cache = LLMCache(ttl=cache_ttl) if cache_enabled else None
        
        if not self.api_key and provider != "ollama":
            logger.warning("AI_SYNC_KEY environment variable not set.")

    def generate(self, prompt: str, system_prompt: str = "You are a helpful assistant.") -> Optional[str]:
        if self.provider_name == "system":
            pass
        elif not self.api_key and self.provider_name != "ollama":
            return f"[Mock Response] (API Key missing) Based on the prompt: {prompt[:50]}..."

        if self._cache:
            cached = self._cache.get(self.provider_name, self.model, prompt, system_prompt)
            if cached is not None:
                logger.debug(f"LLM cache hit for {self.provider_name}/{self.model}")
                return cached

        try:
            result = self._provider.generate(prompt, system_prompt, self.model)
            if self._cache and result:
                self._cache.set(self.provider_name, self.model, prompt, system_prompt, result)
            return result
        except requests.RequestException as e:
            logger.error(f"Error calling LLM ({self.provider_name}): {e}")
            raise LLMError(f"LLM API call failed ({self.provider_name}): {e}") from e

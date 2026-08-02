"""Auto-detect and use LLM from jcode/opencode environment."""

import json
import os
import re
from typing import Optional

import requests

from ..exceptions import LLMError
from ..logger import logger
from .base import LLMProvider
from .claude_provider import ClaudeProvider
from .gemini_provider import GeminiProvider
from .ollama_provider import OllamaProvider
from .openai_provider import OpenAIProvider


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
        except requests.RequestException as e:
            logger.debug(f"Ollama detection failed: {e}")

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
        except (OSError, json.JSONDecodeError) as e:
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
                model_config = config.get("model")
                if isinstance(model_config, dict):
                    provider = config.get("provider", model_config.get("provider"))
                    model = model_config.get("name")
                else:
                    provider = config.get("provider")
                    model = model_config
                if provider:
                    self._detected_provider = provider
                    self._detected_model = model
                    logger.info(f"Loaded opencode config: provider={provider}, model={model}")
                    return True
            except (OSError, json.JSONDecodeError) as e:
                logger.debug(f"Failed to load opencode config from {config_path}: {e}")
        return False

    def _parse_toml_value(self, content: str, key: str) -> Optional[str]:
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
        except (LLMError, requests.RequestException) as e:
            if provider == "ollama":
                raise  # 合法重抛：ollama 自身错误不降级
            logger.warning(f"Provider {provider} failed: {e}, trying Ollama fallback")
            try:
                ollama = OllamaProvider()
                return ollama.generate(prompt, system_prompt, use_model)
            except (LLMError, requests.RequestException):
                raise LLMError(f"All providers failed. Last error: {e}") from e

from dataclasses import dataclass, field, asdict
from typing import List, Optional
import json
import os
from .exceptions import ConfigError

@dataclass
class LLMConfig:
    provider: str = "system"  # Default to auto-detect from jcode/opencode
    model: str = "auto"  # Use detected model or fallback to gpt-4o
    api_base: Optional[str] = None

@dataclass
class SyncSettings:
    ignore: List[str] = field(default_factory=lambda: ["package-lock.json", ".gitignore", "dist/*"])
    auto_commit: bool = False
    context_file: str = "CONTEXT.md"
    adr_dir: str = "docs/adr/"
    test_command: str = "pytest"
    overridden_violations: List[str] = field(default_factory=list)
    executor_max_workers: int = 4
    test_timeout: int = 30
    max_retries: int = 3
    watcher_debounce: float = 1.0
    live_report_path: str = "docs/ai-audit-live.md"
    specs_dir: str = "docs/specs"

@dataclass
class AppConfig:
    llm: LLMConfig = field(default_factory=LLMConfig)
    settings: SyncSettings = field(default_factory=SyncSettings)
    config_path: str = ".ai-sync.json"

    def save(self) -> None:
        try:
            with open(self.config_path, "w") as f:
                data = {
                    "llm": asdict(self.llm),
                    "settings": asdict(self.settings)
                }
                json.dump(data, f, indent=2)
        except OSError as e:
            raise ConfigError(f"Failed to save config to {self.config_path}: {e}") from e

    @classmethod
    def load(cls, path: str) -> "AppConfig":
        if not os.path.exists(path):
            return cls(config_path=path)
        
        try:
            with open(path, "r") as f:
                data = json.load(f)
            
            llm_data = data.get("llm", {})
            settings_data = data.get("settings", {})
            
            # Ensure overridden_violations exists if not in file
            if "overridden_violations" not in settings_data:
                settings_data["overridden_violations"] = []
            
            config = cls(
                llm=LLMConfig(**llm_data),
                settings=SyncSettings(**settings_data),
                config_path=path
            )
        except (json.JSONDecodeError, KeyError, TypeError) as e:
            import logging
            logging.warning(f"Error loading config, using defaults: {e}")
            config = cls(config_path=path)

        env_map = {
            "AI_SYNC_LLM_PROVIDER": ("llm", "provider"),
            "AI_SYNC_LLM_MODEL": ("llm", "model"),
            "AI_SYNC_LLM_API_BASE": ("llm", "api_base"),
            "AI_SYNC_KEY": ("llm", "api_key"),
            "AI_SYNC_CONTEXT_FILE": ("settings", "context_file"),
            "AI_SYNC_ADR_DIR": ("settings", "adr_dir"),
            "AI_SYNC_TEST_COMMAND": ("settings", "test_command"),
        }
        for env_key, (section, attr_name) in env_map.items():
            env_val = os.getenv(env_key)
            if env_val is not None:
                setattr(getattr(config, section), attr_name, env_val)

        return config

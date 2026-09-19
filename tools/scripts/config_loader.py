# 配置加载器

from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar

import yaml

T = TypeVar("T")


class ConfigLoader:
    """统一配置加载器。

    从 config/ 目录加载所有配置文件，提供统一访问接口。
    """

    _instance: ConfigLoader | None = None
    _configs: dict[str, dict[str, Any]] = {}

    def __new__(cls) -> ConfigLoader:
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        if not self._configs:
            self._load_all()

    def _load_all(self) -> None:
        """加载 config/ 目录下所有 YAML 配置。"""
        # 从项目根目录查找 config 目录
        config_dir = Path(__file__).parent.parent.parent / "config"
        if not config_dir.exists():
            # 备选：当前工作目录
            config_dir = Path.cwd() / "config"
        if not config_dir.exists():
            return

        for yaml_file in config_dir.glob("*.yaml"):
            try:
                with yaml_file.open("r", encoding="utf-8") as f:
                    self._configs[yaml_file.stem] = yaml.safe_load(f) or {}
            except Exception as exc:  # noqa: BLE001
                import logging

                logging.getLogger(__name__).debug("配置加载失败 %s: %s", yaml_file.name, exc)

    def get(self, config_name: str, key: str | None = None, default: T | None = None) -> dict[str, Any] | T:
        """获取配置值。

        Args:
            config_name: 配置文件名 (不含 .yaml)
            key: 点分隔的键路径，如 "coverage.fail_under"
            default: 默认值

        Returns:
            配置值或默认值
        """
        config: dict[str, Any] = self._configs.get(config_name, {})
        if key is None:
            return config

        keys = key.split(".")
        value: dict[str, Any] | str | int | float | bool | list[Any] | None = config
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        return value

    def get_coverage_threshold(self) -> int:
        """获取覆盖率门禁阈值。"""
        return self.get("thresholds", "coverage.fail_under", 80)

    def get_complexity_threshold(self, language: str, metric: str) -> int | None:
        """获取复杂度阈值。"""
        return self.get("thresholds", f"complexity.{language}.{metric}")

    def get_ruff_version(self) -> str:
        """获取 ruff 版本。"""
        return self.get("versions", "python.ruff", "==0.15.17")

    def get_supported_languages(self) -> list[str]:
        """获取主要支持的语言列表。"""
        return self.get("languages", "supported", [])

    def get_ci_matrix_languages(self, job: str) -> list[str]:
        """获取 CI 矩阵语言列表。"""
        return self.get("languages", f"ci_matrix.{job}", [])


# 单例实例
config_loader = ConfigLoader()

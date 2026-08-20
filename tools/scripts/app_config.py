"""统一配置管理：读取 pyproject.toml 的 [tool.adg] 段。

所有工具共享同一份配置源（pyproject.toml），支持分层覆盖：
1. pyproject.toml [tool.adg]（基础配置）
2. 项目级 .adg/config.yml（可选覆盖）
3. 环境变量 ADG_*（最高优先级）

用法:
    from tools.scripts.app_config import get_setting, get_settings

    jobs = get_setting("jobs", default=4)
    settings = get_settings()  # 全部配置
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import tomllib

CONFIG_SECTION = "tool.adg"


@lru_cache(maxsize=8)
def _load_toml_config(path: str) -> dict[str, Any]:
    """加载 pyproject.toml 的 [tool.adg] 段（带缓存）。"""
    pp = Path(path)
    if not pp.exists():
        return {}
    try:
        with pp.open("rb") as f:
            data = tomllib.load(f)
        section = data.get("tool", {}).get("adg", {})
        return section if isinstance(section, dict) else {}
    except (tomllib.TOMLDecodeError, OSError):
        return {}


def _find_upwards(start: Path, filename: str) -> Path | None:
    """从 start 向上查找 filename，返回最近的一个。"""
    current = start.resolve()
    for parent in (current, *current.parents):
        candidate = parent / filename
        if candidate.exists():
            return candidate
    return None


def _load_project_overrides() -> dict[str, Any]:
    """加载项目级 .adg/config.yml 覆盖。"""
    root = get_project_root()
    config_file = root / ".adg" / "config.yml"
    if not config_file.exists():
        return {}
    try:
        import yaml

        data = yaml.safe_load(config_file.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "Failed to load .adg/config.yml", exc_info=True
        )
        return {}


def get_project_root() -> Path:
    """项目根目录（由环境变量覆盖，便于测试）。"""
    env_root = os.environ.get("ADG_PROJECT_ROOT", "")
    if env_root:
        return Path(env_root)
    return Path(__file__).resolve().parent.parent.parent


def get_settings() -> dict[str, Any]:
    """获取合并后的完整配置（pyproject.toml + .adg/config.yml）。"""
    settings: dict[str, Any] = {}
    pyproject = _find_upwards(get_project_root(), "pyproject.toml")
    if pyproject is not None:
        settings.update(_load_toml_config(str(pyproject)))
    settings.update(_load_project_overrides())
    return settings


def get_setting(key: str, default: object = None) -> object:
    """读取单个配置项（支持 ADG_* 环境变量覆盖）。"""
    settings = get_settings()
    if key in settings:
        return settings[key]

    env_key = "ADG_" + key.upper().replace("-", "_")
    if env_key in os.environ:
        return os.environ[env_key]

    return default


def get_path(setting_key: str, default: Path) -> Path:
    """读取配置项为路径（展开 ~ 与相对路径）。"""
    value = get_setting(setting_key)
    if value is None:
        return default
    return Path(os.path.expanduser(str(value))).expanduser()


def clear_cache() -> None:
    """清空配置缓存（测试用）。"""
    _load_toml_config.cache_clear()

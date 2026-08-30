"""
配置加载器

负责:
- 发现配置文件
- 合并继承链
- 环境变量覆盖
- Schema 验证
- 热重载监听
"""

from __future__ import annotations

import os
import threading
from collections.abc import Callable
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

import yaml

from .models import (
    DEFAULT_CONFIG_PATHS,
    BaselineConfig,
    CacheConfig,
    ExceptionRule,
    GitHooksConfig,
    GovernanceConfig,
    LanguageConfig,
    MetricsConfig,
    OutputConfig,
    ParallelConfig,
    QualityGateConfig,
    SecretScanConfig,
    SeverityLevel,
    SupplyChainConfig,
    ToolCategory,
    ToolConfig,
)

# 全局配置实例与锁
_config_instance: GovernanceConfig | None = None
_config_lock = threading.RLock()
_config_mtime: float = 0.0
_config_path: Path | None = None


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    """深度合并字典，override 覆盖 base"""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        elif key in result and isinstance(result[key], list) and isinstance(value, list):
            # 列表合并：去重保序
            seen = set()
            merged = []
            for item in result[key] + value:
                if item not in seen:
                    seen.add(item)
                    merged.append(item)
            result[key] = merged
        else:
            result[key] = value
    return result


def _dataclass_to_dict(obj: object) -> Any:
    """递归转换 dataclass 为字典"""
    if is_dataclass(obj) and not isinstance(obj, type):
        return {k: _dataclass_to_dict(v) for k, v in asdict(obj).items()}
    elif isinstance(obj, list):
        return [_dataclass_to_dict(v) for v in obj]
    elif isinstance(obj, dict):
        return {k: _dataclass_to_dict(v) for k, v in obj.items()}
    else:
        return obj


def _known_sections() -> set[str]:
    """已知的配置节点名 (用于环境变量路径分割)。"""
    return {
        "languages",
        "default_tools",
        "exceptions",
        "quality_gates",
        "qualitygates",
        "baseline",
        "secrets",
        "supply_chain",
        "supplychain",
        "cache",
        "parallel",
        "output",
        "git_hooks",
        "githooks",
        "metrics",
        "custom",
    }


def _parse_env_path(env_key: str, prefix: str) -> list[str]:
    """解析 JCODE_GOVERNANCE_PARALLEL_MAX_WORKERS -> ["parallel", "max_workers"]。"""
    path_str = env_key[len(prefix) :].lower()
    known_sections = _known_sections()

    # 找到第一个匹配的 section
    section = None
    rest = ""
    for known in known_sections:
        if path_str.startswith(known + "_"):
            section = known
            rest = path_str[len(known) + 1 :]
            break
        elif path_str == known:
            section = known
            rest = ""
            break

    if section is None:
        # 没有匹配的 section，按下划线分割第一个作为 section
        parts = path_str.split("_", 1)
        section = parts[0]
        rest = parts[1] if len(parts) > 1 else ""

    path_parts = [section]
    if rest:
        if rest in _KNOWN_COMPOUND_KEYS:
            path_parts.append(rest)
        else:
            # 否则按下划线分割
            path_parts.extend(rest.split("_"))
    return path_parts


_KNOWN_COMPOUND_KEYS = {
    "max_workers",
    "max_size_mb",
    "ttl_hours",
    "entropy_threshold",
    "min_coverage_overall",
    "min_coverage_changed",
    "max_critical",
    "max_high",
    "max_medium",
    "max_critical_vulns",
    "max_high_vulns",
    "prometheus_port",
    "push_gateway",
    "retention_days",
    "version_flag",
    "severity_threshold",
    "install_hint",
    "config_file",
    "key_factors",
    "sarif_output",
    "junit_output",
    "sbom_format",
    "sbom_output",
    "vulnerability_sources",
    "allowed_licenses",
    "denied_licenses",
    "trusted_publishers",
    "allowlist",
    "rules",
    "exclude",
    "include",
    "pre_commit",
    "pre_push",
    "commit_msg",
    "prepare_commit_msg",
    "run_on_partial_staging",
    "skip_on_merge_commit",
    "skip_on_fixup_commit",
    "scan_workspace",
    "scan_git_history",
    "scan_pr_diff",
    "scan_containers",
    "verify_active",
    "auto_update",
    "update_on_success",
    "compare_against",
    "fail_on_new",
    "fail_on_worsened",
    "require_zero_new_errors",
    "require_zero_new_warnings",
    "max_new_errors",
    "max_new_warnings",
    "allow_secrets",
    "allow_exceptions",
    "require_approval_for_exceptions",
    "baseline_branch",
    "generate_sbom",
    "verify_signatures",
    "enabled",
    "paths",
    "thresholds",
    "tools",
    "per_category",
    "verbose",
    "show_passed",
    "summary_only",
    "format",
}


def _set_nested_value(config_dict: dict[str, Any], path_parts: list[str], env_value: str) -> None:
    """导航嵌套字典并设置类型转换后的值。"""
    current = config_dict
    for i, part in enumerate(path_parts):
        if i == len(path_parts) - 1:
            # 尝试类型转换
            if env_value.lower() in ("true", "false"):
                current[part] = env_value.lower() == "true"
            elif env_value.isdigit():
                current[part] = int(env_value)
            else:
                try:
                    current[part] = float(env_value)
                except ValueError:
                    current[part] = env_value
        else:
            if part not in current:
                current[part] = {}
            current = current[part]


def _apply_env_overrides(config: GovernanceConfig) -> GovernanceConfig:
    """应用环境变量覆盖

    格式: JCODE_GOVERNANCE_<SECTION>_<KEY>=value
    例如: JCODE_GOVERNANCE_PARALLEL_MAX_WORKERS=8
          JCODE_GOVERNANCE_LANGUAGES_PYTHON_ENABLED=false
    """
    config_dict = _dataclass_to_dict(config)

    prefix = "JCODE_GOVERNANCE_"
    for env_key, env_value in os.environ.items():
        if not env_key.startswith(prefix):
            continue
        path_parts = _parse_env_path(env_key, prefix)
        _set_nested_value(config_dict, path_parts, env_value)

    return _dict_to_config(config_dict)


def _convert_tool_config(d: dict[str, Any]) -> ToolConfig:
    """处理 severity_threshold 枚举转换。"""
    if "severity_threshold" in d and isinstance(d["severity_threshold"], str):
        d["severity_threshold"] = SeverityLevel(d["severity_threshold"])
    return ToolConfig(**d)


def _convert_language_config(d: dict[str, Any]) -> LanguageConfig:
    tools = {}
    for k, v in d.get("tools", {}).items():
        if isinstance(k, str):
            try:
                cat = ToolCategory(k)
            except ValueError:
                continue
        else:
            cat = k
        tools[cat] = _convert_tool_config(v)
    d = {**d, "tools": tools}
    return LanguageConfig(**d)


def _convert_exception_rule(d: dict[str, Any]) -> ExceptionRule:
    if "severity" in d and isinstance(d["severity"], str):
        d["severity"] = SeverityLevel(d["severity"])
    return ExceptionRule(**d)


def _convert_parallel_config(d: dict[str, Any]) -> ParallelConfig:
    per_cat = {}
    for k, v in d.get("per_category", {}).items():
        if isinstance(k, str):
            try:
                cat = ToolCategory(k)
            except ValueError:
                continue
        else:
            cat = k
        per_cat[cat] = v
    d = {**d, "per_category": per_cat}
    return ParallelConfig(**d)


def _dict_to_config(data: dict[str, Any]) -> GovernanceConfig:
    """将字典转换为 GovernanceConfig (处理嵌套 dataclass)"""
    from .models import GovernanceConfig

    # 转换嵌套结构
    converted = {
        "version": data.get("version", 1),
        "extends": data.get("extends", []),
        "languages": {k: _convert_language_config(v) for k, v in data.get("languages", {}).items()},
        "default_tools": {ToolCategory(k): _convert_tool_config(v) for k, v in data.get("default_tools", {}).items()},
        "exceptions": [_convert_exception_rule(e) for e in data.get("exceptions", [])],
        "quality_gates": {k: QualityGateConfig(**v) for k, v in data.get("quality_gates", {}).items()},
        "baseline": BaselineConfig(**data.get("baseline", {})),
        "secrets": SecretScanConfig(**data.get("secrets", {})),
        "supply_chain": SupplyChainConfig(**data.get("supply_chain", {})),
        "cache": CacheConfig(**data.get("cache", {})),
        "parallel": _convert_parallel_config(data.get("parallel", {})),
        "output": OutputConfig(**data.get("output", {})),
        "git_hooks": GitHooksConfig(**data.get("git_hooks", {})),
        "metrics": MetricsConfig(**data.get("metrics", {})),
        "custom": data.get("custom", {}),
    }

    return GovernanceConfig(**converted)


def _load_yaml_file(path: Path) -> dict[str, Any] | None:
    """加载单个 YAML 文件"""
    if not path.exists():
        return None
    try:
        with open(path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        print(f"⚠️  无法加载配置 {path}: {e}")
        return None


def _load_toml_config(path: Path) -> dict[str, Any] | None:
    """从 pyproject.toml 读取 [tool.jcode.governance]"""
    if not path.exists():
        return None
    try:
        import tomllib

        with open(path, "rb") as f:
            data: dict[str, Any] = tomllib.load(f)
        governance = data.get("tool", {}).get("jcode", {}).get("governance", {})
        if not isinstance(governance, dict):
            return None
        return governance
    except Exception:
        return None


def _load_cfg_config(path: Path) -> dict[str, Any] | None:
    """从 setup.cfg 读取 [jcode:governance]"""
    if not path.exists():
        return None
    try:
        import configparser

        parser = configparser.ConfigParser()
        parser.read(path)
        if parser.has_section("jcode:governance"):
            return dict(parser["jcode:governance"])
        return None
    except Exception:
        return None


def _resolve_extends(config_dict: dict[str, Any], base_dir: Path) -> dict[str, Any]:
    """解析继承链 extends: [base, team, org]"""
    extends = config_dict.get("extends", [])
    if not extends:
        return config_dict

    # 移除 extends 避免递归
    local_config = {k: v for k, v in config_dict.items() if k != "extends"}

    # 从第一个开始合并 (最后一个优先级最高)
    merged: dict[str, Any] = {}
    for ext in extends:
        ext_path = base_dir / ext
        if not ext_path.is_absolute():
            ext_path = base_dir / ext
        if ext_path.suffix not in (".yaml", ".yml"):
            ext_path = ext_path.with_suffix(".yaml")

        ext_config = _load_yaml_file(ext_path)
        if ext_config:
            merged = _deep_merge(merged, ext_config)

    # 最后合并本地配置 (最高优先级)
    merged = _deep_merge(merged, local_config)
    return merged


def load_config(config_path: Path | str | None = None) -> GovernanceConfig:
    """加载配置 (V2.21 P5-33 拆分: 抽 _resolve_config_path + _load_config_dict).

    加载顺序 (后者覆盖前者):
    1. 默认值
    2. 继承链 (extends)
    3. 项目配置文件
    4. 环境变量
    """
    global _config_instance, _config_mtime, _config_path

    with _config_lock:
        target_path = _resolve_config_path(config_path)
        if target_path and target_path.exists():
            _config_path = target_path.resolve()
            mtime = _config_path.stat().st_mtime

            # 如果文件未变且已有缓存，直接返回
            if _config_instance is not None and mtime == _config_mtime:
                return _config_instance

            _config_instance, _config_mtime = _build_config_instance(target_path, mtime)
        else:
            # 无配置文件，使用默认值
            _config_instance = GovernanceConfig()
            _config_path = None
            _config_mtime = 0.0

        # 应用环境变量覆盖
        _config_instance = _apply_env_overrides(_config_instance)
        return _config_instance


def _resolve_config_path(config_path: Path | str | None) -> Path | None:
    """解析配置文件路径 (config_path or DEFAULT_CONFIG_PATHS 第一个存在, 模块级 helper).

    Args:
        config_path: 显式指定路径 (None 时走默认)

    Returns:
        解析后 Path, 不存在返回 None
    """
    if config_path:
        return Path(config_path)
    for p in DEFAULT_CONFIG_PATHS:
        if p.exists():
            return p
    return None


def _build_config_instance(target_path: Path, mtime: float) -> tuple[GovernanceConfig, float]:
    """构造 GovernanceConfig + 更新 mtime (模块级 helper).

    处理 yaml/toml/cfg 三种格式 + 继承链 + dict → config 转换.

    Args:
        target_path: 配置文件路径
        mtime: 文件修改时间

    Returns:
        (config_instance, mtime) 元组
    """
    config_dict = _load_config_dict(target_path)
    if config_dict:
        config_dict = _resolve_extends(config_dict, target_path.parent)
        instance = _dict_to_config(config_dict)
    else:
        instance = GovernanceConfig()
    return instance, mtime


def _load_config_dict(target_path: Path) -> dict[str, Any] | None:
    """按后缀加载配置字典 (模块级 helper).

    Args:
        target_path: 配置文件路径

    Returns:
        配置字典, 未知后缀返回 {}
    """
    if target_path.suffix in (".yaml", ".yml"):
        return _load_yaml_file(target_path)
    if target_path.suffix == ".toml":
        return _load_toml_config(target_path)
    if target_path.suffix == ".cfg":
        return _load_cfg_config(target_path)
    return None


def get_config() -> GovernanceConfig:
    """获取当前配置 (懒加载)"""
    if _config_instance is None:
        return load_config()
    return _config_instance


def reload_config() -> GovernanceConfig:
    """强制重新加载配置"""
    global _config_mtime
    _config_mtime = 0.0
    return load_config()


def watch_config(callback: Callable[[], None], interval: float = 1.0) -> threading.Thread:
    """监听配置文件变化，变化时调用 callback

    返回监听线程，调用者需自行管理生命周期
    """

    def watcher() -> None:
        last_mtime = 0.0
        while True:
            if _config_path and _config_path.exists():
                mtime = _config_path.stat().st_mtime
                if mtime != last_mtime:
                    last_mtime = mtime
                    reload_config()
                    callback()
            threading.Event().wait(interval)

    thread = threading.Thread(target=watcher, daemon=True)
    thread.start()
    return thread


def create_default_config(output_path: Path) -> None:
    """生成默认配置文件模板"""
    default = GovernanceConfig()
    data = _dataclass_to_dict(default)
    data["version"] = 1
    data["extends"] = []

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, allow_unicode=True, sort_keys=False)

    print(f"✅ 默认配置已生成: {output_path}")

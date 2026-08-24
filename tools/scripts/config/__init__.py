"""
配置管理系统

支持:
- YAML 配置文件 (.jcode/governance.yaml)
- 继承链 (extends: [base, team, org])
- 环境变量覆盖 (JCODE_GOVERNANCE_*)
- Schema 验证
- 热重载
"""

from .loader import create_default_config, get_config, load_config, reload_config
from .models import (
    BaselineConfig,
    ExceptionRule,
    GovernanceConfig,
    LanguageConfig,
    QualityGateConfig,
    SeverityLevel,
    ToolCategory,
    ToolConfig,
)

__all__ = [
    "load_config",
    "get_config",
    "reload_config",
    "create_default_config",
    "GovernanceConfig",
    "LanguageConfig",
    "ToolConfig",
    "SeverityLevel",
    "ToolCategory",
    "ExceptionRule",
    "QualityGateConfig",
    "BaselineConfig",
]

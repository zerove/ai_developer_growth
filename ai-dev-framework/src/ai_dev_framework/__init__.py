"""
ai-dev-framework — AI Agent 开发治理框架

适用于任何项目的 AI Agent 开发治理标准。
提供参数化配置、钩子系统、初始化工具。
"""

from ai_dev_framework.hook_system import (
    Hook,
    HookConfig,
    HookExecutor,
    create_default_config,
)
from ai_dev_framework.jcode_init import init_jcode
from ai_dev_framework.project_config import (
    AgentConfig,
    JcodeConfig,
    ProjectConfig,
    init_project,
)

__version__ = "0.1.0"
__all__ = [
    "JcodeConfig",
    "ProjectConfig",
    "AgentConfig",
    "HookConfig",
    "Hook",
    "HookExecutor",
    "create_default_config",
    "init_project",
    "init_jcode",
]

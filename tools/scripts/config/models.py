"""
配置数据模型

定义 governance.yaml 的完整结构，支持 Pydantic 验证。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SeverityLevel(str, Enum):
    """严重性级别"""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


class ToolCategory(str, Enum):
    """工具类别"""

    LINT = "lint"
    TYPECHECK = "typecheck"
    TEST = "test"
    SECURITY = "security"
    FORMAT = "format"
    BUILD = "build"
    PACKAGE = "package"
    DEPS = "deps"
    SECRETS = "secrets"
    LICENSE = "license"


@dataclass
class ToolConfig:
    """单个工具配置"""

    command: str
    args: list[str] = field(default_factory=list)
    fix_args: list[str] | None = None
    check_args: list[str] | None = None
    config_file: str | None = None
    install_hint: str | None = None
    version_flag: str = "--version"
    severity_threshold: SeverityLevel = SeverityLevel.WARNING
    exclude: list[str] = field(default_factory=list)
    include: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    timeout: int = 300
    enabled: bool = True


@dataclass
class LanguageConfig:
    """语言级配置"""

    # 覆盖默认工具链
    tools: dict[ToolCategory, ToolConfig] = field(default_factory=dict)
    # 语言特定的默认路径
    paths: dict[str, str] = field(default_factory=dict)
    # 语言特定的阈值
    thresholds: dict[str, Any] = field(default_factory=dict)
    # 启用/禁用该语言
    enabled: bool = True


@dataclass
class ExceptionRule:
    """例外规则"""

    id: str  # 唯一标识
    rule: str  # 规则 ID (如 "PL-R0913", "no-unused-vars")
    paths: list[str] = field(default_factory=list)  # glob 模式
    reason: str = ""  # 业务理由
    expires: str | None = None  # ISO 日期，过期自动失效
    severity: SeverityLevel = SeverityLevel.WARNING  # 降级后的严重性
    created_by: str = ""
    created_at: str = ""
    approved_by: str = ""
    approved_at: str = ""


@dataclass
class QualityGateConfig:
    """质量门禁配置"""

    name: str = "default"
    # 门禁规则
    require_zero_new_errors: bool = True
    require_zero_new_warnings: bool = False
    max_new_errors: int = 0
    max_new_warnings: int = 10
    # 覆盖率要求
    min_coverage_overall: float = 0.0
    min_coverage_changed: float = 0.0
    # 安全要求
    max_critical_vulns: int = 0
    max_high_vulns: int = 0
    # 秘钥要求
    allow_secrets: bool = False
    # 许可证要求
    allowed_licenses: list[str] = field(default_factory=list)
    denied_licenses: list[str] = field(default_factory=list)
    # 例外处理
    allow_exceptions: bool = True
    require_approval_for_exceptions: bool = True
    # 基线分支
    baseline_branch: str = "main"


@dataclass
class BaselineConfig:
    """基线配置"""

    enabled: bool = True
    # 双 schema 路径分离: 此文件存 quality-gate 的 issue 详情 (schema A,
    # files 值为 dict); 棘轮计数基线 (schema B, files 值为 int) 仍使用
    # .jcode/baseline.json。两者曾共用同一路径导致交叉读取崩溃, 故默认路径分开。
    path: str = ".jcode/quality-gate-baseline.json"
    auto_update: bool = False
    update_on_success: bool = True
    # 基线比较选项
    compare_against: str = "baseline"  # baseline | main | previous-run
    fail_on_new: bool = True
    fail_on_worsened: bool = True


@dataclass
class SecretScanConfig:
    """秘钥扫描配置"""

    enabled: bool = True
    tools: list[str] = field(default_factory=lambda: ["gitleaks", "trufflehog"])
    # 扫描范围
    scan_workspace: bool = True
    scan_git_history: bool = True
    scan_pr_diff: bool = True
    scan_containers: bool = False
    # 规则
    rules: list[str] = field(default_factory=list)  # 自定义规则文件
    allowlist: list[str] = field(default_factory=list)  # 允许列表路径/模式
    # 验证
    verify_active: bool = False  # 尝试验证密钥活性
    entropy_threshold: float = 4.5


@dataclass
class SupplyChainConfig:
    """供应链安全配置"""

    enabled: bool = True
    # 漏洞源
    vulnerability_sources: list[str] = field(default_factory=lambda: ["osv", "ghsa", "nvd"])
    # 严重性阈值
    max_critical: int = 0
    max_high: int = 5
    max_medium: int = 20
    # 许可证
    allowed_licenses: list[str] = field(
        default_factory=lambda: ["MIT", "Apache-2.0", "BSD-3-Clause", "BSD-2-Clause", "ISC", "Python-2.0"]
    )
    denied_licenses: list[str] = field(default_factory=lambda: ["GPL-3.0", "AGPL-3.0", "SSPL-1.0"])
    # SBOM
    generate_sbom: bool = True
    sbom_format: str = "cyclonedx"  # cyclonedx | spdx
    sbom_output: str = "sbom.json"
    # 签名验证
    verify_signatures: bool = False
    trusted_publishers: list[str] = field(default_factory=list)


@dataclass
class CacheConfig:
    """缓存配置"""

    enabled: bool = True
    path: str = ".jcode/cache"
    max_size_mb: int = 500
    ttl_hours: int = 168  # 7天
    # 缓存键包含
    key_factors: list[str] = field(default_factory=lambda: ["file_hash", "tool_version", "config_hash"])


@dataclass
class ParallelConfig:
    """并行执行配置"""

    enabled: bool = True
    max_workers: int = 4
    # 每类检查的并行度
    per_category: dict[ToolCategory, int] = field(default_factory=dict)


@dataclass
class OutputConfig:
    """输出配置"""

    format: str = "text"  # text | json | sarif | junit
    sarif_output: str | None = None
    junit_output: str | None = None
    verbose: bool = False
    show_passed: bool = False
    summary_only: bool = False


@dataclass
class GitHooksConfig:
    """Git Hooks 配置"""

    pre_commit: bool = True
    pre_push: bool = False
    commit_msg: bool = False
    prepare_commit_msg: bool = False
    # Hook 行为
    run_on_partial_staging: bool = True
    skip_on_merge_commit: bool = True
    skip_on_fixup_commit: bool = True


@dataclass
class MetricsConfig:
    """度量配置"""

    enabled: bool = True
    db_path: str = "adg_quality.db"
    # 导出
    prometheus_port: int | None = None
    push_gateway: str | None = None
    # 保留
    retention_days: int = 90


@dataclass
class GovernanceConfig:
    """根配置"""

    version: int = 1
    extends: list[str] = field(default_factory=list)
    # 语言配置
    languages: dict[str, LanguageConfig] = field(default_factory=dict)
    # 全局工具默认值（可被语言覆盖）
    default_tools: dict[ToolCategory, ToolConfig] = field(default_factory=dict)
    # 例外规则
    exceptions: list[ExceptionRule] = field(default_factory=list)
    # 质量门禁
    quality_gates: dict[str, QualityGateConfig] = field(default_factory=dict)
    # 基线
    baseline: BaselineConfig = field(default_factory=BaselineConfig)
    # 秘钥扫描
    secrets: SecretScanConfig = field(default_factory=SecretScanConfig)
    # 供应链
    supply_chain: SupplyChainConfig = field(default_factory=SupplyChainConfig)
    # 缓存
    cache: CacheConfig = field(default_factory=CacheConfig)
    # 并行
    parallel: ParallelConfig = field(default_factory=ParallelConfig)
    # 输出
    output: OutputConfig = field(default_factory=OutputConfig)
    # Git Hooks
    git_hooks: GitHooksConfig = field(default_factory=GitHooksConfig)
    # 度量
    metrics: MetricsConfig = field(default_factory=MetricsConfig)
    # 自定义扩展
    custom: dict[str, Any] = field(default_factory=dict)


# 默认配置常量
DEFAULT_CONFIG_PATHS = [
    Path(".jcode/governance.yaml"),
    Path(".jcode/governance.yml"),
    Path("pyproject.toml"),  # [tool.jcode.governance]
    Path("setup.cfg"),  # [jcode:governance]
]

DEFAULT_BASELINE_PATH = Path(".jcode/baseline.json")
DEFAULT_CACHE_DIR = Path(".jcode/cache")

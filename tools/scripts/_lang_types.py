"""语言工具链注册表 - 类型定义

定义语言枚举、工具类别、工具配置与语言工具链数据类。
"""

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Language(StrEnum):
    """支持的编程语言"""

    PYTHON = "python"
    TYPESCRIPT = "typescript"
    JAVASCRIPT = "javascript"
    RUST = "rust"
    GO = "go"
    JAVA = "java"
    CPP = "cpp"
    CSHARP = "csharp"
    RUBY = "ruby"
    PHP = "php"
    SWIFT = "swift"
    KOTLIN = "kotlin"
    SCALA = "scala"
    R = "r"
    LUA = "lua"
    DART = "dart"
    ZIG = "zig"
    ELIXIR = "elixir"
    CLOJURE = "clojure"
    HASKELL = "haskell"
    OCAML = "ocaml"
    FSHARP = "fsharp"
    PERL = "perl"
    SHELL = "shell"
    SQL = "sql"


class ToolCategory(StrEnum):
    """工具类别"""

    FORMAT = "format"
    LINT = "lint"
    TYPECHECK = "typecheck"
    TEST = "test"
    SECURITY = "security"
    DEPS = "deps"
    DOCS = "docs"
    GENERATE = "generate"
    BUILD = "build"
    PACKAGE = "package"


@dataclass
class ToolConfig:
    """单个工具配置"""

    command: str  # 命令名或路径
    args: list[str] = field(default_factory=list)  # 默认参数
    check_args: list[str] = field(default_factory=list)  # 仅检查模式参数
    fix_args: list[str] = field(default_factory=list)  # 自动修复参数
    coverage_args: list[str] = field(default_factory=list)  # 覆盖率参数
    config_file: str | None = None  # 配置文件名
    install_hint: str = ""  # 安装提示
    version_flag: str = "--version"  # 版本检查参数
    available: bool = True  # 是否可用(运行时检测)


@dataclass
class LanguageToolchain:
    """语言完整工具链"""

    language: Language
    version: str = ""  # 语言版本要求
    runtime: str = ""  # 运行时

    # 核心工具
    format: ToolConfig | None = None
    lint: ToolConfig | None = None
    typecheck: ToolConfig | None = None
    test: ToolConfig | None = None
    security: ToolConfig | None = None
    deps: ToolConfig | None = None
    docs: ToolConfig | None = None
    generate: ToolConfig | None = None
    build: ToolConfig | None = None
    package: ToolConfig | None = None

    # 文件扩展名
    extensions: list[str] = field(default_factory=list)

    # 典型项目结构
    default_paths: dict[str, str] = field(default_factory=dict)

    # 默认阈值
    default_thresholds: dict[str, Any] = field(default_factory=dict)

    # 包管理器
    package_manager: str = ""
    lock_file: str = ""

    # 入口文件模式
    entry_patterns: list[str] = field(default_factory=list)

    # 测试文件模式
    test_patterns: list[str] = field(default_factory=list)

    # 配置文件模式
    config_patterns: list[str] = field(default_factory=list)

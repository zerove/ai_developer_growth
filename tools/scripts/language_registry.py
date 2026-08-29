#!/usr/bin/env python3
"""
语言工具链注册表

定义各语言的标准工具链映射，支持动态加载和扩展。
所有 JCode 技能通过此注册表获取语言对应的工具命令。
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, cast


class Language(str, Enum):
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


class ToolCategory(str, Enum):
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


# ============================================================================
# 内置工具链定义
# ============================================================================

# Python
PYTHON_TOOLCHAIN = LanguageToolchain(
    language=Language.PYTHON,
    version=">=3.11",
    runtime="cpython",
    extensions=[".py", ".pyi", ".pyx", ".pxd", ".pxi"],
    package_manager="pip",
    lock_file="requirements.lock",
    entry_patterns=["main.py", "app.py", "run.py", "cli.py", "__main__.py"],
    test_patterns=["test_*.py", "*_test.py", "tests/**/*.py"],
    config_patterns=["pyproject.toml", "setup.py", "setup.cfg", "requirements.txt", "Pipfile", "poetry.lock"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
        "config": "config",
        "scripts": "scripts",
    },
    default_thresholds={
        "coverage_overall": 60,
        "coverage_per_file": 50,
        "complexity_cyclomatic": 10,
        "complexity_cognitive": 15,
        "naming_style": "snake_case",
    },
    format=ToolConfig(
        command="ruff",
        args=["format"],
        check_args=["format", "--check"],
        config_file="pyproject.toml",
        install_hint="pip install ruff",
    ),
    lint=ToolConfig(
        command="ruff",
        args=["check"],
        fix_args=["check", "--fix"],
        config_file="pyproject.toml",
        install_hint="pip install ruff",
    ),
    typecheck=ToolConfig(
        command="mypy",
        args=["--config-file", "pyproject.toml", "tools/scripts"],
        config_file="pyproject.toml",
        install_hint="pip install mypy",
    ),
    test=ToolConfig(
        command="pytest",
        args=["-v", "--tb=short"],
        coverage_args=["--cov", "--cov-report=term-missing", "--cov-report=xml"],
        config_file="pyproject.toml",
        install_hint="pip install pytest pytest-cov",
    ),
    security=ToolConfig(
        command="bandit",
        args=["-r", ".", "-f", "json", "-o", "bandit-report.json", "-c", "pyproject.toml", "--severity-level", "high"],
        config_file="pyproject.toml",
        install_hint="pip install bandit",
    ),
    deps=ToolConfig(
        command="pip-audit",
        args=["--desc"],
        install_hint="pip install pip-audit",
    ),
    docs=ToolConfig(
        command="sphinx-build",
        args=["-b", "html", "docs", "docs/_build"],
        config_file="docs/conf.py",
        install_hint="pip install sphinx",
    ),
    build=ToolConfig(
        command="python",
        args=["-m", "build"],
        install_hint="pip install build",
    ),
    package=ToolConfig(
        command="pip",
        args=["install", "-e", "."],
        install_hint="pip install pip",
    ),
)

# TypeScript/JavaScript
TYPESCRIPT_TOOLCHAIN = LanguageToolchain(
    language=Language.TYPESCRIPT,
    version=">=5.0",
    runtime="node",
    extensions=[".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"],
    package_manager="npm",
    lock_file="package-lock.json",
    entry_patterns=["main.ts", "index.ts", "app.ts", "cli.ts"],
    test_patterns=["**/*.test.ts", "**/*.spec.ts", "**/__tests__/**/*.ts"],
    config_patterns=["tsconfig.json", "package.json", "eslint.config.js", "prettier.config.js"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
        "config": "config",
    },
    default_thresholds={
        "coverage_overall": 70,
        "coverage_per_file": 60,
        "complexity_cyclomatic": 10,
        "naming_style": "camelCase",
    },
    format=ToolConfig(
        command="prettier",
        args=["--write"],
        check_args=["--check"],
        config_file="prettier.config.js",
        install_hint="npm install -D prettier",
    ),
    lint=ToolConfig(
        command="eslint",
        args=["."],
        fix_args=[".", "--fix"],
        config_file="eslint.config.js",
        install_hint="npm install -D eslint",
    ),
    typecheck=ToolConfig(
        command="tsc",
        args=["--noEmit"],
        config_file="tsconfig.json",
        install_hint="npm install -D typescript",
    ),
    test=ToolConfig(
        command="vitest",
        args=["run"],
        coverage_args=["run", "--coverage"],
        config_file="vitest.config.ts",
        install_hint="npm install -D vitest @vitest/coverage-v8",
    ),
    security=ToolConfig(
        command="npm",
        args=["audit", "--json"],
        install_hint="npm install -D npm-audit",
    ),
    deps=ToolConfig(
        command="npm",
        args=["outdated", "--json"],
        install_hint="npm install -D npm-outdated",
    ),
    docs=ToolConfig(
        command="typedoc",
        args=["--out", "docs/api", "src"],
        config_file="typedoc.json",
        install_hint="npm install -D typedoc",
    ),
    build=ToolConfig(
        command="tsc",
        args=[],
        config_file="tsconfig.json",
    ),
    package=ToolConfig(
        command="npm",
        args=["pack"],
    ),
)

JAVASCRIPT_TOOLCHAIN = LanguageToolchain(
    language=Language.JAVASCRIPT,
    version=">=18.0",
    runtime="node",
    extensions=[".js", ".jsx", ".mjs", ".cjs"],
    package_manager="npm",
    lock_file="package-lock.json",
    entry_patterns=["main.js", "index.js", "app.js", "cli.js"],
    test_patterns=["**/*.test.js", "**/*.spec.js", "**/__tests__/**/*.js"],
    config_patterns=["package.json", "eslint.config.js", "prettier.config.js"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
    },
    default_thresholds={
        "coverage_overall": 70,
        "naming_style": "camelCase",
    },
    format=ToolConfig(
        command="prettier",
        args=["--write"],
        check_args=["--check"],
        config_file="prettier.config.js",
        install_hint="npm install -D prettier",
    ),
    lint=ToolConfig(
        command="eslint",
        args=["."],
        fix_args=[".", "--fix"],
        config_file="eslint.config.js",
        install_hint="npm install -D eslint",
    ),
    test=ToolConfig(
        command="vitest",
        args=["run"],
        coverage_args=["run", "--coverage"],
        config_file="vitest.config.js",
        install_hint="npm install -D vitest @vitest/coverage-v8",
    ),
    security=ToolConfig(
        command="npm",
        args=["audit", "--json"],
    ),
    deps=ToolConfig(
        command="npm",
        args=["outdated", "--json"],
    ),
    docs=ToolConfig(
        command="jsdoc",
        args=["-c", "jsdoc.json"],
        config_file="jsdoc.json",
        install_hint="npm install -D jsdoc",
    ),
    build=ToolConfig(
        command="npm",
        args=["run", "build"],
    ),
    package=ToolConfig(
        command="npm",
        args=["pack"],
    ),
)

# Rust
RUST_TOOLCHAIN = LanguageToolchain(
    language=Language.RUST,
    version=">=1.70",
    runtime="rustc",
    extensions=[".rs"],
    package_manager="cargo",
    lock_file="Cargo.lock",
    entry_patterns=["src/main.rs", "src/bin/*.rs"],
    test_patterns=["tests/*.rs", "src/**/*_test.rs"],
    config_patterns=["Cargo.toml", "rustfmt.toml", "clippy.toml"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
        "examples": "examples",
        "benches": "benches",
    },
    default_thresholds={
        "coverage_overall": 70,
        "complexity_cyclomatic": 15,
        "naming_style": "snake_case",
    },
    format=ToolConfig(
        command="rustfmt",
        args=["--check"],
        fix_args=[],
        config_file="rustfmt.toml",
        install_hint="rustup component add rustfmt",
    ),
    lint=ToolConfig(
        command="cargo",
        args=["clippy", "--all-targets", "--all-features", "--", "-D", "warnings"],
        config_file="clippy.toml",
        install_hint="rustup component add clippy",
    ),
    typecheck=ToolConfig(
        command="cargo",
        args=["check", "--all-targets"],
    ),
    test=ToolConfig(
        command="cargo",
        args=["test", "--all-targets"],
        coverage_args=["llvm-cov", "--html"],
        install_hint="cargo install cargo-llvm-cov",
    ),
    security=ToolConfig(
        command="cargo",
        args=["audit"],
        install_hint="cargo install cargo-audit",
    ),
    deps=ToolConfig(
        command="cargo",
        args=["outdated"],
        install_hint="cargo install cargo-outdated",
    ),
    docs=ToolConfig(
        command="cargo",
        args=["doc", "--no-deps", "--document-private-items"],
    ),
    build=ToolConfig(
        command="cargo",
        args=["build", "--release"],
    ),
    package=ToolConfig(
        command="cargo",
        args=["package"],
    ),
)

# Go
GO_TOOLCHAIN = LanguageToolchain(
    language=Language.GO,
    version=">=1.21",
    runtime="go",
    extensions=[".go"],
    package_manager="go mod",
    lock_file="go.sum",
    entry_patterns=["main.go", "cmd/**/main.go"],
    test_patterns=["**/*_test.go"],
    config_patterns=["go.mod", "go.sum", "golangci.yml"],
    default_paths={
        "src": ".",
        "tests": ".",
        "docs": "docs",
        "cmd": "cmd",
        "internal": "internal",
        "pkg": "pkg",
    },
    default_thresholds={
        "coverage_overall": 70,
        "complexity_cyclomatic": 10,
        "naming_style": "camelCase",
    },
    format=ToolConfig(
        command="gofmt",
        args=["-l", "."],
        fix_args=["-w", "."],
        install_hint="go install golang.org/x/tools/cmd/gofmt@latest",
    ),
    lint=ToolConfig(
        command="golangci-lint",
        args=["run"],
        fix_args=["run", "--fix"],
        config_file="golangci.yml",
        install_hint="go install github.com/golangci/golangci-lint/cmd/golangci-lint@latest",
    ),
    typecheck=ToolConfig(
        command="go",
        args=["vet", "./..."],
    ),
    test=ToolConfig(
        command="go",
        args=["test", "-v", "./..."],
        coverage_args=["test", "-coverprofile=coverage.out", "./..."],
    ),
    security=ToolConfig(
        command="gosec",
        args=["./..."],
        install_hint="go install github.com/securego/gosec/v2/cmd/gosec@latest",
    ),
    deps=ToolConfig(
        command="go",
        args=["list", "-m", "-u", "all"],
    ),
    docs=ToolConfig(
        command="go",
        args=["doc", "./..."],
    ),
    build=ToolConfig(
        command="go",
        args=["build", "./..."],
    ),
    package=ToolConfig(
        command="go",
        args=["mod", "tidy"],
    ),
)

# Java
JAVA_TOOLCHAIN = LanguageToolchain(
    language=Language.JAVA,
    version=">=17",
    runtime="jvm",
    extensions=[".java", ".kt", ".groovy", ".scala"],
    package_manager="maven",
    lock_file="pom.xml",
    entry_patterns=["src/main/java/**/Main.java", "src/main/kotlin/**/Main.kt"],
    test_patterns=["src/test/**/*Test.java", "src/test/**/*Spec.kt"],
    config_patterns=["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle"],
    default_paths={
        "src": "src/main",
        "tests": "src/test",
        "docs": "docs",
    },
    default_thresholds={
        "coverage_overall": 70,
        "complexity_cyclomatic": 10,
        "naming_style": "camelCase",
    },
    format=ToolConfig(
        command="google-java-format",
        args=["--dry-run"],
        fix_args=["--replace"],
        install_hint="https://github.com/google/google-java-format",
    ),
    lint=ToolConfig(
        command="spotbugs",
        args=["-textui"],
        install_hint="https://spotbugs.github.io/",
    ),
    typecheck=ToolConfig(
        command="javac",
        args=["-Xlint:all"],
    ),
    test=ToolConfig(
        command="mvn",
        args=["test"],
        coverage_args=["test", "jacoco:report"],
    ),
    security=ToolConfig(
        command="mvn",
        args=["org.owasp:dependency-check-maven:check"],
    ),
    deps=ToolConfig(
        command="mvn",
        args=["versions:display-dependency-updates"],
    ),
    docs=ToolConfig(
        command="mvn",
        args=["javadoc:javadoc"],
    ),
    build=ToolConfig(
        command="mvn",
        args=["package", "-DskipTests"],
    ),
    package=ToolConfig(
        command="mvn",
        args=["install", "-DskipTests"],
    ),
)

# C/C++
CPP_TOOLCHAIN = LanguageToolchain(
    language=Language.CPP,
    version=">=17",
    runtime="native",
    extensions=[".cpp", ".cc", ".cxx", ".c", ".h", ".hpp", ".hxx"],
    package_manager="conan",
    lock_file="conan.lock",
    entry_patterns=["src/main.cpp", "src/main.c", "app.cpp"],
    test_patterns=["test/**/*.cpp", "**/*_test.cpp", "**/*Test.cpp"],
    config_patterns=["CMakeLists.txt", "meson.build", "Makefile", "conanfile.txt", "vcpkg.json"],
    default_paths={
        "src": "src",
        "tests": "test",
        "docs": "docs",
        "include": "include",
    },
    default_thresholds={
        "coverage_overall": 60,
        "complexity_cyclomatic": 15,
        "naming_style": "snake_case",
    },
    format=ToolConfig(
        command="clang-format",
        args=["-i"],
        check_args=["--dry-run", "-Werror"],
        config_file=".clang-format",
        install_hint="apt install clang-format",
    ),
    lint=ToolConfig(
        command="clang-tidy",
        args=["-p", "build"],
        config_file=".clang-tidy",
        install_hint="apt install clang-tidy",
    ),
    typecheck=ToolConfig(
        command="cppcheck",
        args=["--enable=all", "--std=c++17"],
        install_hint="apt install cppcheck",
    ),
    test=ToolConfig(
        command="ctest",
        args=["--output-on-failure"],
        coverage_args=["--coverage"],
        install_hint="apt install cmake lcov",
    ),
    security=ToolConfig(
        command="flawfinder",
        args=["."],
        install_hint="pip install flawfinder",
    ),
    build=ToolConfig(
        command="cmake",
        args=["--build", "build", "--config", "Release"],
    ),
    package=ToolConfig(
        command="cpack",
        args=["-G", "TGZ"],
    ),
)

# C#
CSHARP_TOOLCHAIN = LanguageToolchain(
    language=Language.CSHARP,
    version=">=8.0",
    runtime="clr",
    extensions=[".cs", ".fs", ".vb"],
    package_manager="nuget",
    lock_file="packages.lock.json",
    entry_patterns=["**/Program.cs", "**/Main.cs"],
    test_patterns=["**/*Tests.cs", "**/*Test.cs", "**/*.Tests.cs"],
    config_patterns=["*.csproj", "*.sln", "Directory.Build.props", "nuget.config"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
    },
    default_thresholds={
        "coverage_overall": 70,
        "complexity_cyclomatic": 10,
        "naming_style": "PascalCase",
    },
    format=ToolConfig(
        command="dotnet",
        args=["format", "--verify-no-changes"],
        fix_args=["format"],
        install_hint="dotnet tool install -g dotnet-format",
    ),
    lint=ToolConfig(
        command="dotnet",
        args=["build", "--no-restore", "/p:WarningLevel=4", "/p:TreatWarningsAsErrors=true"],
    ),
    typecheck=ToolConfig(
        command="dotnet",
        args=["build", "--no-restore"],
    ),
    test=ToolConfig(
        command="dotnet",
        args=["test", "--no-build", "--logger:trx"],
        coverage_args=["test", "--collect:XPlat Code Coverage"],
    ),
    security=ToolConfig(
        command="dotnet",
        args=["list", "package", "--vulnerable", "--include-transitive"],
    ),
    deps=ToolConfig(
        command="dotnet",
        args=["list", "package", "--outdated"],
    ),
    docs=ToolConfig(
        command="dotnet",
        args=["doc", "build"],
    ),
    build=ToolConfig(
        command="dotnet",
        args=["build", "--configuration", "Release"],
    ),
    package=ToolConfig(
        command="dotnet",
        args=["pack", "--configuration", "Release"],
    ),
)

# Ruby
RUBY_TOOLCHAIN = LanguageToolchain(
    language=Language.RUBY,
    version=">=3.0",
    runtime="ruby",
    extensions=[".rb", ".rake", ".gemspec"],
    package_manager="bundler",
    lock_file="Gemfile.lock",
    entry_patterns=["bin/*", "exe/*", "main.rb"],
    test_patterns=["spec/**/*_spec.rb", "test/**/*_test.rb"],
    config_patterns=["Gemfile", ".rubocop.yml", "Rakefile", ".ruby-version"],
    default_paths={
        "src": "lib",
        "tests": "spec",
        "docs": "docs",
    },
    default_thresholds={
        "coverage_overall": 80,
        "naming_style": "snake_case",
    },
    format=ToolConfig(
        command="rubocop",
        args=["-a"],
        check_args=["--dry-run"],
        config_file=".rubocop.yml",
        install_hint="gem install rubocop",
    ),
    lint=ToolConfig(
        command="rubocop",
        args=[],
        fix_args=["-a"],
        config_file=".rubocop.yml",
    ),
    typecheck=ToolConfig(
        command="sorbet",
        args=[],
        config_file="sorbet/config",
        install_hint="gem install sorbet",
    ),
    test=ToolConfig(
        command="rspec",
        args=[],
        coverage_args=["--format", "RspecJunitFormatter", "--out", "coverage.xml"],
        install_hint="gem install rspec simplecov",
    ),
    security=ToolConfig(
        command="bundler-audit",
        args=["--update"],
        install_hint="gem install bundler-audit",
    ),
    deps=ToolConfig(
        command="bundle",
        args=["outdated"],
    ),
    docs=ToolConfig(
        command="yard",
        args=["doc"],
        install_hint="gem install yard",
    ),
    build=ToolConfig(
        command="gem",
        args=["build", "*.gemspec"],
    ),
    package=ToolConfig(
        command="gem",
        args=["push", "*.gem"],
    ),
)

# PHP
PHP_TOOLCHAIN = LanguageToolchain(
    language=Language.PHP,
    version=">=8.1",
    runtime="php",
    extensions=[".php", ".phtml", ".php8"],
    package_manager="composer",
    lock_file="composer.lock",
    entry_patterns=["public/index.php", "bin/console", "artisan"],
    test_patterns=["tests/**/*Test.php", "**/*Test.php"],
    config_patterns=["composer.json", "phpstan.neon", "psalm.xml", ".php-cs-fixer.php"],
    default_paths={
        "src": "src",
        "tests": "tests",
        "docs": "docs",
    },
    default_thresholds={
        "coverage_overall": 70,
        "naming_style": "camelCase",
    },
    format=ToolConfig(
        command="php-cs-fixer",
        args=["fix", "--dry-run", "--diff"],
        fix_args=["fix"],
        config_file=".php-cs-fixer.php",
        install_hint="composer require --dev friendsofphp/php-cs-fixer",
    ),
    lint=ToolConfig(
        command="phpstan",
        args=["analyse", "--level=5"],
        config_file="phpstan.neon",
        install_hint="composer require --dev phpstan/phpstan",
    ),
    typecheck=ToolConfig(
        command="psalm",
        args=["--show-info=true"],
        config_file="psalm.xml",
        install_hint="composer require --dev vimeo/psalm",
    ),
    test=ToolConfig(
        command="phpunit",
        args=["--coverage-text"],
        coverage_args=["--coverage-clover", "coverage.xml"],
        install_hint="composer require --dev phpunit/phpunit",
    ),
    security=ToolConfig(
        command="composer",
        args=["audit"],
    ),
    deps=ToolConfig(
        command="composer",
        args=["outdated", "--direct"],
    ),
    docs=ToolConfig(
        command="phpdoc",
        args=["run"],
        install_hint="composer require --dev phpdocumentor/phpdocumentor",
    ),
    build=ToolConfig(
        command="composer",
        args=["install", "--no-dev", "--optimize-autoloader"],
    ),
    package=ToolConfig(
        command="composer",
        args=["archive", "--format=zip"],
    ),
)

# Swift
SWIFT_TOOLCHAIN = LanguageToolchain(
    language=Language.SWIFT,
    version=">=5.7",
    runtime="swift",
    extensions=[".swift"],
    package_manager="swiftpm",
    lock_file="Package.resolved",
    entry_patterns=["Sources/**/main.swift", "main.swift"],
    test_patterns=["Tests/**/*Tests.swift"],
    config_patterns=["Package.swift", ".swiftlint.yml"],
    default_paths={"src": "Sources", "tests": "Tests", "docs": "Documentation"},
    default_thresholds={"coverage_overall": 70, "naming_style": "camelCase"},
    format=ToolConfig(
        command="swiftformat",
        args=["."],
        check_args=["--lint"],
        config_file=".swiftformat",
        install_hint="brew install swiftformat",
    ),
    lint=ToolConfig(
        command="swiftlint",
        args=["lint"],
        fix_args=["autocorrect"],
        config_file=".swiftlint.yml",
        install_hint="brew install swiftlint",
    ),
    typecheck=ToolConfig(
        command="swift",
        args=["build", "--dry-run"],
        install_hint="xcode-select --install",
    ),
    test=ToolConfig(
        command="swift",
        args=["test", "--parallel"],
        coverage_args=["test", "--enable-code-coverage"],
        install_hint="xcode-select --install",
    ),
    security=ToolConfig(
        command="swift",
        args=["package", "show-dependencies", "--format", "json"],
        install_hint="xcode-select --install",
    ),
    build=ToolConfig(
        command="swift",
        args=["build", "-c", "release"],
    ),
    package=ToolConfig(
        command="swift",
        args=["package", "archive-source"],
    ),
)

# Kotlin
KOTLIN_TOOLCHAIN = LanguageToolchain(
    language=Language.KOTLIN,
    version=">=1.9",
    runtime="jvm",
    extensions=[".kt", ".kts"],
    package_manager="gradle",
    lock_file="gradle.lockfile",
    entry_patterns=["src/main/kotlin/**/Main.kt", "src/main/kotlin/**/main.kt"],
    test_patterns=["src/test/**/*Test.kt", "src/test/**/*Spec.kt"],
    config_patterns=["build.gradle.kts", "settings.gradle.kts", "gradle.properties", "ktlint.yml", "detekt.yml"],
    default_paths={"src": "src/main/kotlin", "tests": "src/test/kotlin", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "camelCase"},
    format=ToolConfig(
        command="ktlint",
        args=["--format"],
        check_args=[],
        config_file="ktlint.yml",
        install_hint="https://github.com/pinterest/ktlint",
    ),
    lint=ToolConfig(
        command="detekt",
        args=["--config", "detekt.yml"],
        config_file="detekt.yml",
        install_hint="https://detekt.dev/",
    ),
    typecheck=ToolConfig(
        command="kotlinc",
        args=["-Xlint"],
        install_hint="https://kotlinlang.org/docs/command-line.html",
    ),
    test=ToolConfig(
        command="./gradlew",
        args=["test"],
        coverage_args=["jacocoTestReport"],
        install_hint="https://gradle.org/",
    ),
    security=ToolConfig(
        command="./gradlew",
        args=["dependencyCheckAnalyze"],
        install_hint="https://owasp.org/www-project-dependency-check/",
    ),
    build=ToolConfig(
        command="./gradlew",
        args=["build", "-x", "test"],
    ),
    package=ToolConfig(
        command="./gradlew",
        args=["jar"],
    ),
)

# Scala
SCALA_TOOLCHAIN = LanguageToolchain(
    language=Language.SCALA,
    version=">=3.3",
    runtime="jvm",
    extensions=[".scala", ".sc"],
    package_manager="sbt",
    lock_file="build.sbt.lock",
    entry_patterns=["src/main/scala/**/Main.scala"],
    test_patterns=["src/test/**/*Spec.scala", "src/test/**/*Test.scala"],
    config_patterns=["build.sbt", "project/build.properties", "scalafmt.conf"],
    default_paths={"src": "src/main/scala", "tests": "src/test/scala", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "camelCase"},
    format=ToolConfig(
        command="scalafmt",
        args=["--test"],
        fix_args=[],
        config_file="scalafmt.conf",
        install_hint="https://scalameta.org/scalafmt/",
    ),
    lint=ToolConfig(
        command="scalafix",
        args=["--check"],
        fix_args=["--rules"],
        install_hint="https://scalacenter.github.io/scalafix/",
    ),
    typecheck=ToolConfig(
        command="sbt",
        args=["compile"],
    ),
    test=ToolConfig(
        command="sbt",
        args=["test"],
        coverage_args=["coverage", "test", "coverageReport"],
        install_hint="https://www.scala-sbt.org/",
    ),
    security=ToolConfig(
        command="sbt",
        args=["dependencyCheck"],
        install_hint="https://owasp.org/www-project-dependency-check/",
    ),
    build=ToolConfig(
        command="sbt",
        args=["assembly"],
    ),
    package=ToolConfig(
        command="sbt",
        args=["package"],
    ),
)

# Dart
DART_TOOLCHAIN = LanguageToolchain(
    language=Language.DART,
    version=">=3.0",
    runtime="dart",
    extensions=[".dart"],
    package_manager="pub",
    lock_file="pubspec.lock",
    entry_patterns=["bin/main.dart", "lib/main.dart"],
    test_patterns=["test/**/*_test.dart"],
    config_patterns=["pubspec.yaml", "analysis_options.yaml"],
    default_paths={"src": "lib", "tests": "test", "docs": "docs"},
    default_thresholds={"coverage_overall": 80, "naming_style": "camelCase"},
    format=ToolConfig(
        command="dart",
        args=["format", "--set-exit-if-changed", "."],
        fix_args=["format", "."],
        install_hint="https://dart.dev/get-dart",
    ),
    lint=ToolConfig(
        command="dart",
        args=["analyze", "--fatal-infos"],
        config_file="analysis_options.yaml",
        install_hint="https://dart.dev/get-dart",
    ),
    typecheck=ToolConfig(
        command="dart",
        args=["analyze"],
        config_file="analysis_options.yaml",
    ),
    test=ToolConfig(
        command="dart",
        args=["test", "--reporter=expanded"],
        coverage_args=["test", "--coverage=coverage"],
        install_hint="https://dart.dev/get-dart",
    ),
    security=ToolConfig(
        command="dart",
        args=["pub", "deps", "--style=compact"],
        install_hint="https://dart.dev/get-dart",
    ),
    build=ToolConfig(
        command="dart",
        args=["compile", "exe", "bin/main.dart"],
    ),
    package=ToolConfig(
        command="dart",
        args=["pub", "publish", "--dry-run"],
    ),
)

# Zig
ZIG_TOOLCHAIN = LanguageToolchain(
    language=Language.ZIG,
    version=">=0.11",
    runtime="zig",
    extensions=[".zig"],
    package_manager="zig",
    lock_file="zig.lock",
    entry_patterns=["src/main.zig", "src/root.zig"],
    test_patterns=["src/**/*_test.zig", "tests/**/*.zig"],
    config_patterns=["build.zig", "build.zig.zon"],
    default_paths={"src": "src", "tests": "tests", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "snake_case"},
    format=ToolConfig(
        command="zig",
        args=["fmt", "--check", "src"],
        fix_args=["fmt", "src"],
        install_hint="https://ziglang.org/download/",
    ),
    lint=ToolConfig(
        command="zig",
        args=["build", "check"],
        config_file="build.zig",
    ),
    typecheck=ToolConfig(
        command="zig",
        args=["build", "check"],
        config_file="build.zig",
    ),
    test=ToolConfig(
        command="zig",
        args=["test", "--summary", "all"],
        coverage_args=["test", "--coverage"],
        config_file="build.zig",
    ),
    security=ToolConfig(
        command="zig",
        args=["build", "check"],
        config_file="build.zig",
    ),
    build=ToolConfig(
        command="zig",
        args=["build", "-Doptimize=ReleaseFast"],
        config_file="build.zig",
    ),
    package=ToolConfig(
        command="zig",
        args=["build", "install"],
        config_file="build.zig",
    ),
)

# Elixir
ELIXIR_TOOLCHAIN = LanguageToolchain(
    language=Language.ELIXIR,
    version=">=1.15",
    runtime="beam",
    extensions=[".ex", ".exs", ".eex", ".leex"],
    package_manager="mix",
    lock_file="mix.lock",
    entry_patterns=["lib/**/application.ex", "mix.exs"],
    test_patterns=["test/**/*_test.exs"],
    config_patterns=["mix.exs", ".formatter.exs", "credo_config.exs"],
    default_paths={"src": "lib", "tests": "test", "docs": "docs"},
    default_thresholds={"coverage_overall": 80, "naming_style": "snake_case"},
    format=ToolConfig(
        command="mix",
        args=["format", "--check-formatted"],
        fix_args=["format"],
        config_file=".formatter.exs",
        install_hint="mix archive.install hex mix_format",
    ),
    lint=ToolConfig(
        command="mix",
        args=["credo", "--strict"],
        config_file="credo_config.exs",
        install_hint="mix archive.install hex credo",
    ),
    typecheck=ToolConfig(
        command="mix",
        args=["dialyzer"],
        install_hint="mix archive.install hex dialyxir",
    ),
    test=ToolConfig(
        command="mix",
        args=["test", "--trace"],
        coverage_args=["test", "--cover"],
        install_hint="https://elixir-lang.org/install.html",
    ),
    security=ToolConfig(
        command="mix",
        args=["deps.audit"],
        install_hint="mix archive.install hex mix_audit",
    ),
    build=ToolConfig(
        command="mix",
        args=["compile", "--warnings-as-errors"],
    ),
    package=ToolConfig(
        command="mix",
        args=["hex.publish"],
    ),
)

# Clojure
CLOJURE_TOOLCHAIN = LanguageToolchain(
    language=Language.CLOJURE,
    version=">=1.11",
    runtime="jvm",
    extensions=[".clj", ".cljs", ".cljc", ".edn"],
    package_manager="clojure",
    lock_file="deps.edn",
    entry_patterns=["src/**/core.clj", "src/**/main.clj"],
    test_patterns=["test/**/*_test.clj", "test/**/*_spec.clj"],
    config_patterns=["deps.edn", "shadow-cljs.edn", "cljfmt.edn"],
    default_paths={"src": "src", "tests": "test", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "kebab-case"},
    format=ToolConfig(
        command="cljfmt",
        args=["check"],
        fix_args=["fix"],
        config_file="cljfmt.edn",
        install_hint="https://github.com/weavejester/cljfmt",
    ),
    lint=ToolConfig(
        command="clj-kondo",
        args=["--lint", "src"],
        config_file=".clj-kondo/config.edn",
        install_hint="https://github.com/clj-kondo/clj-kondo",
    ),
    typecheck=ToolConfig(
        command="clojure",
        args=["-M:check"],
        install_hint="https://clojure.org/guides/getting_started",
    ),
    test=ToolConfig(
        command="clojure",
        args=["-M:test"],
        coverage_args=["-M:test", "--coverage"],
        install_hint="https://clojure.org/guides/getting_started",
    ),
    security=ToolConfig(
        command="clojure",
        args=["-M:audit"],
        install_hint="https://github.com/clj-commons/antiquarian",
    ),
    build=ToolConfig(
        command="clojure",
        args=["-M:build"],
    ),
    package=ToolConfig(
        command="clojure",
        args=["-M:jar"],
    ),
)

# Haskell
HASKELL_TOOLCHAIN = LanguageToolchain(
    language=Language.HASKELL,
    version=">=9.6",
    runtime="ghc",
    extensions=[".hs", ".lhs", ".cabal"],
    package_manager="cabal",
    lock_file="cabal.project.freeze",
    entry_patterns=["app/Main.hs", "src/Main.hs"],
    test_patterns=["test/**/*Spec.hs", "test/**/*Test.hs"],
    config_patterns=["*.cabal", "cabal.project", "hlint.yaml", "ormolu.yaml"],
    default_paths={"src": "src", "tests": "test", "app": "app", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "camelCase"},
    format=ToolConfig(
        command="ormolu",
        args=["--mode", "check"],
        fix_args=["--mode", "inplace"],
        config_file="ormolu.yaml",
        install_hint="cabal install ormolu",
    ),
    lint=ToolConfig(
        command="hlint",
        args=["."],
        config_file="hlint.yaml",
        install_hint="cabal install hlint",
    ),
    typecheck=ToolConfig(
        command="cabal",
        args=["build", "--dry-run"],
        install_hint="https://www.haskell.org/cabal/",
    ),
    test=ToolConfig(
        command="cabal",
        args=["test", "--test-show-details=direct"],
        coverage_args=["test", "--enable-coverage"],
        install_hint="https://www.haskell.org/cabal/",
    ),
    security=ToolConfig(
        command="cabal",
        args=["outdated"],
        install_hint="cabal install cabal-outdated",
    ),
    build=ToolConfig(
        command="cabal",
        args=["build", "all"],
    ),
    package=ToolConfig(
        command="cabal",
        args=["sdist"],
    ),
)

# F#
FSHARP_TOOLCHAIN = LanguageToolchain(
    language=Language.FSHARP,
    version=">=8.0",
    runtime="dotnet",
    extensions=[".fs", ".fsx", ".fsi"],
    package_manager="nuget",
    lock_file="paket.lock",
    entry_patterns=["src/**/Program.fs", "src/**/main.fs"],
    test_patterns=["tests/**/*Tests.fs", "tests/**/*Spec.fs"],
    config_patterns=["*.fsproj", "*.sln", "paket.dependencies", "paket.lock"],
    default_paths={"src": "src", "tests": "tests", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "PascalCase"},
    format=ToolConfig(
        command="dotnet",
        args=["format", "--verify-no-changes"],
        fix_args=["format"],
        install_hint="dotnet tool install -g fantomas-tool",
    ),
    lint=ToolConfig(
        command="dotnet",
        args=["build", "--no-restore", "/p:WarningLevel=4", "/p:TreatWarningsAsErrors=true"],
    ),
    typecheck=ToolConfig(
        command="dotnet",
        args=["build", "--no-restore"],
    ),
    test=ToolConfig(
        command="dotnet",
        args=["test", "--no-build", "--logger:trx"],
        coverage_args=["test", "--collect:XPlat Code Coverage"],
    ),
    security=ToolConfig(
        command="dotnet",
        args=["list", "package", "--vulnerable", "--include-transitive"],
    ),
    build=ToolConfig(
        command="dotnet",
        args=["build", "--configuration", "Release"],
    ),
    package=ToolConfig(
        command="dotnet",
        args=["pack", "--configuration", "Release"],
    ),
)

# Lua
LUA_TOOLCHAIN = LanguageToolchain(
    language=Language.LUA,
    version=">=5.4",
    runtime="lua",
    extensions=[".lua"],
    package_manager="luarocks",
    lock_file="lua-lock.json",
    entry_patterns=["main.lua", "init.lua", "src/main.lua"],
    test_patterns=["spec/**/*_spec.lua", "test/**/*_test.lua"],
    config_patterns=[".luacheckrc", "lua.toml", "rockspec"],
    default_paths={"src": "src", "tests": "spec", "docs": "docs"},
    default_thresholds={"coverage_overall": 70, "naming_style": "snake_case"},
    format=ToolConfig(
        command="stylua",
        args=["--check"],
        fix_args=[],
        config_file="stylua.toml",
        install_hint="cargo install stylua",
    ),
    lint=ToolConfig(
        command="luacheck",
        args=["."],
        config_file=".luacheckrc",
        install_hint="luarocks install luacheck",
    ),
    typecheck=ToolConfig(
        command="lua-language-server",
        args=["--check"],
        install_hint="https://github.com/LuaLS/lua-language-server",
    ),
    test=ToolConfig(
        command="busted",
        args=["-v"],
        coverage_args=["-c"],
        install_hint="luarocks install busted",
    ),
    security=ToolConfig(
        command="luarocks",
        args=["list", "--porcelain"],
        install_hint="https://luarocks.org/",
    ),
    build=ToolConfig(
        command="luarocks",
        args=["make"],
        install_hint="https://luarocks.org/",
    ),
    package=ToolConfig(
        command="luarocks",
        args=["pack"],
        install_hint="https://luarocks.org/",
    ),
)

# Shell
SHELL_TOOLCHAIN = LanguageToolchain(
    language=Language.SHELL,
    version=">=5.0",
    runtime="bash",
    extensions=[".sh", ".bash", ".zsh", ".fish"],
    package_manager="none",
    lock_file="",
    entry_patterns=["*.sh", "scripts/*.sh", "bin/*"],
    test_patterns=["test/**/*_test.sh", "tests/**/*_test.sh"],
    config_patterns=[".shellcheckrc", ".bash_aliases"],
    default_paths={"src": "scripts", "tests": "test", "docs": "docs"},
    default_thresholds={"coverage_overall": 50, "naming_style": "snake_case"},
    format=ToolConfig(
        command="shfmt",
        args=["-d"],
        fix_args=["-w"],
        config_file=".shfmtrc",
        install_hint="go install mvdan.cc/sh/v3/cmd/shfmt@latest",
    ),
    lint=ToolConfig(
        command="shellcheck",
        args=["-x", "-S", "warning", "."],
        config_file=".shellcheckrc",
        install_hint="apt install shellcheck",
    ),
    typecheck=ToolConfig(
        command="bash",
        args=["-n"],
        install_hint="apt install bash",
    ),
    test=ToolConfig(
        command="bats",
        args=["test"],
        coverage_args=[],
        install_hint="apt install bats",
    ),
    security=ToolConfig(
        command="shellcheck",
        args=["-x", "-S", "error", "."],
        config_file=".shellcheckrc",
    ),
    build=ToolConfig(
        command="true",
        args=[],
    ),
    package=ToolConfig(
        command="true",
        args=[],
    ),
)

# SQL
SQL_TOOLCHAIN = LanguageToolchain(
    language=Language.SQL,
    version="ansi",
    runtime="postgres",
    extensions=[".sql", ".ddl", ".dml"],
    package_manager="none",
    lock_file="",
    entry_patterns=["migrations/*.sql", "schema.sql"],
    test_patterns=["test/**/*.sql", "tests/**/*.sql"],
    config_patterns=[".sqlfluff", "sqlfluff.cfg"],
    default_paths={"src": "migrations", "tests": "test", "docs": "docs"},
    default_thresholds={"coverage_overall": 50, "naming_style": "snake_case"},
    format=ToolConfig(
        command="sqlfluff",
        args=["fix"],
        check_args=["lint"],
        config_file=".sqlfluff",
        install_hint="pip install sqlfluff",
    ),
    lint=ToolConfig(
        command="sqlfluff",
        args=["lint"],
        config_file=".sqlfluff",
        install_hint="pip install sqlfluff",
    ),
    typecheck=ToolConfig(
        command="sqlfluff",
        args=["parse"],
        config_file=".sqlfluff",
    ),
    test=ToolConfig(
        command="pg_prove",
        args=["-v"],
        install_hint="https://github.com/theory/pg_prove",
    ),
    security=ToolConfig(
        command="sqlfluff",
        args=["lint", "--rules", "security"],
        config_file=".sqlfluff",
    ),
    build=ToolConfig(
        command="true",
        args=[],
    ),
    package=ToolConfig(
        command="true",
        args=[],
    ),
)

# 所有工具链注册表
BUILTIN_TOOLCHAINS: dict[Language, LanguageToolchain] = {
    Language.PYTHON: PYTHON_TOOLCHAIN,
    Language.TYPESCRIPT: TYPESCRIPT_TOOLCHAIN,
    Language.JAVASCRIPT: JAVASCRIPT_TOOLCHAIN,
    Language.RUST: RUST_TOOLCHAIN,
    Language.GO: GO_TOOLCHAIN,
    Language.JAVA: JAVA_TOOLCHAIN,
    Language.CPP: CPP_TOOLCHAIN,
    Language.CSHARP: CSHARP_TOOLCHAIN,
    Language.RUBY: RUBY_TOOLCHAIN,
    Language.PHP: PHP_TOOLCHAIN,
    Language.SWIFT: SWIFT_TOOLCHAIN,
    Language.KOTLIN: KOTLIN_TOOLCHAIN,
    Language.SCALA: SCALA_TOOLCHAIN,
    Language.DART: DART_TOOLCHAIN,
    Language.ZIG: ZIG_TOOLCHAIN,
    Language.ELIXIR: ELIXIR_TOOLCHAIN,
    Language.CLOJURE: CLOJURE_TOOLCHAIN,
    Language.HASKELL: HASKELL_TOOLCHAIN,
    Language.FSHARP: FSHARP_TOOLCHAIN,
    Language.LUA: LUA_TOOLCHAIN,
    Language.SHELL: SHELL_TOOLCHAIN,
    Language.SQL: SQL_TOOLCHAIN,
}

# 别名映射
LANGUAGE_ALIASES: dict[str, Language] = {
    "py": Language.PYTHON,
    "python3": Language.PYTHON,
    "ts": Language.TYPESCRIPT,
    "typescript": Language.TYPESCRIPT,
    "js": Language.JAVASCRIPT,
    "javascript": Language.JAVASCRIPT,
    "rs": Language.RUST,
    "rust": Language.RUST,
    "golang": Language.GO,
    "go": Language.GO,
    "java": Language.JAVA,
    "c++": Language.CPP,
    "cpp": Language.CPP,
    "cc": Language.CPP,
    "cxx": Language.CPP,
    "c": Language.CPP,
    "csharp": Language.CSHARP,
    "cs": Language.CSHARP,
    "dotnet": Language.CSHARP,
    "rb": Language.RUBY,
    "ruby": Language.RUBY,
    "php": Language.PHP,
    "swift": Language.SWIFT,
    "kt": Language.KOTLIN,
    "kotlin": Language.KOTLIN,
    "scala": Language.SCALA,
    "r": Language.R,
    "lua": Language.LUA,
    "dart": Language.DART,
    "zig": Language.ZIG,
    "ex": Language.ELIXIR,
    "elixir": Language.ELIXIR,
    "clj": Language.CLOJURE,
    "clojure": Language.CLOJURE,
    "hs": Language.HASKELL,
    "haskell": Language.HASKELL,
    "ml": Language.OCAML,
    "ocaml": Language.OCAML,
    "fs": Language.FSHARP,
    "fsharp": Language.FSHARP,
    "pl": Language.PERL,
    "perl": Language.PERL,
    "sh": Language.SHELL,
    "bash": Language.SHELL,
    "zsh": Language.SHELL,
    "sql": Language.SQL,
}


# ============================================================================
# 注册表类
# ============================================================================


_CONFIG_FILE_LANGUAGES: dict[str, Language] = {
    "pyproject.toml": Language.PYTHON,
    "setup.py": Language.PYTHON,
    "requirements.txt": Language.PYTHON,
    "Pipfile": Language.PYTHON,
    "poetry.lock": Language.PYTHON,
    "tsconfig.json": Language.TYPESCRIPT,
    "package.json": Language.TYPESCRIPT,  # 可能是 JS 或 TS
    "Cargo.toml": Language.RUST,
    "go.mod": Language.GO,
    "pom.xml": Language.JAVA,
    "build.gradle": Language.JAVA,
    "build.gradle.kts": Language.KOTLIN,
    "settings.gradle.kts": Language.KOTLIN,
    "build.sbt": Language.SCALA,
    "CMakeLists.txt": Language.CPP,
    "meson.build": Language.CPP,
    "*.csproj": Language.CSHARP,
    "*.sln": Language.CSHARP,
    "Gemfile": Language.RUBY,
    "composer.json": Language.PHP,
    "Package.swift": Language.SWIFT,
    "pubspec.yaml": Language.DART,
    "build.zig": Language.ZIG,
    "mix.exs": Language.ELIXIR,
    "deps.edn": Language.CLOJURE,
    "*.cabal": Language.HASKELL,
    "cabal.project": Language.HASKELL,
    "paket.dependencies": Language.FSHARP,
    "*.fsproj": Language.FSHARP,
    ".luacheckrc": Language.LUA,
    "lua.toml": Language.LUA,
    ".sqlfluff": Language.SQL,
    "sqlfluff.cfg": Language.SQL,
}


class LanguageRegistry:
    """语言工具链注册表 - 单例"""

    _instance: "LanguageRegistry | None" = None
    _toolchains: dict[Language, LanguageToolchain]
    _custom_toolchains: dict[Language, LanguageToolchain]

    def __new__(cls) -> "LanguageRegistry":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._toolchains = dict(BUILTIN_TOOLCHAINS)
            cls._instance._custom_toolchains = {}
        return cls._instance

    def get(self, language: str | Language) -> LanguageToolchain | None:
        """获取工具链"""
        if isinstance(language, str):
            lang = LANGUAGE_ALIASES.get(language.lower())
            if lang is None:
                try:
                    lang = Language(language.lower())
                except ValueError:
                    return None
        else:
            lang = language

        # 优先返回自定义工具链
        if lang in self._custom_toolchains:
            return self._custom_toolchains[lang]
        return self._toolchains.get(lang)

    def get_tool(self, language: str | Language, category: ToolCategory) -> ToolConfig | None:
        """获取特定类别工具"""
        toolchain = self.get(language)
        if toolchain is None:
            return None
        return getattr(toolchain, category.value, None)

    def register(self, toolchain: LanguageToolchain) -> None:
        """注册自定义工具链"""
        self._custom_toolchains[toolchain.language] = toolchain

    def unregister(self, language: Language) -> bool:
        """注销自定义工具链"""
        if language in self._custom_toolchains:
            del self._custom_toolchains[language]
            return True
        return False

    def list_languages(self) -> list[Language]:
        """列出所有支持的语言"""
        all_langs = set(self._toolchains.keys()) | set(self._custom_toolchains.keys())
        return sorted(all_langs, key=lambda lang: lang.value)

    def _has_typescript_dependency(self, data: dict[str, object]) -> bool:
        """检查 devDependencies / dependencies 是否声明 typescript.

        V2.18 P3-15 拆分: 从 _detect_from_package_json (B=9) 抽出.
        """
        deps: dict[str, object] = {}
        for key in ("devDependencies", "dependencies"):
            section = data.get(key, {})
            if isinstance(section, dict):
                deps.update(cast("dict[str, object]", section))
        return "typescript" in deps

    def _has_typescript_script(self, data: dict[str, object]) -> bool:
        """检查 scripts 任意条目是否引用 .ts/.tsx 源.

        V2.18 P3-15 拆分: 从 _detect_from_package_json (B=9) 抽出.
        """
        scripts_raw = data.get("scripts", {})
        if not isinstance(scripts_raw, dict):
            return False
        return any(isinstance(p, str) and (p.endswith(".ts") or p.endswith(".tsx")) for p in scripts_raw.values())

    def _has_typescript_sources(self, project_root: Path) -> bool:
        """检查项目目录是否包含 .ts/.tsx 源文件.

        V2.18 P3-15 拆分: 从 _detect_from_package_json (B=9) 抽出.
        """
        return any(project_root.rglob("*.ts")) or any(project_root.rglob("*.tsx"))

    def _detect_from_package_json(self, project_root: Path) -> Language:
        """package.json 存在时判定 TS 或 JS (orchestrator).

        V2.18 P3-15 拆分: 从 B(9) / 27 行方法拆出 3 个判定 helper.
        主方法仅负责: 读取 JSON → 委托 3 判定 → 异常回退 JS.
        """
        import json

        pkg = project_root / "package.json"
        try:
            data = json.loads(pkg.read_text())
            if (
                self._has_typescript_dependency(data)
                or self._has_typescript_script(data)
                or self._has_typescript_sources(project_root)
            ):
                return Language.TYPESCRIPT
        except Exception:  # noqa: BLE001
            # TS 探测失败时降级为 JS, 属预期回退路径
            pass
        return Language.JAVASCRIPT

    def _detect_from_extensions(self, project_root: Path) -> Language | None:
        """按源文件扩展名统计取占比最高语言。"""
        ext_counts: dict[Language, int] = {}
        for ext, lang in EXTENSION_MAP.items():
            count = len(list(project_root.rglob(f"*{ext}")))
            if count > 0:
                ext_counts[lang] = ext_counts.get(lang, 0) + count

        if ext_counts:
            return max(ext_counts, key=lambda k: ext_counts[k])
        return None

    def detect_language(self, project_root: Path) -> Language | None:
        """从项目文件自动检测语言"""
        for pattern, lang in _CONFIG_FILE_LANGUAGES.items():
            if list(project_root.glob(pattern)):
                # package.json 需要进一步判断 TS/JS
                if pattern == "package.json":
                    return self._detect_from_package_json(project_root)
                return lang
        return self._detect_from_extensions(project_root)

    def validate_toolchain(self, language: str | Language) -> list[str]:
        """验证工具链可用性，返回缺失工具列表"""
        toolchain = self.get(language)
        if toolchain is None:
            return [f"Unknown language: {language}"]

        missing = []
        import subprocess

        for category in ToolCategory:
            tool = getattr(toolchain, category.value, None)
            if tool and tool.available:
                try:
                    result = subprocess.run(
                        [tool.command, tool.version_flag],
                        capture_output=True,
                        timeout=5,
                    )
                    if result.returncode != 0:
                        missing.append(f"{category.value}: {tool.command} (not found)")
                except (FileNotFoundError, subprocess.TimeoutExpired):
                    missing.append(f"{category.value}: {tool.command} (not installed)")

        return missing


# 扩展名映射 (用于自动检测)
EXTENSION_MAP: dict[str, Language] = {
    ".py": Language.PYTHON,
    ".pyi": Language.PYTHON,
    ".pyx": Language.PYTHON,
    ".pxd": Language.PYTHON,
    ".pxi": Language.PYTHON,
    ".ts": Language.TYPESCRIPT,
    ".tsx": Language.TYPESCRIPT,
    ".js": Language.JAVASCRIPT,
    ".jsx": Language.JAVASCRIPT,
    ".mjs": Language.JAVASCRIPT,
    ".cjs": Language.JAVASCRIPT,
    ".rs": Language.RUST,
    ".go": Language.GO,
    ".java": Language.JAVA,
    ".kt": Language.KOTLIN,
    ".kts": Language.KOTLIN,
    ".scala": Language.SCALA,
    ".sc": Language.SCALA,
    ".cpp": Language.CPP,
    ".cc": Language.CPP,
    ".cxx": Language.CPP,
    ".c": Language.CPP,
    ".hpp": Language.CPP,
    ".h": Language.CPP,
    ".hxx": Language.CPP,
    ".cs": Language.CSHARP,
    ".fs": Language.FSHARP,
    ".fsx": Language.FSHARP,
    ".fsi": Language.FSHARP,
    ".vb": Language.CSHARP,
    ".rb": Language.RUBY,
    ".rake": Language.RUBY,
    ".gemspec": Language.RUBY,
    ".php": Language.PHP,
    ".phtml": Language.PHP,
    ".swift": Language.SWIFT,
    ".dart": Language.DART,
    ".zig": Language.ZIG,
    ".ex": Language.ELIXIR,
    ".exs": Language.ELIXIR,
    ".eex": Language.ELIXIR,
    ".leex": Language.ELIXIR,
    ".clj": Language.CLOJURE,
    ".cljs": Language.CLOJURE,
    ".cljc": Language.CLOJURE,
    ".edn": Language.CLOJURE,
    ".hs": Language.HASKELL,
    ".lhs": Language.HASKELL,
    ".ml": Language.OCAML,
    ".mli": Language.OCAML,
    ".pl": Language.PERL,
    ".pm": Language.PERL,
    ".sh": Language.SHELL,
    ".bash": Language.SHELL,
    ".zsh": Language.SHELL,
    ".fish": Language.SHELL,
    ".sql": Language.SQL,
    ".ddl": Language.SQL,
    ".dml": Language.SQL,
    ".r": Language.R,
    ".R": Language.R,
    ".lua": Language.LUA,
}

# 单例实例
registry = LanguageRegistry()


# ============================================================================
# 便捷函数
# ============================================================================


def get_toolchain(language: str | Language) -> LanguageToolchain | None:
    return registry.get(language)


def get_tool(language: str | Language, category: ToolCategory) -> ToolConfig | None:
    return registry.get_tool(language, category)


def detect_language(project_root: Path) -> Language | None:
    return registry.detect_language(project_root)


def list_supported_languages() -> list[Language]:
    return registry.list_languages()


def validate_toolchain(language: str | Language) -> list[str]:
    return registry.validate_toolchain(language)


if __name__ == "__main__":
    import json
    import sys

    if len(sys.argv) < 2:
        print("用法: language_registry.py <command> [args]")
        print("命令:")
        print("  list                    - 列出支持的语言")
        print("  detect <path>           - 检测项目语言")
        print("  validate <language>     - 验证工具链")
        print("  get <language> [tool]   - 获取工具链/特定工具")
        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "list":
        langs = registry.list_languages()
        print(json.dumps([lang.value for lang in langs], indent=2, ensure_ascii=False))

    elif cmd == "detect":
        if len(sys.argv) < 3:
            print("需要路径参数")
            sys.exit(1)
        detected_lang = detect_language(Path(sys.argv[2]))
        print(detected_lang.value if detected_lang else "unknown")

    elif cmd == "validate":
        if len(sys.argv) < 3:
            print("需要语言参数")
            sys.exit(1)
        missing = validate_toolchain(sys.argv[2])
        if missing:
            print("缺失工具:")
            for m in missing:
                print(f"  - {m}")
            sys.exit(1)
        else:
            print("所有工具可用")

    elif cmd == "get":
        if len(sys.argv) < 3:
            print("需要语言参数")
            sys.exit(1)
        lang_str = sys.argv[2]
        try:
            target_lang: Language = Language(lang_str.lower())
        except ValueError:
            from tools.scripts.language_registry import LANGUAGE_ALIASES

            alias_lang = LANGUAGE_ALIASES.get(lang_str.lower())
            if alias_lang is None:
                print(f"未知语言: {lang_str}")
                sys.exit(1)
            target_lang = alias_lang
        if len(sys.argv) >= 4:
            tool = registry.get_tool(target_lang, ToolCategory(sys.argv[3]))
            if tool:
                print(
                    json.dumps(
                        {
                            "command": tool.command,
                            "args": tool.args,
                            "check_args": tool.check_args,
                            "fix_args": tool.fix_args,
                            "coverage_args": tool.coverage_args,
                            "config_file": tool.config_file,
                            "install_hint": tool.install_hint,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"未找到工具: {sys.argv[3]}")
        else:
            tc = registry.get(target_lang)
            if tc:
                print(
                    json.dumps(
                        {
                            "language": tc.language.value,
                            "extensions": tc.extensions,
                            "package_manager": tc.package_manager,
                            "default_paths": tc.default_paths,
                            "default_thresholds": tc.default_thresholds,
                        },
                        indent=2,
                        ensure_ascii=False,
                    )
                )
            else:
                print(f"未找到语言: {lang_str}")

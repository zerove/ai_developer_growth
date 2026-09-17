"""语言工具链注册表 - 内置工具链定义 (前半: Python → Kotlin)"""

from ._lang_types import Language, LanguageToolchain, ToolConfig

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

"""语言工具链注册表 - 内置工具链定义 (后半: Scala → SQL) 与映射表"""

from ._lang_data_a import (
    CPP_TOOLCHAIN,
    CSHARP_TOOLCHAIN,
    GO_TOOLCHAIN,
    JAVA_TOOLCHAIN,
    JAVASCRIPT_TOOLCHAIN,
    KOTLIN_TOOLCHAIN,
    PHP_TOOLCHAIN,
    PYTHON_TOOLCHAIN,
    RUBY_TOOLCHAIN,
    RUST_TOOLCHAIN,
    SWIFT_TOOLCHAIN,
    TYPESCRIPT_TOOLCHAIN,
)
from ._lang_types import Language, LanguageToolchain, ToolConfig

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
# 工具本身不会递归目录: shellcheck/shfmt 收到目录参数会报
# "openBinaryFile: inappropriate type (is a directory)", 而 `bash -n` /
# `shfmt -d` 不给文件时会读 stdin 挂起。因此统一用
# "find | xargs" 显式列出脚本文件（并排除 .git/.venv/node_modules）。
_SHELL_FILES = (
    r"find . -type f \( -name '*.sh' -o -name '*.bash' -o -name '*.zsh' \) "
    r"-not -path './.git/*' -not -path './.venv/*' -not -path './node_modules/*' -print0"
)

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
        command="bash",
        args=["-c", f"{_SHELL_FILES} | xargs -0 -r shfmt -d"],
        fix_args=["-c", f"{_SHELL_FILES} | xargs -0 -r shfmt -w"],
        config_file=".shfmtrc",
        install_hint="go install mvdan.cc/sh/v3/cmd/shfmt@latest",
    ),
    lint=ToolConfig(
        command="bash",
        args=["-c", f"{_SHELL_FILES} | xargs -0 -r shellcheck -x -S warning"],
        config_file=".shellcheckrc",
        install_hint="apt install shellcheck",
    ),
    typecheck=ToolConfig(
        command="bash",
        args=["-c", f"{_SHELL_FILES} | xargs -0 -r -n 1 bash -n"],
        install_hint="apt install bash",
    ),
    test=ToolConfig(
        command="bash",
        args=[
            "-c",
            "if compgen -G 'test/*_test.sh' >/dev/null 2>&1; then bats test; else echo 'no bats tests found'; fi",
        ],
        coverage_args=[],
        install_hint="apt install bats",
    ),
    security=ToolConfig(
        command="bash",
        args=["-c", f"{_SHELL_FILES} | xargs -0 -r shellcheck -x -S error"],
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

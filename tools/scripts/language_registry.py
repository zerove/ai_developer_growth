#!/usr/bin/env python3
"""
语言工具链注册表

定义各语言的标准工具链映射，支持动态加载和扩展。
所有 JCode 技能通过此注册表获取语言对应的工具命令。

实现已拆分为 _lang_types / _lang_data_a / _lang_data_b / _lang_registry 子模块，
本文件为薄 facade，重导出全部公开符号以保持既有导入路径兼容。
"""

from ._lang_data_a import (
    CPP_TOOLCHAIN as CPP_TOOLCHAIN,
)
from ._lang_data_a import (
    CSHARP_TOOLCHAIN as CSHARP_TOOLCHAIN,
)
from ._lang_data_a import (
    GO_TOOLCHAIN as GO_TOOLCHAIN,
)
from ._lang_data_a import (
    JAVA_TOOLCHAIN as JAVA_TOOLCHAIN,
)
from ._lang_data_a import (
    JAVASCRIPT_TOOLCHAIN as JAVASCRIPT_TOOLCHAIN,
)
from ._lang_data_a import (
    KOTLIN_TOOLCHAIN as KOTLIN_TOOLCHAIN,
)
from ._lang_data_a import (
    PHP_TOOLCHAIN as PHP_TOOLCHAIN,
)
from ._lang_data_a import (
    PYTHON_TOOLCHAIN as PYTHON_TOOLCHAIN,
)
from ._lang_data_a import (
    RUBY_TOOLCHAIN as RUBY_TOOLCHAIN,
)
from ._lang_data_a import (
    RUST_TOOLCHAIN as RUST_TOOLCHAIN,
)
from ._lang_data_a import (
    SWIFT_TOOLCHAIN as SWIFT_TOOLCHAIN,
)
from ._lang_data_a import (
    TYPESCRIPT_TOOLCHAIN as TYPESCRIPT_TOOLCHAIN,
)
from ._lang_data_b import (
    BUILTIN_TOOLCHAINS as BUILTIN_TOOLCHAINS,
)
from ._lang_data_b import (
    CLOJURE_TOOLCHAIN as CLOJURE_TOOLCHAIN,
)
from ._lang_data_b import (
    DART_TOOLCHAIN as DART_TOOLCHAIN,
)
from ._lang_data_b import (
    ELIXIR_TOOLCHAIN as ELIXIR_TOOLCHAIN,
)
from ._lang_data_b import (
    EXTENSION_MAP as EXTENSION_MAP,
)
from ._lang_data_b import (
    FSHARP_TOOLCHAIN as FSHARP_TOOLCHAIN,
)
from ._lang_data_b import (
    HASKELL_TOOLCHAIN as HASKELL_TOOLCHAIN,
)
from ._lang_data_b import (
    LANGUAGE_ALIASES as LANGUAGE_ALIASES,
)
from ._lang_data_b import (
    LUA_TOOLCHAIN as LUA_TOOLCHAIN,
)
from ._lang_data_b import (
    SCALA_TOOLCHAIN as SCALA_TOOLCHAIN,
)
from ._lang_data_b import (
    SHELL_TOOLCHAIN as SHELL_TOOLCHAIN,
)
from ._lang_data_b import (
    SQL_TOOLCHAIN as SQL_TOOLCHAIN,
)
from ._lang_data_b import (
    ZIG_TOOLCHAIN as ZIG_TOOLCHAIN,
)
from ._lang_registry import (
    LanguageRegistry as LanguageRegistry,
)
from ._lang_registry import (
    detect_language as detect_language,
)
from ._lang_registry import (
    get_tool as get_tool,
)
from ._lang_registry import (
    get_toolchain as get_toolchain,
)
from ._lang_registry import (
    list_supported_languages as list_supported_languages,
)
from ._lang_registry import (
    registry as registry,
)
from ._lang_registry import (
    validate_toolchain as validate_toolchain,
)
from ._lang_types import (
    Language as Language,
)
from ._lang_types import (
    LanguageToolchain as LanguageToolchain,
)
from ._lang_types import (
    ToolCategory as ToolCategory,
)
from ._lang_types import (
    ToolConfig as ToolConfig,
)

__all__ = [
    "Language",
    "ToolCategory",
    "ToolConfig",
    "LanguageToolchain",
    "LanguageRegistry",
    "PYTHON_TOOLCHAIN",
    "TYPESCRIPT_TOOLCHAIN",
    "JAVASCRIPT_TOOLCHAIN",
    "RUST_TOOLCHAIN",
    "GO_TOOLCHAIN",
    "JAVA_TOOLCHAIN",
    "CPP_TOOLCHAIN",
    "CSHARP_TOOLCHAIN",
    "RUBY_TOOLCHAIN",
    "PHP_TOOLCHAIN",
    "SWIFT_TOOLCHAIN",
    "KOTLIN_TOOLCHAIN",
    "SCALA_TOOLCHAIN",
    "DART_TOOLCHAIN",
    "ZIG_TOOLCHAIN",
    "ELIXIR_TOOLCHAIN",
    "CLOJURE_TOOLCHAIN",
    "HASKELL_TOOLCHAIN",
    "FSHARP_TOOLCHAIN",
    "LUA_TOOLCHAIN",
    "SHELL_TOOLCHAIN",
    "SQL_TOOLCHAIN",
    "BUILTIN_TOOLCHAINS",
    "LANGUAGE_ALIASES",
    "EXTENSION_MAP",
    "registry",
    "get_toolchain",
    "get_tool",
    "detect_language",
    "list_supported_languages",
    "validate_toolchain",
]

if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

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

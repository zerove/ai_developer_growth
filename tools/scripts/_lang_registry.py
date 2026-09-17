"""语言工具链注册表 - 注册表类与便捷函数"""

from pathlib import Path
from typing import cast

from ._lang_data_b import BUILTIN_TOOLCHAINS, EXTENSION_MAP, LANGUAGE_ALIASES
from ._lang_types import Language, LanguageToolchain, ToolCategory, ToolConfig

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

    @staticmethod
    def _check_single_tool(category: ToolCategory, tool: ToolConfig) -> str | None:
        """探测单个工具的可用性.

        V2.19 P3-16 拆分: 从 validate_toolchain (B=7) 抽出.
        通过 subprocess 调用 tool --version_flag, 5s 超时.
        返回缺失描述 (str) 或 None (可用).
        """
        import subprocess

        try:
            result = subprocess.run(
                [tool.command, tool.version_flag],
                capture_output=True,
                timeout=5,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return f"{category.value}: {tool.command} (not installed)"
        if result.returncode != 0:
            return f"{category.value}: {tool.command} (not found)"
        return None

    def validate_toolchain(self, language: str | Language) -> list[str]:
        """验证工具链可用性，返回缺失工具列表 (orchestrator).

        V2.19 P3-16 拆分: 从 B(7) / 25 行方法拆出 _check_single_tool helper.
        主方法仅负责: 解析 toolchain → 遍历 category → 委托探测 → 收集缺失.
        """
        toolchain = self.get(language)
        if toolchain is None:
            return [f"Unknown language: {language}"]

        missing: list[str] = []
        for category in ToolCategory:
            tool = getattr(toolchain, category.value, None)
            if tool and tool.available:
                result = self._check_single_tool(category, tool)
                if result is not None:
                    missing.append(result)
        return missing


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

"""Build and analyze module dependency graphs from source code imports.

Usage:
    from tools.scripts.rules_engine.arch import DependencyGraph

    graph = DependencyGraph()
    issues = graph.analyze_directory(Path("src/"))
    for issue in issues:
        print(f"{issue.severity}: {issue.message}")

## import 必须解析到真实模块（架构守卫修复）

旧实现把 import 说明符（如 ``services.billing`` / ``./helper``）**原样**当作
图节点写入, 而图节点是**文件相对路径**（``services/billing.py``）。两者永不相等,
于是:

- 边的终点不是图节点 → 循环依赖检测**永远不可能命中**（静默假绿灯）;
- hub 统计把标准库/第三方依赖也计入 → 阈值失真。

现改为: 先建立"模块路径 → 文件"的索引, 再把每条 import 说明符解析到树内模块;
解析不到 (标准库/第三方) 的不建边 —— 图因此只表达**项目内部**依赖。
Python 用 ``ast`` 精确取 import (不受 docstring/注释里的示例代码干扰),
其余语言用正则。
"""

from __future__ import annotations

import ast
import os
import re
from collections import defaultdict
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path, PurePosixPath

from ..models import Issue


@dataclass
class DependencyIssue:
    """A single architecture-level issue."""

    severity: str  # error, warning, info
    category: str  # "cycle", "layer-violation", "hub"
    file: str
    line: int
    message: str
    related_files: list[str] = field(default_factory=list)

    def to_issue(self, rule_id: str) -> Issue:
        return Issue(
            rule_id=rule_id,
            severity=self.severity,
            category=f"architecture.{self.category}",
            file=self.file,
            line=self.line,
            message=self.message,
        )


# Import pattern for various languages (Python 走 ast, 不在此列)
IMPORT_PATTERNS: dict[str, list[str]] = {
    "typescript": [
        r"import\s+.*\s+from\s+['\"](\.[^'\"]+)['\"]",
        r"import\s+['\"](\.[^'\"]+)['\"]",
    ],
    "javascript": [
        r"require\s*\(\s*['\"](\.[^'\"]+)['\"]",
        r"import\s+.*\s+from\s+['\"](\.[^'\"]+)['\"]",
    ],
    "java": [
        r"import\s+(\w+(?:\.\w+)+);",
    ],
    "go": [
        r'import\s+"([^"]+)"',
    ],
    "rust": [
        r"use\s+(\w+(?:::\w+)*)",
        r"extern\s+crate\s+(\w+)",
    ],
}

# Languages that are commonly analyzed for architecture
ANALYZED_LANGUAGES = {"python", "typescript", "javascript", "java", "go", "rust"}

# Default file extensions by language
LANGUAGE_EXTS: dict[str, list[str]] = {
    "python": [".py"],
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx", ".mjs"],
    "java": [".java"],
    "go": [".go"],
    "rust": [".rs"],
}


@dataclass
class CycleExemption:
    """已登记的循环豁免（存量债务, 附原因, 逐条可见）。"""

    modules: frozenset[str]
    reason: str = ""


@dataclass
class ArchitectureSettings:
    """``.adg/architecture.yml`` 中与依赖图相关的设置。

    该文件此前只有 ``layers`` 被解析, ``cycle_detection`` / ``hub_detection``
    段落是**摆设**（写了不生效）。现由本类统一承载, 让配置真正生效。
    """

    cycle_detection_enabled: bool = True
    max_cycle_length: int = 10
    cycle_exemptions: list[CycleExemption] = field(default_factory=list)
    hub_detection_enabled: bool = True
    hub_threshold: int = 25
    hub_exclude_patterns: list[str] = field(default_factory=list)

    @classmethod
    def from_yaml(cls, path: Path) -> ArchitectureSettings:
        """从 YAML 读取设置；文件缺失/解析失败时返回默认值（不 fail-open 到"无检查"）。"""
        settings = cls()
        try:
            import yaml

            if not path.exists():
                return settings
            data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(data, dict):
                return settings
        except Exception:  # noqa: BLE001 - 配置坏了也要继续检查, 只是用默认值
            return settings

        cycle = data.get("cycle_detection") or {}
        if isinstance(cycle, dict):
            settings.cycle_detection_enabled = bool(cycle.get("enabled", True))
            settings.max_cycle_length = int(cycle.get("max_cycle_length", 10) or 10)
            settings.cycle_exemptions = _parse_cycle_exemptions(cycle.get("exemptions"))

        hub = data.get("hub_detection") or {}
        if isinstance(hub, dict):
            settings.hub_detection_enabled = bool(hub.get("enabled", True))
            settings.hub_threshold = int(hub.get("threshold", 25) or 25)
            excludes = hub.get("exclude_patterns")
            settings.hub_exclude_patterns = [str(p) for p in excludes] if isinstance(excludes, list) else []
        return settings


def _parse_cycle_exemptions(raw: object) -> list[CycleExemption]:
    """解析 cycle_detection.exemptions 列表。"""
    if not isinstance(raw, list):
        return []
    exemptions: list[CycleExemption] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        modules = item.get("modules")
        if not isinstance(modules, list) or not modules:
            continue
        exemptions.append(
            CycleExemption(
                modules=frozenset(str(m) for m in modules),
                reason=str(item.get("reason", "")),
            )
        )
    return exemptions


def _python_import_specifiers(content: str) -> list[str]:
    """用 ast 精确提取 Python import 说明符。

    不用正则的原因: 文档字符串/注释里的示例 import 会造成**假边**
    (旧实现里 ``app_config.py`` 甚至因此指向自己), 而 ast 只看真实语句。
    语法错误时返回空列表 (语法错误由别的检查器负责报告)。
    """
    try:
        tree = ast.parse(content)
    except SyntaxError:
        return []
    specifiers: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            specifiers.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                specifiers.append("." * node.level + (node.module or ""))
            elif node.module:
                specifiers.append(node.module)
    return specifiers


def _python_candidates(specifier: str, importer_rel: str) -> list[str]:
    """Python import 说明符 → 可能的模块键。

    - 绝对导入: ``a.b.c`` → ``a/b/c`` (索引里登记了点号形式, 两者都能命中);
    - 相对导入: ``.mod`` → 相对导入方所在包目录拼接。
    """
    if not specifier.startswith("."):
        return [specifier.replace(".", "/"), specifier]
    level = len(specifier) - len(specifier.lstrip("."))
    rest = specifier[level:].replace(".", "/")
    parent = PurePosixPath(importer_rel).parent
    parts = [p for p in parent.parts if p not in (".", "/")]
    if level > 1:
        parts = parts[: len(parts) - (level - 1)] if len(parts) >= level - 1 else []
    prefix = "/".join(parts)
    if rest:
        return [f"{prefix}/{rest}" if prefix else rest]
    return [prefix] if prefix else []


def _js_candidates(specifier: str, importer_rel: str) -> list[str]:
    """JS/TS 相对 import → 可能的模块键 (含 ``/index`` 形式)。"""
    if not specifier.startswith("."):
        return []
    parent = PurePosixPath(importer_rel).parent
    target = os.path.normpath(str(parent / specifier)).replace(os.sep, "/")
    return [target, f"{target}/index"]


def _is_exempted_cycle(cycle: list[str], exemptions: list[CycleExemption]) -> bool:
    """循环是否命中已登记的豁免。

    豁免的 ``modules`` 支持 glob (``parsers/*.py``): 环中**每个**模块都能被
    同一条豁免的某个模式匹配时才算豁免 —— 避免"沾边即豁免"。
    """
    if not exemptions:
        return False
    for exemption in exemptions:
        if not exemption.modules:
            continue
        if all(any(_module_matches(m, pattern) for pattern in exemption.modules) for m in cycle):
            return True
    return False


def _module_matches(module: str, pattern: str) -> bool:
    """模块路径是否匹配豁免模式 (支持 glob 与精确路径)。"""
    if pattern == module:
        return True
    return fnmatch(module, pattern)


def _matches_exclude(module: str, patterns: list[str]) -> bool:
    """模块路径是否命中排除模式 (``**/x.py`` 或 ``x.py`` 片段)。"""
    for pattern in patterns:
        if not pattern:
            continue
        if fnmatch(module, pattern) or fnmatch(module, f"*/{pattern.lstrip('*/')}"):
            return True
        if pattern.endswith("/") and module.startswith(pattern):
            return True
    return False


class DependencyGraph:
    """Analyze module dependencies and detect architecture issues."""

    def __init__(self) -> None:
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._file_to_module: dict[str, str] = {}
        self._module_to_files: dict[str, list[str]] = defaultdict(list)
        # 模块路径(去扩展名) -> 文件相对路径; 用于把 import 说明符解析到真实模块
        self._module_index: dict[str, str] = {}

    def analyze_directory(self, dirpath: Path, languages: list[str] | None = None) -> list[DependencyIssue]:
        """Analyze all source files in directory and find architecture issues.

        Args:
            dirpath: Project root directory.
            languages: Languages to analyze (None = all supported).

        Returns:
            List of architecture issues found.
        """
        issues: list[DependencyIssue] = []
        settings = ArchitectureSettings.from_yaml(dirpath / ".adg" / "architecture.yml")

        # 1. Build dependency graph
        self._build_graph(dirpath, languages or list(ANALYZED_LANGUAGES))

        # 2. Detect cycles
        issues.extend(self._find_cycles(settings))

        # 3. Detect hub modules (threshold from config, default 25; skip __init__.py)
        if settings.hub_detection_enabled:
            issues.extend(self._find_hubs(settings.hub_threshold, settings.hub_exclude_patterns))

        return issues

    def _build_graph(self, dirpath: Path, languages: list[str]) -> None:
        """Scan files and build import dependency graph (V2.21 P5-56 拆分: 抽 _collect_code_files + _extract_imports_in_file, 方法级 helper)."""
        code_files = self._collect_code_files(dirpath, languages)
        self._build_module_index(code_files, dirpath)

        for filepath in code_files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue

            self._extract_imports_in_file(filepath, dirpath, content)

    def _build_module_index(self, code_files: list[Path], dirpath: Path) -> None:
        """建立"模块路径(去扩展名) → 文件相对路径"索引, 供 import 解析。

        同时登记包目录 (``pkg/__init__.py`` → ``pkg``) 与 Python 点号形式
        (``pkg.mod`` → ``pkg/mod.py``), 使绝对导入也能解析。
        """
        for filepath in code_files:
            rel = str(filepath.relative_to(dirpath))
            stem = rel.rsplit(".", 1)[0]
            self._module_index.setdefault(stem, rel)
            if stem.endswith("/__init__"):
                self._module_index.setdefault(stem[: -len("/__init__")], rel)
            if filepath.suffix.lower() == ".py":
                self._module_index.setdefault(stem.replace("/", "."), rel)

    def _collect_code_files(self, dirpath: Path, languages: list[str]) -> list[Path]:
        """收集指定语言的代码文件, 跳过 ignore 目录 (方法级 helper).

        Args:
            dirpath: 扫描根目录
            languages: 目标语言列表

        Returns:
            文件路径列表
        """
        exts: list[str] = []
        for lang in languages:
            exts.extend(LANGUAGE_EXTS.get(lang, []))
        code_files: list[Path] = []
        for ext in exts:
            code_files.extend(dirpath.rglob(f"*{ext}"))
        ignore_dirs = {
            "__pycache__",
            ".git",
            "node_modules",
            ".venv",
            "dist",
            "build",
            ".mypy_cache",
        }
        return [f for f in code_files if not any(d in f.parts for d in ignore_dirs)]

    def _extract_imports_in_file(self, filepath: Path, dirpath: Path, content: str) -> None:
        """从单文件提取 import, 内部更新 self._graph/_file_to_module/_module_to_files.

        只保留**能解析到树内模块**的依赖: 标准库/第三方不入图, 图因此只表达
        项目内部依赖 (hub 统计与循环检测才有意义)。

        Args:
            filepath: 文件路径
            dirpath: 扫描根目录
            content: 文件内容
        """
        lang = self._detect_lang(filepath)
        rel = str(filepath.relative_to(dirpath))
        self._file_to_module[rel] = rel
        self._module_to_files[rel].append(rel)

        for specifier in self._iter_imports(lang, content):
            target = self._resolve_import(specifier, lang, rel)
            if target is None:
                continue  # 外部依赖 (标准库/第三方) 不入图
            if target == rel:
                continue  # 自引用 (模块导入自己)
            self._graph[rel].add(target)

    def _iter_imports(self, lang: str, content: str) -> list[str]:
        """列出文件中的 import 说明符 (Python 走 ast, 其余走正则)。"""
        if lang == "python":
            return _python_import_specifiers(content)
        patterns = IMPORT_PATTERNS.get(lang, [])
        if not patterns:
            return []
        specifiers: list[str] = []
        for pattern in patterns:
            for match in re.finditer(pattern, content):
                specifiers.append(match.group(1))
        return specifiers

    def _resolve_import(self, specifier: str, lang: str, importer_rel: str) -> str | None:
        """把 import 说明符解析为树内**文件相对路径**; 解析不到返回 None。"""
        for candidate in self._import_candidates(specifier, lang, importer_rel):
            target = self._module_index.get(candidate)
            if target is not None:
                return target
        return None

    def _import_candidates(self, specifier: str, lang: str, importer_rel: str) -> list[str]:
        """给出 import 说明符可能对应的模块键 (按优先级)。"""
        if lang == "python":
            return _python_candidates(specifier, importer_rel)
        if lang in ("javascript", "typescript"):
            return _js_candidates(specifier, importer_rel)
        if lang == "java":
            return [specifier.replace(".", "/")]
        if lang == "rust":
            return [specifier.replace("::", "/")]
        return []  # Go 的 import 是模块路径, 无法映射到文件

    def _find_cycles(self, settings: ArchitectureSettings | None = None) -> list[DependencyIssue]:
        """Detect circular dependencies using DFS.

        Args:
            settings: 架构设置 (启用开关、最大环长、已登记豁免)；None 用默认值。
        """
        settings = settings or ArchitectureSettings()
        if not settings.cycle_detection_enabled:
            return []
        issues: list[DependencyIssue] = []
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
                if len(cycle) - 1 > settings.max_cycle_length:
                    return
                if _is_exempted_cycle(cycle, settings.cycle_exemptions):
                    return
                issues.append(
                    DependencyIssue(
                        severity="error",
                        category="cycle",
                        file=node,
                        line=1,
                        message=f"Circular dependency detected: {' → '.join(cycle)}",
                        related_files=cycle,
                    )
                )
                return
            if node in visited:
                return
            visited.add(node)
            path.append(node)
            for neighbor in sorted(self._graph.get(node, set())):
                if neighbor in self._file_to_module or neighbor in self._graph:
                    dfs(neighbor)
            path.pop()

        for node in list(self._graph.keys()):
            dfs(node)

        return issues

    def _find_hubs(self, max_deps: int = 25, exclude_patterns: list[str] | None = None) -> list[DependencyIssue]:
        """Detect hub modules that depend on too many other modules.

        Args:
            max_deps: Maximum allowed dependencies before warning.
                      Raised from 15 to 25 because orchestrator/entry-point
                      files naturally import many modules.
            exclude_patterns: 排除的模块路径片段 (glob), 如 ``**/__init__.py``。
        """
        issues: list[DependencyIssue] = []
        excludes = list(exclude_patterns or [])
        for module, deps in self._graph.items():
            # Skip __init__.py files (they are package aggregators by design)
            if "__init__.py" in module or module.endswith("__init__"):
                continue
            if _matches_exclude(module, excludes):
                continue
            if len(deps) > max_deps:
                issues.append(
                    DependencyIssue(
                        severity="warning",
                        category="hub",
                        file=module,
                        line=1,
                        message=f"Module depends on {len(deps)} modules (max {max_deps}) — consider splitting",
                        related_files=list(deps),
                    )
                )
        return issues

    def _detect_lang(self, filepath: Path) -> str:
        ext = filepath.suffix.lower()
        for lang, exts in LANGUAGE_EXTS.items():
            if ext in exts:
                return lang
        return "unknown"

    @property
    def module_count(self) -> int:
        return len(self._graph)

    @property
    def edge_count(self) -> int:
        return sum(len(deps) for deps in self._graph.values())

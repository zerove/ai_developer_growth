"""Build and analyze module dependency graphs from source code imports.

Usage:
    from tools.scripts.rules_engine.arch import DependencyGraph

    graph = DependencyGraph()
    issues = graph.analyze_directory(Path("src/"))
    for issue in issues:
        print(f"{issue.severity}: {issue.message}")
"""

from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

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


# Import pattern for various languages
IMPORT_PATTERNS: dict[str, list[str]] = {
    "python": [
        r"import\s+(\w+)",
        r"from\s+(\w+(?:\.\w+)*)\s+import",
    ],
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


class DependencyGraph:
    """Analyze module dependencies and detect architecture issues."""

    def __init__(self) -> None:
        self._graph: dict[str, set[str]] = defaultdict(set)
        self._file_to_module: dict[str, str] = {}
        self._module_to_files: dict[str, list[str]] = defaultdict(list)

    def analyze_directory(self, dirpath: Path, languages: list[str] | None = None) -> list[DependencyIssue]:
        """Analyze all source files in directory and find architecture issues.

        Args:
            dirpath: Project root directory.
            languages: Languages to analyze (None = all supported).

        Returns:
            List of architecture issues found.
        """
        issues: list[DependencyIssue] = []

        # 1. Build dependency graph
        self._build_graph(dirpath, languages or list(ANALYZED_LANGUAGES))

        # 2. Detect cycles
        issues.extend(self._find_cycles())

        # 3. Detect hub modules (threshold 25, skip __init__.py)
        issues.extend(self._find_hubs(max_deps=25))

        return issues

    def _build_graph(self, dirpath: Path, languages: list[str]) -> None:
        """Scan files and build import dependency graph."""
        exts: list[str] = []
        for lang in languages:
            exts.extend(LANGUAGE_EXTS.get(lang, []))

        code_files: list[Path] = []
        for ext in exts:
            code_files.extend(dirpath.rglob(f"*{ext}"))

        # Filter ignored dirs
        ignore_dirs = {"__pycache__", ".git", "node_modules", ".venv", "dist", "build", ".mypy_cache"}
        code_files = [f for f in code_files if not any(d in f.parts for d in ignore_dirs)]

        for filepath in code_files:
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
            except Exception:
                continue

            lang = self._detect_lang(filepath)
            patterns = IMPORT_PATTERNS.get(lang, [])
            if not patterns:
                continue

            # Register file
            rel = str(filepath.relative_to(dirpath))
            self._file_to_module[rel] = rel
            self._module_to_files[rel].append(rel)

            # Find imports
            for pattern in patterns:
                for match in re.finditer(pattern, content):
                    imported = match.group(1)
                    # Only track local imports
                    if imported.startswith(".") or "/" in imported or imported[0].islower():
                        self._graph[rel].add(imported)

    def _find_cycles(self) -> list[DependencyIssue]:
        """Detect circular dependencies using DFS."""
        issues: list[DependencyIssue] = []
        visited: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            if node in path:
                cycle_start = path.index(node)
                cycle = path[cycle_start:] + [node]
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
            for neighbor in list(self._graph.get(node, set())):
                if neighbor in self._file_to_module or neighbor in self._graph:
                    dfs(neighbor)
            path.pop()

        for node in list(self._graph.keys()):
            dfs(node)

        return issues

    def _find_hubs(self, max_deps: int = 25) -> list[DependencyIssue]:
        """Detect hub modules that depend on too many other modules.

        Args:
            max_deps: Maximum allowed dependencies before warning.
                      Raised from 15 to 25 because orchestrator/entry-point
                      files naturally import many modules.
        """
        issues: list[DependencyIssue] = []
        for module, deps in self._graph.items():
            # Skip __init__.py files (they are package aggregators by design)
            if "__init__.py" in module or module.endswith("__init__"):
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

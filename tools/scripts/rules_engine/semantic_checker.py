"""Semantic code analysis engine using AST parsing.

Performs cross-file dependency analysis, unused import detection,
import cycle detection, and code complexity metrics.

Usage:
    from tools.scripts.rules_engine.semantic_checker import SemanticChecker

    checker = SemanticChecker()
    results = checker.analyze_directory(project_path)
"""

from __future__ import annotations

import time
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tools.scripts.rules_engine.ast_parser import ASTParser, FileAST, ImportInfo, get_parser


@dataclass
class SemanticIssue:
    """A semantic issue found by analysis."""

    rule_id: str
    severity: str
    category: str
    file: str
    line: int
    message: str
    fix_hint: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass
class ImportGraph:
    """Dependency graph for a project."""

    nodes: set[str] = field(default_factory=set)
    edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))
    reverse_edges: dict[str, set[str]] = field(default_factory=lambda: defaultdict(set))

    def add_edge(self, source: str, target: str) -> None:
        """Add a dependency edge."""
        self.nodes.add(source)
        self.nodes.add(target)
        self.edges[source].add(target)
        self.reverse_edges[target].add(source)

    def find_cycles(self) -> list[list[str]]:
        """Find import cycles using DFS."""
        cycles: list[list[str]] = []
        visited: set[str] = set()
        rec_stack: set[str] = set()
        path: list[str] = []

        def dfs(node: str) -> None:
            visited.add(node)
            rec_stack.add(node)
            path.append(node)

            for neighbor in self.edges.get(node, set()):
                if neighbor not in visited:
                    dfs(neighbor)
                elif neighbor in rec_stack:
                    # Found cycle
                    cycle_start = path.index(neighbor)
                    cycle = path[cycle_start:] + [neighbor]
                    cycles.append(cycle)

            path.pop()
            rec_stack.discard(node)

        for node in self.nodes:
            if node not in visited:
                dfs(node)

        return cycles

    def find_unused_imports(self, file_imports: dict[str, list[ImportInfo]], file_content: dict[str, str]) -> list[SemanticIssue]:
        """Find imports that are not used in the file."""
        issues: list[SemanticIssue] = []

        for filepath, imports in file_imports.items():
            content = file_content.get(filepath, "")
            for imp in imports:
                if imp.is_from and imp.names:
                    for name in imp.names:
                        # Check if the imported name is used
                        if name not in content or content.count(name) <= 1:
                            issues.append(
                                SemanticIssue(
                                    rule_id="unused-import",
                                    severity="warning",
                                    category="code_quality",
                                    file=filepath,
                                    line=imp.line,
                                    message=f"Unused import: {name} from {imp.module}",
                                    fix_hint=f"Remove 'from {imp.module} import {name}'",
                                )
                            )
                elif not imp.is_from and imp.module:
                    # Check if module name appears in content
                    module_short = imp.module.split(".")[-1]
                    if module_short not in content or content.count(module_short) <= 1:
                        issues.append(
                            SemanticIssue(
                                rule_id="unused-import",
                                severity="warning",
                                category="code_quality",
                                file=filepath,
                                line=imp.line,
                                message=f"Unused import: {imp.module}",
                                fix_hint=f"Remove 'import {imp.module}'",
                            )
                        )

        return issues

    def find_shadowed_imports(self, file_imports: dict[str, list[ImportInfo]]) -> list[SemanticIssue]:
        """Find imports that shadow built-in names."""
        builtin_names = {
            "list", "dict", "set", "tuple", "str", "int", "float", "bool",
            "type", "id", "hash", "input", "map", "filter", "range", "zip",
            "open", "print", "format", "len", "abs", "min", "max", "sum",
            "all", "any", "sorted", "reversed", "enumerate", "isinstance",
            "issubclass", "super", "property", "staticmethod", "classmethod",
        }
        issues: list[SemanticIssue] = []

        for filepath, imports in file_imports.items():
            for imp in imports:
                for name in imp.names:
                    if name in builtin_names:
                        issues.append(
                            SemanticIssue(
                                rule_id="shadowed-import",
                                severity="warning",
                                category="code_quality",
                                file=filepath,
                                line=imp.line,
                                message=f"Import '{name}' shadows Python built-in",
                                fix_hint=f"Rename import to avoid shadowing built-in '{name}'",
                            )
                        )

        return issues


@dataclass
class ComplexityMetrics:
    """Code complexity metrics for a file or project."""

    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0
    total_lines: int = 0
    avg_function_length: float = 0.0
    max_function_length: int = 0
    avg_complexity: float = 0.0
    max_complexity: int = 0
    functions_without_docstring: int = 0
    classes_without_docstring: int = 0
    long_functions: list[str] = field(default_factory=list)
    complex_functions: list[str] = field(default_factory=list)


@dataclass
class SemanticResult:
    """Results from semantic analysis."""

    issues: list[SemanticIssue]
    metrics: ComplexityMetrics
    import_graph: ImportGraph
    parse_errors: list[SemanticIssue]
    analysis_time_ms: float
    files_analyzed: int


class SemanticChecker:
    """Semantic code analysis using AST parsing."""

    def __init__(self) -> None:
        self.parser: ASTParser = get_parser()
        self.import_graph = ImportGraph()

    def analyze_file(self, filepath: Path, language: str | None = None) -> FileAST | None:
        """Analyze a single file using AST parsing."""
        return self.parser.parse_file(filepath, language)

    def analyze_directory(
        self,
        dirpath: Path,
        languages: list[str] | None = None,
        max_files: int = 1000,
    ) -> SemanticResult:
        """Analyze an entire directory for semantic issues.

        Args:
            dirpath: Directory to analyze.
            languages: Filter to these languages only.
            max_files: Maximum files to analyze.

        Returns:
            SemanticResult with all findings.
        """
        start_time = time.monotonic()
        issues: list[SemanticIssue] = []
        parse_errors: list[SemanticIssue] = []
        file_asts: dict[str, FileAST] = {}
        file_imports: dict[str, list[ImportInfo]] = {}
        file_content: dict[str, str] = {}

        # Collect source files
        source_files = self._collect_source_files(dirpath, languages, max_files)

        # Parse all files
        for filepath in source_files:
            try:
                ast_result = self.parser.parse_file(filepath)
                if ast_result is not None:
                    rel_path = str(filepath.relative_to(dirpath))
                    file_asts[rel_path] = ast_result
                    file_imports[rel_path] = ast_result.imports
                    try:
                        file_content[rel_path] = filepath.read_text(encoding="utf-8", errors="ignore")
                    except OSError:
                        pass

                    # Build import graph
                    for imp in ast_result.imports:
                        if imp.module:
                            self.import_graph.add_edge(rel_path, imp.module)

                    # Check for parse errors
                    for error_node in ast_result.error_nodes:
                        parse_errors.append(
                            SemanticIssue(
                                rule_id="parse-error",
                                severity="error",
                                category="syntax",
                                file=rel_path,
                                line=error_node.line,
                                message=f"Syntax error at line {error_node.line}: {error_node.name[:80]}",
                                fix_hint="Fix syntax error",
                            )
                        )
            except Exception as e:
                parse_errors.append(
                    SemanticIssue(
                        rule_id="parse-failure",
                        severity="error",
                        category="syntax",
                        file=str(filepath.relative_to(dirpath)),
                        line=0,
                        message=f"Failed to parse file: {e}",
                        fix_hint="Check file encoding and syntax",
                    )
                )

        # Run semantic checks
        issues.extend(self._check_complexity(file_asts, dirpath))
        issues.extend(self._check_missing_docstrings(file_asts, dirpath))
        issues.extend(self.import_graph.find_unused_imports(file_imports, file_content))
        issues.extend(self.import_graph.find_shadowed_imports(file_imports))

        # Import cycles
        cycles = self.import_graph.find_cycles()
        for cycle in cycles:
            issues.append(
                SemanticIssue(
                    rule_id="import-cycle",
                    severity="warning",
                    category="architecture",
                    file=cycle[0] if cycle else "",
                    line=0,
                    message=f"Import cycle detected: {' -> '.join(cycle)}",
                    fix_hint="Refactor to break the import cycle",
                    context={"cycle": cycle},
                )
            )

        # Calculate metrics
        metrics = self._calculate_metrics(file_asts)

        analysis_time = (time.monotonic() - start_time) * 1000

        return SemanticResult(
            issues=issues,
            metrics=metrics,
            import_graph=self.import_graph,
            parse_errors=parse_errors,
            analysis_time_ms=analysis_time,
            files_analyzed=len(file_asts),
        )

    def _collect_source_files(
        self, dirpath: Path, languages: list[str] | None, max_files: int
    ) -> list[Path]:
        """Collect source files from directory."""
        extensions = {
            "python": {".py"},
            "javascript": {".js", ".jsx", ".mjs"},
            "typescript": {".ts", ".tsx"},
            "rust": {".rs"},
            "go": {".go"},
            "java": {".java"},
            "ruby": {".rb"},
        }

        if languages:
            exts: set[str] = set()
            for lang in languages:
                exts.update(extensions.get(lang, set()))
        else:
            exts = set()
            for ext_set in extensions.values():
                exts.update(ext_set)

        ignore_dirs = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build", ".cache", "site"}

        files: list[Path] = []
        for ext in exts:
            for filepath in dirpath.rglob(f"*{ext}"):
                if any(d in filepath.parts for d in ignore_dirs):
                    continue
                files.append(filepath)
                if len(files) >= max_files:
                    return files

        return sorted(files)

    def _check_complexity(self, file_asts: dict[str, FileAST], base_dir: Path) -> list[SemanticIssue]:
        """Check for overly complex functions."""
        issues: list[SemanticIssue] = []

        for filepath, ast_result in file_asts.items():
            for func in ast_result.functions:
                if func.body_lines > 50:
                    issues.append(
                        SemanticIssue(
                            rule_id="long-function",
                            severity="warning",
                            category="complexity",
                            file=filepath,
                            line=func.line,
                            message=f"Function '{func.name}' is {func.body_lines} lines long (>50)",
                            fix_hint="Break into smaller functions",
                        )
                    )

                if func.complexity > 10:
                    issues.append(
                        SemanticIssue(
                            rule_id="high-complexity",
                            severity="warning",
                            category="complexity",
                            file=filepath,
                            line=func.line,
                            message=f"Function '{func.name}' has complexity {func.complexity} (>10)",
                            fix_hint="Simplify control flow or extract helper functions",
                        )
                    )

                if func.is_method and func.name.startswith("_") and not func.name.startswith("__"):
                    pass  # private methods are OK

        return issues

    def _check_missing_docstrings(self, file_asts: dict[str, FileAST], base_dir: Path) -> list[SemanticIssue]:
        """Check for missing docstrings on public functions/classes."""
        issues: list[SemanticIssue] = []

        for filepath, ast_result in file_asts.items():
            for func in ast_result.functions:
                if not func.name.startswith("_") and func.docstring is None:
                    issues.append(
                        SemanticIssue(
                            rule_id="missing-docstring",
                            severity="info",
                            category="documentation",
                            file=filepath,
                            line=func.line,
                            message=f"Public function '{func.name}' has no docstring",
                            fix_hint=f"Add docstring: \"\"\"{func.name} ... \"\"\"",
                        )
                    )

            for cls in ast_result.classes:
                if not cls.name.startswith("_") and cls.docstring is None:
                    issues.append(
                        SemanticIssue(
                            rule_id="missing-docstring",
                            severity="info",
                            category="documentation",
                            file=filepath,
                            line=cls.line,
                            message=f"Public class '{cls.name}' has no docstring",
                            fix_hint=f"Add docstring: \"\"\"{cls.name} ... \"\"\"",
                        )
                    )

        return issues

    def _calculate_metrics(self, file_asts: dict[str, FileAST]) -> ComplexityMetrics:
        """Calculate aggregate complexity metrics."""
        metrics = ComplexityMetrics()

        total_func_length = 0
        total_complexity = 0

        for ast_result in file_asts.values():
            metrics.total_functions += len(ast_result.functions)
            metrics.total_classes += len(ast_result.classes)
            metrics.total_imports += len(ast_result.imports)

            for func in ast_result.functions:
                total_func_length += func.body_lines
                total_complexity += func.complexity
                if func.body_lines > metrics.max_function_length:
                    metrics.max_function_length = func.body_lines
                if func.complexity > metrics.max_complexity:
                    metrics.max_complexity = func.complexity
                if func.body_lines > 50:
                    metrics.long_functions.append(f"{func.class_name}.{func.name}" if func.class_name else func.name)
                if func.complexity > 10:
                    metrics.complex_functions.append(f"{func.class_name}.{func.name}" if func.class_name else func.name)
                if func.docstring is None and not func.name.startswith("_"):
                    metrics.functions_without_docstring += 1

            for cls in ast_result.classes:
                if cls.docstring is None and not cls.name.startswith("_"):
                    metrics.classes_without_docstring += 1

        if metrics.total_functions > 0:
            metrics.avg_function_length = total_func_length / metrics.total_functions
            metrics.avg_complexity = total_complexity / metrics.total_functions

        return metrics

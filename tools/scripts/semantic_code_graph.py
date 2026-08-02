"""Semantic Code Knowledge Graph (Pillar 1)

Extracts AST-based code nodes (classes, functions, calls, imports) and builds
a local semantic dependency graph to analyze upstream/downstream impact of changes.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

from tools.scripts._common import get_project_root


class CodeNode:
    def __init__(self, name: str, node_type: str, file_path: str, line: int):
        self.name = name
        self.node_type = node_type
        self.file_path = file_path
        self.line = line
        self.dependencies: set[str] = set()
        self.dependents: set[str] = set()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "node_type": self.node_type,
            "file_path": self.file_path,
            "line": self.line,
            "dependencies": list(self.dependencies),
            "dependents": list(self.dependents),
        }


class SemanticCodeGraph:
    def __init__(self, root_dir: Path | None = None):
        self.root_dir = root_dir or get_project_root()
        self.nodes: dict[str, CodeNode] = {}

    def build_graph(self) -> None:
        py_files = list(self.root_dir.glob("**/*.py"))
        for file_path in py_files:
            if any(p in str(file_path) for p in [".venv", "build", "dist", ".git", "__pycache__"]):
                continue
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                rel_path = str(file_path.relative_to(self.root_dir))
                self._parse_ast(tree, rel_path)
            except Exception as e:
                print(f"Warning: could not parse {file_path}: {e}")

        for key, node in self.nodes.items():
            for dep in node.dependencies:
                for target_key, target_node in self.nodes.items():
                    if target_node.name == dep or dep in target_node.file_path:
                        target_node.dependents.add(key)

    def _parse_ast(self, tree: ast.AST, file_path: str) -> None:
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                key = f"{file_path}:{node.name}"
                code_node = CodeNode(node.name, "function", file_path, node.lineno)
                for sub in ast.walk(node):
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name):
                        code_node.dependencies.add(sub.func.id)
                self.nodes[key] = code_node
            elif isinstance(node, ast.ClassDef):
                key = f"{file_path}:{node.name}"
                code_node = CodeNode(node.name, "class", file_path, node.lineno)
                for base in node.bases:
                    if isinstance(base, ast.Name):
                        code_node.dependencies.add(base.id)
                self.nodes[key] = code_node

    def query_impact(self, symbol_name: str) -> list[dict[str, Any]]:
        impacted = []
        for key, node in self.nodes.items():
            if symbol_name == node.name or symbol_name in node.file_path:
                impacted.append(node.to_dict())
                for dep_key in node.dependents:
                    if dep_key in self.nodes:
                        impacted.append(self.nodes[dep_key].to_dict())
        return impacted

    def save_to_json(self, output_path: Path) -> None:
        data = {k: v.to_dict() for k, v in self.nodes.items()}
        output_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


if __name__ == "__main__":
    graph = SemanticCodeGraph()
    graph.build_graph()
    out = get_project_root() / ".semantic_graph.json"
    graph.save_to_json(out)
    print(f"Semantic graph built with {len(graph.nodes)} nodes. Saved to {out}")

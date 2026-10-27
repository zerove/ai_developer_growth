"""Semantic Code Knowledge Graph (Pillar 1)

Extracts AST-based code nodes (classes, functions, calls, imports) and builds
a local semantic dependency graph to analyze upstream/downstream impact of changes.
"""

from __future__ import annotations

import ast
import json
import os
from pathlib import Path
from typing import Any

# ADR-079: 统一路径引导 —— `python -m tools.scripts.X`（包上下文）与
# `python tools/scripts/X.py`（path[0]=tools/scripts）均由 _bootstrap 幂等补齐仓库根。
try:  # python -m tools.scripts.X (根已在 path)
    from tools.scripts import _bootstrap
except ModuleNotFoundError:  # python tools/scripts/X.py (path[0]=tools/scripts)
    import _bootstrap  # type: ignore[no-redef]  # noqa: F401


from tools.scripts._common import get_project_root  # noqa: E402


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
        """构建代码图 (V2.21 P5-30 拆分: 抽 _build_name_index + _resolve_dependencies)."""
        self._parse_all_files()
        name_to_keys = self._build_name_index()
        self._resolve_dependencies(name_to_keys)

    def _parse_all_files(self) -> None:
        """遍历所有 .py 文件, 解析 AST 构建初始 nodes (方法级 helper).

        跳过 .venv/build/dist/.git/__pycache__ 目录.
        """
        skip = {".venv", "build", "dist", ".git", "__pycache__"}
        # os.walk + 就地剪枝: glob("**/*.py") 仍会枚举被排除目录下的全部 .py
        # root 必须 resolve: os.walk 产出的 root 不带 "./" 前缀, 直接 relative_to
        # 未归一化的 self.root_dir (如 Path(".")) 会抛 ValueError。
        walk_root = self.root_dir.resolve()
        for root, dirs, filenames in os.walk(walk_root):
            dirs[:] = [d for d in dirs if d not in skip]
            for name in filenames:
                if not name.endswith(".py"):
                    continue
                file_path = Path(root) / name
                try:
                    content = file_path.read_text(encoding="utf-8")
                    tree = ast.parse(content, filename=str(file_path))
                    rel_path = str(file_path.relative_to(walk_root))
                    self._parse_ast(tree, rel_path)
                except Exception as e:
                    print(f"Warning: could not parse {file_path}: {e}")

    def _build_name_index(self) -> dict[str, set[str]]:
        """构建 name → keys 索引, O(1) 依赖解析 (方法级 helper).

        Returns:
            {node.name: {key1, key2, ...}} 索引
        """
        name_to_keys: dict[str, set[str]] = {}
        for key, node in self.nodes.items():
            name_to_keys.setdefault(node.name, set()).add(key)
        return name_to_keys

    def _resolve_dependencies(self, name_to_keys: dict[str, set[str]]) -> None:
        """用 name 索引解析依赖, 设置 dependents 集合 (方法级 helper, 内部修改 self.nodes).

        Args:
            name_to_keys: _build_name_index 返回的索引
        """
        for key, node in self.nodes.items():
            for dep in node.dependencies:
                # Direct name match
                if dep in name_to_keys:
                    for target_key in name_to_keys[dep]:
                        if target_key != key:
                            self.nodes[target_key].dependents.add(key)

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

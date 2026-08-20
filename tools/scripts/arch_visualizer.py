#!/usr/bin/env python3
"""Architecture Dependency Graph & Drift Visualizer: builds import graph and exports Mermaid diagrams."""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


def scan_python_imports(root_dir: Path) -> dict[str, set[str]]:
    """Scan Python files and build module import dependency graph."""
    graph: dict[str, set[str]] = {}
    for py_file in root_dir.rglob("*.py"):
        if any(
            p in py_file.parts
            for p in [".git", ".venv", "venv", "__pycache__", ".pytest_cache"]
        ):
            continue
        rel_path = str(py_file.relative_to(root_dir).with_suffix("")).replace("/", ".")
        graph[rel_path] = set()

        try:
            tree = ast.parse(py_file.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        graph[rel_path].add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        graph[rel_path].add(node.module.split(".")[0])
        except (SyntaxError, OSError):
            continue
    return graph


def generate_mermaid_diagram(graph: dict[str, set[str]]) -> str:
    """Generate Mermaid.js graph markup from dependency graph."""
    lines = ["graph TD;"]
    added_edges = set()
    for mod, imports in sorted(graph.items()):
        short_mod = mod.split(".")[-1]
        for imp in sorted(imports):
            if imp in graph or any(imp in m for m in graph):
                edge = f"    {short_mod} --> {imp};"
                if edge not in added_edges:
                    lines.append(edge)
                    added_edges.add(edge)
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Architecture Dependency Graph Visualizer"
    )
    parser.add_argument(
        "--path", type=Path, default=Path("tools/scripts"), help="Root path to scan"
    )
    parser.add_argument(
        "--output", type=Path, help="Optional output markdown/mermaid file"
    )
    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path {args.path} does not exist.", file=sys.stderr)
        return 1

    graph = scan_python_imports(args.path)
    mermaid = generate_mermaid_diagram(graph)

    print("## 🏗️ Architecture Dependency Graph (Mermaid)")
    print("```mermaid")
    print(mermaid)
    print("```")

    if args.output:
        args.output.write_text(
            f"## Architecture Dependency Graph\n\n```mermaid\n{mermaid}\n```\n",
            encoding="utf-8",
        )
        print(f"✅ Mermaid graph saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())

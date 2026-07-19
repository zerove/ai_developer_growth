import os
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Set


@dataclass
class ADRNode:
    id: str
    title: str
    dependencies: Set[str]
    supersedes: Set[str]
    content: str

class DecisionGraph:
    """
    Parses ADR files and builds a directed graph of architectural decisions.
    Allows for causal tracing and visualization of decision evolution.
    """
    def __init__(self, adr_dir: str):
        self.adr_dir = adr_dir
        self.nodes: Dict[str, ADRNode] = {}
        self.load_graph()

    def load_graph(self) -> None:
        """Scans the ADR directory and parses all ADR files into the graph."""
        if not os.path.exists(self.adr_dir):
            return

        for file in os.listdir(self.adr_dir):
            if file.endswith(".md"):
                self._parse_adr_file(os.path.join(self.adr_dir, file))

    def _parse_adr_file(self, path: str) -> None:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

            # Extract ID and Title: # ADR-001: The Title
            id_match = re.search(r"#\s*(ADR-\d+):?\s*(.*)", content)
            if not id_match:
                return

            adr_id = id_match.group(1)
            title = id_match.group(2).strip()

            # Extract Depends On
            depends_on = set()
            dep_match = re.search(r"- \*\*Depends On:\*\* \[(.*?)\]", content)
            if dep_match:
                deps = dep_match.group(1).split(",")
                depends_on = {d.strip() for d in deps if d.strip()}

            # Extract Supersedes
            supersedes = set()
            sup_match = re.search(r"- \*\*Supersedes:\*\* \[(.*?)\]", content)
            if sup_match:
                sups = sup_match.group(1).split(",")
                supersedes = {s.strip() for s in sups if s.strip()}

            self.nodes[adr_id] = ADRNode(
                id=adr_id,
                title=title,
                dependencies=depends_on,
                supersedes=supersedes,
                content=content
            )

    def trace_causality(self, start_id: str, visited: Optional[List[str]] = None) -> List[str]:
        """
        Returns the causal chain leading up to a specific decision.
        """
        if visited is None:
            visited = []

        if start_id not in self.nodes or start_id in visited:
            return list(visited)

        visited.append(start_id)
        node = self.nodes[start_id]

        # Recurse through dependencies
        for dep in node.dependencies:
            self.trace_causality(dep, visited)

        return visited

    def generate_mermaid(self) -> str:
        """
        Generates a Mermaid.js graph definition of the decision tree.
        """
        if not self.nodes:
            return "graph TD\n  Empty[No ADRs found]"

        lines = ["graph TD"]
        for node_id, node in self.nodes.items():
            # Node definition with title
            lines.append(f'  {node_id}["{node_id}: {node.title}"]')

            # Dependency edges
            for dep in node.dependencies:
                lines.append(f"  {dep} --> {node_id}")

            # Supersedes edges (dashed)
            for sup in node.supersedes:
                lines.append(f"  {sup} -.-> {node_id}")

        return "\n".join(lines)

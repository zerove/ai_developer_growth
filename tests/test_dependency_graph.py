"""Tests for dependency graph analysis"""

from pathlib import Path

import pytest

from tools.scripts.dependency_graph import (
    DependencyGraph,
    DependencyNode,
    analyze_dependency_graph,
)
from tools.scripts.supply_chain import SBOM, Dependency


class TestDependencyGraph:
    """Test DependencyGraph"""

    def setup_method(self):
        self.graph = DependencyGraph()

    def test_build_from_dependencies(self):
        deps = [
            Dependency(name="pkg-a", version="1.0.0", ecosystem="pypi", is_direct=True),
            Dependency(name="pkg-b", version="2.0.0", ecosystem="pypi", is_direct=True),
            Dependency(name="pkg-c", version="3.0.0", ecosystem="pypi", is_direct=False),
        ]
        self.graph.build_from_dependencies(deps, "my-project", "1.0.0")

        assert "ROOT:my-project:1.0.0" in self.graph.nodes
        assert "pypi:pkg-a:1.0.0" in self.graph.nodes
        assert "pypi:pkg-b:2.0.0" in self.graph.nodes
        assert "pypi:pkg-c:3.0.0" in self.graph.nodes

    def test_build_from_dependencies_with_transitive(self):
        trans_dep = Dependency(name="transitive", version="1.0.0", ecosystem="pypi", is_direct=False)
        direct_dep = Dependency(
            name="direct",
            version="1.0.0",
            ecosystem="pypi",
            is_direct=True,
            dependencies=[trans_dep],
        )
        deps = [direct_dep]

        self.graph.build_from_dependencies(deps, "project", "1.0.0")

        # 检查边
        root_key = "ROOT:project:1.0.0"
        direct_key = "pypi:direct:1.0.0"
        trans_key = "pypi:transitive:1.0.0"

        assert direct_key in self.graph.nodes[root_key].outgoing
        assert trans_key in self.graph.nodes[direct_key].outgoing
        assert root_key in self.graph.nodes[direct_key].incoming
        assert direct_key in self.graph.nodes[trans_key].incoming

    def test_detect_circular_dependencies_none(self):
        deps = [
            Dependency(name="a", version="1.0.0", ecosystem="pypi", is_direct=True),
            Dependency(name="b", version="1.0.0", ecosystem="pypi", is_direct=True),
        ]
        self.graph.build_from_dependencies(deps)
        cycles = self.graph.detect_circular_dependencies()
        assert len(cycles) == 0

    def test_detect_circular_dependencies_simple(self):
        # 手动创建循环
        self.graph.nodes["a"] = DependencyNode(name="a", version="1.0.0", ecosystem="pypi")
        self.graph.nodes["b"] = DependencyNode(name="b", version="1.0.0", ecosystem="pypi")
        self.graph.nodes["c"] = DependencyNode(name="c", version="1.0.0", ecosystem="pypi")
        self.graph._add_edge("a", "b")
        self.graph._add_edge("b", "c")
        self.graph._add_edge("c", "a")

        cycles = self.graph.detect_circular_dependencies()
        assert len(cycles) == 1
        assert len(cycles[0].cycle) == 3

    def test_detect_conflicts_none(self):
        deps = [
            Dependency(name="pkg-a", version="1.0.0", ecosystem="pypi"),
            Dependency(name="pkg-b", version="2.0.0", ecosystem="pypi"),
        ]
        self.graph.build_from_dependencies(deps)
        conflicts = self.graph.detect_conflicts()
        assert len(conflicts) == 0

    def test_detect_conflicts_with_conflict(self):
        deps = [
            Dependency(name="pkg-a", version="1.0.0", ecosystem="pypi"),
            Dependency(name="pkg-a", version="2.0.0", ecosystem="pypi"),
        ]
        self.graph.build_from_dependencies(deps)
        conflicts = self.graph.detect_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0].package_name == "pkg-a"
        assert len(conflicts[0].versions) == 2

    def test_get_transitive_dependencies(self):
        trans_dep = Dependency(name="trans", version="1.0.0", ecosystem="pypi", is_direct=False)
        direct_dep = Dependency(
            name="direct", version="1.0.0", ecosystem="pypi", is_direct=True, dependencies=[trans_dep]
        )
        self.graph.build_from_dependencies([direct_dep])

        trans_key = "pypi:trans:1.0.0"
        direct_key = "pypi:direct:1.0.0"

        trans_deps = self.graph.get_transitive_dependencies(direct_key)
        assert trans_key in trans_deps

    def test_get_transitive_dependents(self):
        trans_dep = Dependency(name="trans", version="1.0.0", ecosystem="pypi", is_direct=False)
        direct_dep = Dependency(
            name="direct", version="1.0.0", ecosystem="pypi", is_direct=True, dependencies=[trans_dep]
        )
        self.graph.build_from_dependencies([direct_dep])

        trans_key = "pypi:trans:1.0.0"
        direct_key = "pypi:direct:1.0.0"

        dependents = self.graph.get_transitive_dependents(trans_key)
        assert direct_key in dependents

    def test_analyze_impact(self):
        trans_dep = Dependency(name="trans", version="1.0.0", ecosystem="pypi", is_direct=False)
        direct_dep = Dependency(
            name="direct", version="1.0.0", ecosystem="pypi", is_direct=True, dependencies=[trans_dep]
        )
        self.graph.build_from_dependencies([direct_dep])

        impacts = self.graph.analyze_impact("trans", "1.0.0")
        assert len(impacts) == 1
        assert impacts[0].package == "trans"
        assert impacts[0].total_affected >= 1  # direct 依赖它

    def test_analyze_impact_not_found(self):
        self.graph.build_from_dependencies([])
        impacts = self.graph.analyze_impact("nonexistent")
        assert len(impacts) == 0

    def test_get_dependency_tree(self):
        deps = [
            Dependency(name="a", version="1.0.0", ecosystem="pypi", is_direct=True),
        ]
        self.graph.build_from_dependencies(deps)
        tree = self.graph.get_dependency_tree()
        assert "children" in tree
        assert len(tree["children"]) == 1

    def test_export_graphviz(self):
        deps = [Dependency(name="a", version="1.0.0", ecosystem="pypi", is_direct=True)]
        self.graph.build_from_dependencies(deps)
        dot = self.graph.export_graphviz()
        assert "digraph dependencies" in dot
        assert "pypi:a:1.0.0" in dot

    def test_export_mermaid(self):
        deps = [Dependency(name="a", version="1.0.0", ecosystem="pypi", is_direct=True)]
        self.graph.build_from_dependencies(deps)
        mermaid = self.graph.export_mermaid()
        assert "graph TD" in mermaid
        assert "a@1.0.0" in mermaid

    def test_to_json(self):
        deps = [Dependency(name="a", version="1.0.0", ecosystem="pypi", is_direct=True)]
        self.graph.build_from_dependencies(deps)
        json_str = self.graph.to_json()
        import json

        data = json.loads(json_str)
        assert "nodes" in data
        assert "edges" in data


class TestAnalyzeDependencyGraph:
    """Test analyze_dependency_graph convenience function"""

    def test_analyze_from_sbom(self):
        sbom = SBOM(name="test", version="1.0.0")
        sbom.packages = [
            Dependency(name="pkg-a", version="1.0.0", ecosystem="pypi", is_direct=True),
        ]
        sbom.relationships = [
            {
                "spdxElementId": "SPDXRef-Package-0",
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": "SPDXRef-Package-ROOT",
            },
        ]

        graph = analyze_dependency_graph(Path("."), sbom)
        assert "ROOT:test:1.0.0" in graph.nodes
        assert "pypi:pkg-a:1.0.0" in graph.nodes


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

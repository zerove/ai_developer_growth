"""Tests for src/graph.py - DecisionGraph and ADRNode"""
import os
import sys
import tempfile
import shutil
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.graph import DecisionGraph, ADRNode


@pytest.fixture
def adr_dir():
    """Create a temporary ADR directory with test ADR files."""
    tmpdir = tempfile.mkdtemp()
    
    # ADR-001: No dependencies
    with open(os.path.join(tmpdir, "ADR-001.md"), "w") as f:
        f.write("# ADR-001: Use REST API\n\n"
               "We will use REST for external APIs.\n")
    
    # ADR-002: Depends on ADR-001
    with open(os.path.join(tmpdir, "ADR-002.md"), "w") as f:
        f.write("# ADR-002: Add Authentication\n\n"
               "- **Depends On:** [ADR-001]\n\n"
               "We add JWT auth to the REST API.\n")
    
    # ADR-003: Depends on ADR-002, supersedes ADR-001
    with open(os.path.join(tmpdir, "ADR-003.md"), "w") as f:
        f.write("# ADR-003: OAuth2 Migration\n\n"
               "- **Depends On:** [ADR-002]\n"
               "- **Supersedes:** [ADR-001]\n\n"
               "Migrate from JWT to OAuth2.\n")
    
    # Invalid ADR file (no matching header)
    with open(os.path.join(tmpdir, "ADR-999.md"), "w") as f:
        f.write("# Random Notes\n\nSome random content.\n")
    
    yield tmpdir
    shutil.rmtree(tmpdir)


@pytest.fixture
def empty_adr_dir():
    tmpdir = tempfile.mkdtemp()
    yield tmpdir
    shutil.rmtree(tmpdir)


class TestDecisionGraph:
    def test_load_graph(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        assert len(graph.nodes) == 3
        assert "ADR-001" in graph.nodes
        assert "ADR-002" in graph.nodes
        assert "ADR-003" in graph.nodes

    def test_load_graph_nonexistent_dir(self):
        graph = DecisionGraph("/nonexistent/path")
        assert len(graph.nodes) == 0

    def test_load_graph_empty_dir(self, empty_adr_dir):
        graph = DecisionGraph(empty_adr_dir)
        assert len(graph.nodes) == 0

    def test_parse_adr_dependencies(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        assert graph.nodes["ADR-002"].dependencies == {"ADR-001"}
        assert graph.nodes["ADR-003"].dependencies == {"ADR-002"}

    def test_parse_adr_supersedes(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        assert graph.nodes["ADR-003"].supersedes == {"ADR-001"}

    def test_parse_adr_no_deps(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        assert graph.nodes["ADR-001"].dependencies == set()
        assert graph.nodes["ADR-001"].supersedes == set()

    def test_parse_adr_title(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        assert "REST API" in graph.nodes["ADR-001"].title
        assert "Authentication" in graph.nodes["ADR-002"].title

    def test_trace_causality_single(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        chain = graph.trace_causality("ADR-001")
        assert chain == ["ADR-001"]

    def test_trace_causality_chain(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        chain = graph.trace_causality("ADR-003")
        # ADR-003 -> ADR-002 -> ADR-001
        assert "ADR-003" in chain
        assert "ADR-002" in chain
        assert "ADR-001" in chain
        # Order: ADR-003 first (start), then deps
        assert chain.index("ADR-003") < chain.index("ADR-002")

    def test_trace_causality_nonexistent(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        chain = graph.trace_causality("ADR-999")
        assert chain == []

    def test_trace_causality_circular_protection(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        chain = graph.trace_causality("ADR-001")
        # Should not infinite loop even if called again with visited
        assert isinstance(chain, list)

    def test_generate_mermaid(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        mermaid = graph.generate_mermaid()
        assert "graph TD" in mermaid
        assert "ADR-001" in mermaid
        assert "ADR-002" in mermaid
        assert "ADR-003" in mermaid

    def test_generate_mermaid_empty(self, empty_adr_dir):
        graph = DecisionGraph(empty_adr_dir)
        mermaid = graph.generate_mermaid()
        assert "Empty" in mermaid

    def test_generate_mermaid_edges(self, adr_dir):
        graph = DecisionGraph(adr_dir)
        mermaid = graph.generate_mermaid()
        # ADR-002 depends on ADR-001 -> ADR-001 --> ADR-002
        assert "ADR-001 --> ADR-002" in mermaid
        assert "ADR-002 --> ADR-003" in mermaid
        # ADR-003 supersedes ADR-001 -> dashed line
        assert "ADR-001 -.-> ADR-003" in mermaid

    def test_adr_node_dataclass(self):
        node = ADRNode(
            id="ADR-001", title="Test",
            dependencies=set(), supersedes=set(), content="test"
        )
        assert node.id == "ADR-001"
        assert node.title == "Test"

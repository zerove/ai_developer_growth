"""Comprehensive Unit & Integration Tests for AI-Native SDLC Modules

Tests semantic knowledge graph, architecture drift guard, multi-llm router,
autonomous swarm, self-evolving engine, telemetry, and workflow pipeline.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add tools/scripts and orchestration paths
sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "examples" / "multi-agent-orch" / "src" / "orchestration"))

import pytest
from semantic_code_graph import SemanticCodeGraph, CodeNode
from architecture_drift_guard import ArchitectureDriftGuard
from multi_llm_router import MultiLLMRouter
from autonomous_swarm_engine import AutonomousSwarmOrchestrator
from self_evolving_engine import SelfEvolvingEngine
from metrics_telemetry import MetricsTelemetry
from intent_delivery import IntentDeliveryEngine
from context_streamer import ContextStreamer
from ai_slop_scanner import AISlopScanner
from runtime_verifier import RuntimeVerifier


def test_code_node_serialization():
    node = TestNode = CodeNode("test_func", "function", "test.py", 10)
    node.dependencies.add("helper")
    d = node.to_dict()
    assert d["name"] == "test_func"
    assert d["node_type"] == "function"
    assert "helper" in d["dependencies"]


def test_semantic_graph_building(tmp_path: Path):
    graph = SemanticCodeGraph(tmp_path)
    graph.build_graph()
    assert isinstance(graph.nodes, dict)


def test_architecture_drift_guard(tmp_path: Path):
    guard = ArchitectureDriftGuard(tmp_path)
    violations = guard.check_layering()
    assert isinstance(violations, list)


def test_multi_llm_router():
    router = MultiLLMRouter()
    res = router.route_task("architecture_design")
    assert res["selected_model"] == "claude-opus-4-7"
    res_routine = router.route_task("routine_bug_fix")
    assert res_routine["selected_model"] == "gemini-3.5-flash-lite"


def test_autonomous_swarm(tmp_path: Path):
    orch = AutonomousSwarmOrchestrator(tmp_path)
    res = orch.execute_swarm_cycle("Test Task")
    assert res["status"] == "Swarm Execution Completed Successfully"
    assert len(res["stages"]) > 0


def test_self_evolving_engine(tmp_path: Path):
    engine = SelfEvolvingEngine(tmp_path)
    res = engine.evolve()
    assert "status" in res


def test_metrics_telemetry(tmp_path: Path):
    telemetry = MetricsTelemetry(tmp_path)
    data = telemetry.collect_metrics()
    assert "test_coverage_percent" in data
    assert data["test_coverage_percent"] == 84.0


def test_intent_delivery():
    engine = IntentDeliveryEngine("Build REST API")
    res = engine.process_intent()
    assert res["intent"] == "Build REST API"
    assert len(res["execution_plan"]) > 0


def test_context_streamer(tmp_path: Path):
    f = tmp_path / "sample.txt"
    f.write_text("line1\nline2\nline3\n", encoding="utf-8")
    streamer = ContextStreamer(tmp_path, page_size=2)
    chunks = streamer.stream_file_chunks(f)
    assert len(chunks) == 2


def test_ai_slop_scanner(tmp_path: Path):
    scanner = AISlopScanner(tmp_path)
    findings = scanner.scan_codebase()
    assert isinstance(findings, list)


def test_runtime_verifier(tmp_path: Path):
    verifier = RuntimeVerifier(tmp_path)
    success, _ = verifier.run_tests()
    assert success is True

"""Coverage tests for AI-Native SDLC modules that previously had 0% coverage.

Covers:
- jcode_cross_platform_runner: task dispatch and unknown-task handling
- jcode_setup_wizard: .jcode/rules dir creation and opencode.json config
- self_healing_ci: self-healing loop execution
- ai_native_dashboard: dashboard render with/without telemetry/graph data
- ai_native_mcp_server: tool call dispatch (query_semantic_graph, architecture guard, unknown)
- case_study_pipeline: case study markdown generation
- rules_engine.feedback: false-positive feedback, downgrade threshold logic
- rules_engine.rule_docs_mapper: keyword extraction, mapping build/rebuild/query
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts" / "hooks"))

from ai_native_dashboard import AIDashboard
from ai_native_mcp_server import AINativeMCPServer
from case_study_pipeline import CaseStudyPipeline
from jcode_cross_platform_runner import run_task
from jcode_setup_wizard import JCodeSetupWizard
from self_healing_ci import SelfHealingCILoop

from tools.scripts.rules_engine.feedback import (
    AUTO_DOWNGRADE_THRESHOLD,
    MIN_REPORTS_FOR_DOWNGRADE,
    _load_feedback,
    get_effective_severity,
    get_feedback_stats,
    mark_false_positive,
    reset_feedback,
)
from tools.scripts.rules_engine.rule_docs_mapper import (
    build_mapping,
    extract_keywords_from_docs,
    extract_keywords_from_rule,
    query_mapping,
    rebuild_mapping,
)


# ─────────────────────────────────────────────────────────────
# jcode_cross_platform_runner
# ─────────────────────────────────────────────────────────────

def test_cross_platform_unknown_task_returns_1(capsys):
    """Unknown task should print available tasks and return 1."""
    assert run_task("nonexistent-task") == 1
    out = capsys.readouterr().out
    assert "Unknown task" in out


@patch("jcode_cross_platform_runner.run_command")
def test_cross_platform_known_task_success(mock_run, capsys):
    """Known task with success exit code returns 0."""
    mock_run.return_value = (0, "ok")
    assert run_task("check") == 0
    out = capsys.readouterr().out
    assert "completed successfully" in out
    mock_run.assert_called_once()


@patch("jcode_cross_platform_runner.run_command")
def test_cross_platform_known_task_failure(mock_run, capsys):
    """Known task with failure exit code returns 1."""
    mock_run.return_value = (1, "boom")
    assert run_task("swarm-run") == 1
    out = capsys.readouterr().out
    assert "failed" in out


# ─────────────────────────────────────────────────────────────
# jcode_setup_wizard
# ─────────────────────────────────────────────────────────────

def test_setup_wizard_creates_rules_dir(tmp_path: Path):
    """Wizard creates .jcode/rules and does not overwrite existing opencode.json."""
    (tmp_path / "opencode.json").write_text('{"keep": true}', encoding="utf-8")
    wizard = JCodeSetupWizard(root_dir=tmp_path)
    wizard.run_setup()
    assert (tmp_path / ".jcode" / "rules").is_dir()
    # Existing opencode.json must NOT be overwritten
    assert json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8")) == {"keep": True}


def test_setup_wizard_writes_mcp_config(tmp_path: Path):
    """Wizard writes opencode.json when it does not exist yet."""
    wizard = JCodeSetupWizard(root_dir=tmp_path)
    wizard.run_setup()
    cfg = json.loads((tmp_path / "opencode.json").read_text(encoding="utf-8"))
    assert "mcp" in cfg
    assert "ai-native-sdlc" in cfg["mcp"]


# ─────────────────────────────────────────────────────────────
# self_healing_ci
# ─────────────────────────────────────────────────────────────

def test_self_healing_ci_returns_true():
    """Self-healing loop returns True when codebase is healthy."""
    loop = SelfHealingCILoop(max_retries=2)
    assert loop.max_retries == 2
    assert loop.execute_with_healing() is True


# ─────────────────────────────────────────────────────────────
# ai_native_dashboard
# ─────────────────────────────────────────────────────────────

def test_dashboard_render_without_data(tmp_path: Path, capsys):
    """Dashboard renders gracefully when no telemetry/graph data exists."""
    dash = AIDashboard(root_dir=tmp_path)
    dash.render()
    out = capsys.readouterr().out
    assert "Dashboard rendered successfully" in out
    assert "No metrics generated" in out


def test_dashboard_render_with_telemetry(tmp_path: Path, capsys):
    """Dashboard shows telemetry metrics and graph node count when data exists."""
    (tmp_path / ".quality-trends").mkdir(parents=True)
    (tmp_path / ".quality-trends" / "telemetry.json").write_text(
        json.dumps({"tests": 2513, "coverage": 80.4}), encoding="utf-8"
    )
    (tmp_path / ".semantic_graph.json").write_text(
        json.dumps({"node1": {"type": "function"}, "node2": {"type": "class"}}), encoding="utf-8"
    )
    dash = AIDashboard(root_dir=tmp_path)
    dash.render()
    out = capsys.readouterr().out
    assert "tests" in out
    assert "2" in out  # node count


# ─────────────────────────────────────────────────────────────
# ai_native_mcp_server
# ─────────────────────────────────────────────────────────────

def test_mcp_unknown_tool():
    server = AINativeMCPServer()
    res = server.handle_tool_call("nope", {})
    assert res["status"] == "error"
    assert "Unknown tool" in res["message"]


def test_mcp_query_semantic_graph_without_graph(tmp_path: Path):
    server = AINativeMCPServer()
    with patch.object(server, "root_dir", tmp_path):
        res = server.handle_tool_call("query_semantic_graph", {"symbol": "foo"})
    assert res["status"] == "error"


def test_mcp_query_semantic_graph_with_graph(tmp_path: Path):
    (tmp_path / ".semantic_graph.json").write_text(
        json.dumps({"auth_login": {"type": "function"}, "auth_logout": {"type": "function"}}),
        encoding="utf-8",
    )
    server = AINativeMCPServer()
    with patch.object(server, "root_dir", tmp_path):
        res = server.handle_tool_call("query_semantic_graph", {"symbol": "auth"})
    assert res["status"] == "success"
    assert len(res["matches"]) == 2


def test_mcp_architecture_guard(tmp_path: Path):
    server = AINativeMCPServer()
    with patch.object(server, "root_dir", tmp_path):
        res = server.handle_tool_call("run_architecture_guard", {})
    assert res["status"] == "success"
    assert isinstance(res["violations"], list)


# ─────────────────────────────────────────────────────────────
# case_study_pipeline
# ─────────────────────────────────────────────────────────────

def test_case_study_pipeline_generates_file(tmp_path: Path):
    pipeline = CaseStudyPipeline(root_dir=tmp_path)
    path = pipeline.generate_case_study("Test Case Study", "Automated testing", "5x")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert "Test Case Study" in content
    assert "5x" in content
    assert path.name == "test-case-study.md"


# ─────────────────────────────────────────────────────────────
# rules_engine.feedback
# ─────────────────────────────────────────────────────────────

def test_feedback_load_nonexistent_returns_empty():
    with patch("tools.scripts.rules_engine.feedback.FEEDBACK_FILE", Path("/nonexistent/feedback.json")):
        data = _load_feedback()
    assert data == {"rules": {}, "total_feedback": 0}


def test_feedback_mark_and_stats(tmp_path: Path):
    fb_file = tmp_path / "fb.json"
    with patch("tools.scripts.rules_engine.feedback.FEEDBACK_FILE", fb_file):
        mark_false_positive("py-bare-except", "file.py", "warning")
        mark_false_positive("py-bare-except", "file2.py", "warning")
        stats = get_feedback_stats()
    assert stats["total_feedback"] == 2
    assert stats["tracked_rules"] == 1
    assert fb_file.exists()


def test_feedback_severity_downgrade_after_repeated_fps(tmp_path: Path):
    """5+ false positives (100% rate >= 60%) triggers severity downgrade."""
    fb_file = tmp_path / "fb.json"
    with patch("tools.scripts.rules_engine.feedback.FEEDBACK_FILE", fb_file):
        assert get_effective_severity("rule-x", "error") == "error"  # before
        for i in range(MIN_REPORTS_FOR_DOWNGRADE):
            mark_false_positive("rule-x", f"f{i}.py", "error")
        assert get_effective_severity("rule-x", "error") == "warning"
        assert get_effective_severity("rule-x", "warning") == "info"
        assert get_effective_severity("rule-x", "info") == "info"  # floor


def test_feedback_reset(tmp_path: Path):
    fb_file = tmp_path / "fb.json"
    with patch("tools.scripts.rules_engine.feedback.FEEDBACK_FILE", fb_file):
        mark_false_positive("rule-a", "f.py", "warning")
        reset_feedback()
        stats = get_feedback_stats()
    assert stats["total_feedback"] == 0
    assert stats["tracked_rules"] == 0


def test_feedback_threshold_constants():
    assert AUTO_DOWNGRADE_THRESHOLD == 0.6
    assert MIN_REPORTS_FOR_DOWNGRADE == 5


# ─────────────────────────────────────────────────────────────
# rules_engine.rule_docs_mapper
# ─────────────────────────────────────────────────────────────

def test_extract_keywords_from_rule():
    kws = extract_keywords_from_rule("py-bare-except", {"message": "Avoid bare except", "category": "error"})
    assert "py" in kws
    assert "python" in kws  # language mapping
    assert "avoid" in kws
    assert "except" in kws


def test_extract_keywords_from_docs():
    """extract_keywords_from_docs uses global PROJECT_ROOT for relative paths,
    so test against the real docs directory (read-only)."""
    docs_dir = Path(__file__).parent.parent / "docs"
    kws = extract_keywords_from_docs(docs_dir)
    assert len(kws) > 0
    # each key is a relative path, keywords are non-empty
    for rel_path, kw_list in kws.items():
        assert rel_path.endswith(".md")
        assert len(kw_list) > 0


def test_build_mapping_uses_builtin(tmp_path: Path):
    """When rule_dir has no rules, builtin mappings don't appear (need rules to trigger),
    but extract_keywords still works on empty dirs."""
    mapping = build_mapping(rule_dir=tmp_path, docs_dir=tmp_path, case_studies=False)
    assert mapping == {}  # no rules to map


def test_rebuild_mapping(tmp_path: Path):
    out = tmp_path / "mapping.json"
    mapping = rebuild_mapping(rule_dir=tmp_path, output_path=out)
    assert out.exists()
    assert isinstance(mapping, dict)


def test_query_mapping_unknown_rule(tmp_path: Path):
    """Querying without a mapping cache returns an empty list (not an error)."""
    res = query_mapping("no-such-rule", mapping_path=tmp_path / "nope.json")
    assert res == []


def test_query_mapping_existing_rule(tmp_path: Path):
    mapping_file = tmp_path / "mapping.json"
    mapping_file.write_text(json.dumps({"py-bare-except": [{"path": "docs/x.md", "reason": "y"}]}), encoding="utf-8")
    res = query_mapping("py-bare-except", mapping_path=mapping_file)
    assert len(res) == 1
    assert res[0]["path"] == "docs/x.md"
    # Unknown rule in existing mapping -> empty list
    assert query_mapping("other", mapping_path=mapping_file) == []

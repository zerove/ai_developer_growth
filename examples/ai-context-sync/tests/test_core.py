"""Tests for src/core.py — AIContextSync coordinator.

Covers all previously uncovered lines: 52, 79, 87, 107-108, 120-122, 127-139,
148-149, 161-162, 169-176.
"""

import os
from unittest.mock import MagicMock

from src.auditor import FeedbackManager, SpecAuditor, Violation
from src.core import AIContextSync
from src.evolution import EvolutionEngine
from src.guard import ArchitectureGuard
from src.llm_client import LLMClient
from src.orchestrator import WorkflowManager
from src.synthesizer import ContextSynthesizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_config_file(tmpdir: str) -> str:
    """Write a minimal config file and return its path."""
    cfg_path = os.path.join(tmpdir, ".ai-sync.json")
    import json

    with open(cfg_path, "w") as f:
        json.dump(
            {
                "llm": {"provider": "system", "model": "auto", "api_base": None},
                "settings": {
                    "ignore": [],
                    "context_file": "CONTEXT.md",
                    "adr_dir": os.path.join(tmpdir, "docs/adr"),
                    "specs_dir": os.path.join(tmpdir, "docs/specs"),
                },
            },
            f,
        )
    return cfg_path


def _build_sync(tmpdir: str, *, dry_run=False, synthesizer=None):
    """Create an AIContextSync with all deps injected (no real I/O)."""
    cfg_path = _make_config_file(tmpdir)
    kwargs = dict(
        config_path=cfg_path,
        dry_run=dry_run,
        llm_client=MagicMock(spec=LLMClient),
        analyzer=MagicMock(),
        guard=MagicMock(spec=ArchitectureGuard),
        auditor=MagicMock(spec=SpecAuditor),
        feedback=MagicMock(spec=FeedbackManager),
        evolution=MagicMock(spec=EvolutionEngine),
        orchestrator=MagicMock(spec=WorkflowManager),
        synthesizer=MagicMock(spec=ContextSynthesizer),
    )
    if synthesizer is not None:
        kwargs["synthesizer"] = synthesizer
    return AIContextSync(**kwargs)


# ===================================================================
# __init__ — line 52: else branch (injected synthesizer)
# ===================================================================


class TestInitSynthesizerInjection:
    """Cover line 52: synthesizer provided via kwarg."""

    def test_injected_synthesizer_is_used(self, tmp_path):
        tmpdir = str(tmp_path)
        mock_synth = MagicMock(spec=ContextSynthesizer)
        sync = _build_sync(tmpdir, synthesizer=mock_synth)
        assert sync.synthesizer is mock_synth


# ===================================================================
# _get_context_for_path — line 79: root boundary break
# ===================================================================


class TestGetContextForPath:
    """Cover line 79: parent_dir == current_dir triggers break."""

    def test_breaks_at_root(self, tmp_path, monkeypatch):
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        sync = _build_sync(tmpdir)
        # Point to a file at the tmpdir root so after one iteration
        # parent_dir == current_dir == tmpdir → break
        fake_file = os.path.join(tmpdir, "some_file.py")
        result = sync._get_context_for_path(fake_file)
        assert isinstance(result, list)

    def test_collects_context_files_upward(self, tmp_path, monkeypatch):
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        sync = _build_sync(tmpdir)
        # Create nested structure with CONTEXT.md at each level
        nested = os.path.join(tmpdir, "a", "b")
        os.makedirs(nested, exist_ok=True)
        root_ctx = os.path.join(tmpdir, sync.config.settings.context_file)
        mid_ctx = os.path.join(tmpdir, "a", sync.config.settings.context_file)
        with open(root_ctx, "w") as f:
            f.write("ROOT")
        with open(mid_ctx, "w") as f:
            f.write("MID")
        result = sync._get_context_for_path(os.path.join(nested, "x.py"))
        # Should contain both, ordered root-first
        assert "ROOT" in result
        assert "MID" in result
        assert result.index("ROOT") < result.index("MID")


# ===================================================================
# get_aggregated_context — line 87: empty affected_files
# ===================================================================


class TestGetAggregatedContext:
    """Cover line 87: returns '' for empty input."""

    def test_empty_files_returns_empty_string(self, tmp_path):
        tmpdir = str(tmp_path)
        sync = _build_sync(tmpdir)
        assert sync.get_aggregated_context([]) == ""


# ===================================================================
# sync — lines 107-108, 120-122, 127-139
# ===================================================================


class TestSync:
    """Cover sync() branches: empty diff, file write, dry_run, ADR trigger."""

    def test_empty_filtered_diff_skips(self, tmp_path, monkeypatch):
        """Lines 107-108: filtered_diff empty → early return."""
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        sync = _build_sync(tmpdir)
        sync.analyzer.get_last_commit_message.return_value = "msg"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = ""
        sync.synthesizer.synthesize_context_update.return_value = "updated"
        # Should return without writing anything
        sync.sync()

    def test_non_dry_run_writes_context(self, tmp_path, monkeypatch):
        """Lines 120-122: writes updated context to file."""
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        sync = _build_sync(tmpdir, dry_run=False)
        sync.analyzer.get_last_commit_message.return_value = "feat: add login"
        sync.analyzer.get_last_commit_diff.return_value = "diff content"
        sync.analyzer.filter_diff.return_value = "filtered"
        sync.synthesizer.synthesize_context_update.return_value = "NEW CONTEXT"
        # context_file = "CONTEXT.md" relative to cwd; create it
        ctx_path = os.path.join(tmpdir, "CONTEXT.md")
        with open(ctx_path, "w") as f:
            f.write("old")
        sync.sync()
        with open(ctx_path, "r") as f:
            content = f.read()
        assert content == "NEW CONTEXT"

    def test_dry_run_does_not_write_context(self, tmp_path, monkeypatch):
        """Lines 120-122: dry_run skips file write."""
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        sync = _build_sync(tmpdir, dry_run=True)
        sync.analyzer.get_last_commit_message.return_value = "fix: typo"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = "filtered"
        sync.synthesizer.synthesize_context_update.return_value = "UPDATED"
        # Make sure no file is created
        ctx_path = os.path.join(tmpdir, "CONTEXT.md")
        sync.sync()
        assert not os.path.exists(ctx_path)

    def test_adr_trigger_non_dry_run_creates_adr(self, tmp_path, monkeypatch):
        """Lines 127-139: #ADR in commit_msg creates ADR file."""
        tmpdir = str(tmp_path)
        monkeypatch.chdir(tmpdir)
        adr_dir = os.path.join(tmpdir, "docs", "adr")
        cfg_path = _make_config_file(tmpdir)
        # Override adr_dir in config
        import json

        with open(cfg_path, "r") as f:
            cfg_data = json.load(f)
        cfg_data["settings"]["adr_dir"] = adr_dir
        with open(cfg_path, "w") as f:
            json.dump(cfg_data, f)

        sync = AIContextSync(
            config_path=cfg_path,
            dry_run=False,
            llm_client=MagicMock(),
            analyzer=MagicMock(),
            synthesizer=MagicMock(),
            guard=MagicMock(),
            auditor=MagicMock(),
            feedback=MagicMock(),
            evolution=MagicMock(),
            orchestrator=MagicMock(),
        )
        sync.analyzer.get_last_commit_message.return_value = "feat: new module #ADR"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = "filtered"
        sync.synthesizer.synthesize_context_update.return_value = "ctx"
        sync.synthesizer.synthesize_adr.return_value = "# ADR: Test Decision\n\nSome content."

        # Ensure CONTEXT.md exists so the non-adr branch doesn't error
        ctx_path = os.path.join(tmpdir, "CONTEXT.md")
        with open(ctx_path, "w") as f:
            f.write("old")
        sync.sync()

        # Verify ADR file was created
        assert os.path.isdir(adr_dir)
        adr_files = [f for f in os.listdir(adr_dir) if f.startswith("ADR-") and f.endswith(".md")]
        assert len(adr_files) == 1
        with open(os.path.join(adr_dir, adr_files[0])) as f:
            assert "Test Decision" in f.read()

    def test_adr_trigger_dry_run_skips_write(self, tmp_path):
        """Lines 127-139: #ADR + dry_run does NOT create ADR file."""
        tmpdir = str(tmp_path)
        adr_dir = os.path.join(tmpdir, "docs", "adr")
        cfg_path = _make_config_file(tmpdir)
        import json

        with open(cfg_path, "r") as f:
            cfg_data = json.load(f)
        cfg_data["settings"]["adr_dir"] = adr_dir
        with open(cfg_path, "w") as f:
            json.dump(cfg_data, f)

        sync = AIContextSync(
            config_path=cfg_path,
            dry_run=True,
            llm_client=MagicMock(),
            analyzer=MagicMock(),
            synthesizer=MagicMock(),
            guard=MagicMock(),
            auditor=MagicMock(),
            feedback=MagicMock(),
            evolution=MagicMock(),
            orchestrator=MagicMock(),
        )
        sync.analyzer.get_last_commit_message.return_value = "feat: #ADR"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = "filtered"
        sync.synthesizer.synthesize_context_update.return_value = "ctx"

        ctx_path = os.path.join(os.getcwd(), "CONTEXT.md")
        existed = os.path.exists(ctx_path)
        try:
            if not existed:
                with open(ctx_path, "w") as f:
                    f.write("old")
            sync.sync()
        finally:
            if not existed and os.path.exists(ctx_path):
                os.remove(ctx_path)

        # No ADR directory should be created
        assert not os.path.exists(adr_dir)


# ===================================================================
# guard_check — lines 148-149
# ===================================================================


class TestGuardCheck:
    """Cover lines 148-149: empty filtered_diff in guard_check."""

    def test_no_changes_returns_message(self, tmp_path):
        tmpdir = str(tmp_path)
        sync = _build_sync(tmpdir)
        sync.analyzer.get_last_commit_message.return_value = "msg"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = ""
        result = sync.guard_check()
        assert result == "No changes to audit."


# ===================================================================
# spec_audit — lines 161-162, 169-176
# ===================================================================


class TestSpecAudit:
    """Cover spec_audit branches: empty diff, compliance, violations."""

    def test_no_changes_returns_message(self, tmp_path):
        """Lines 161-162."""
        tmpdir = str(tmp_path)
        sync = _build_sync(tmpdir)
        sync.analyzer.get_last_commit_message.return_value = "msg"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = ""
        result = sync.spec_audit()
        assert result == "No changes to audit."

    def test_all_compliant(self, tmp_path):
        """Lines 166-167: no violations returned."""
        tmpdir = str(tmp_path)
        sync = _build_sync(tmpdir)
        sync.analyzer.get_last_commit_message.return_value = "msg"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = "filtered"
        sync.auditor.audit.return_value = []
        result = sync.spec_audit()
        assert "comply" in result.lower()

    def test_violations_saved_and_reported(self, tmp_path):
        """Lines 169-176: violations loop + report construction."""
        tmpdir = str(tmp_path)
        sync = _build_sync(tmpdir)
        sync.analyzer.get_last_commit_message.return_value = "msg"
        sync.analyzer.get_last_commit_diff.return_value = "diff"
        sync.analyzer.filter_diff.return_value = "filtered"

        v1 = Violation(rule_id="R1", message="bad import", severity="Critical", file_path="a.py")
        v2 = Violation(rule_id="R2", message="missing type", severity="Warning", file_path="b.py")
        sync.auditor.audit.return_value = [v1, v2]

        result = sync.spec_audit()

        # feedback.save_violation called for each
        assert sync.feedback.save_violation.call_count == 2
        sync.feedback.save_violation.assert_any_call(v1)
        sync.feedback.save_violation.assert_any_call(v2)

        # Report contains both violations
        assert "2 violation" in result
        assert "[Critical]" in result
        assert "[Warning]" in result
        assert "bad import" in result
        assert "missing type" in result

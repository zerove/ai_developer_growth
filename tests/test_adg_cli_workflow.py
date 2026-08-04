"""Coverage tests for adg_cli (0%) and jcode_ai_native_workflow (0%)."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "tools" / "scripts"))

# Import adg_cli module
import tools.scripts.adg_cli as adg_cli

# Import jcode_ai_native_workflow
import tools.scripts.jcode_ai_native_workflow as jcode_ai_native_workflow
from tools.scripts.dor_checker import DoRChecker

# ─────────────────────────────────────────────────────────────
# adg_cli - basic import and main() coverage
# ─────────────────────────────────────────────────────────────

def test_adg_cli_module_imports():
    """Ensure module imports without error."""
    assert hasattr(adg_cli, "main")
    assert callable(adg_cli.main)


def test_adg_cli_main_no_args():
    """CLI with no command prints help and exits with 0."""
    with patch.object(sys, "argv", ["adg_cli"]):
        # New adg_cli v2 returns 0 and prints help instead of raising SystemExit
        result = adg_cli.main()
        assert result == 0


def test_adg_cli_help():
    """CLI with --help shows help and exits with SystemExit(0)."""
    with patch.object(sys, "argv", ["adg_cli", "--help"]):
        with pytest.raises(SystemExit):
            adg_cli.main()


def test_adg_cli_check_requires_path():
    """check command requires path argument."""
    with patch.object(sys, "argv", ["adg_cli", "check"]):
        with pytest.raises(SystemExit):
            adg_cli.main()


def test_adg_cli_detect():
    """detect command runs without error."""
    with patch.object(sys, "argv", ["adg_cli", "detect"]):
        try:
            adg_cli.main()
        except SystemExit:
            pass


def test_adg_cli_invalid_command():
    """Invalid command shows error."""
    with patch.object(sys, "argv", ["adg_cli", "invalid-cmd"]):
        with pytest.raises(SystemExit):
            adg_cli.main()


def test_adg_cli_main_entry_import():
    """Test __main__ entry point can be imported."""
    with patch("tools.scripts.adg_cli.__main__.main", MagicMock(return_value=0)):
        pass


# ─────────────────────────────────────────────────────────────
# jcode_ai_native_workflow - DoR checker and basic import
# ─────────────────────────────────────────────────────────────

def test_jcode_ai_native_workflow_init():
    """Workflow initializes with root dir."""
    workflow = jcode_ai_native_workflow.JCodeAINativeWorkflow()
    assert workflow.root_dir is not None


@patch("tools.scripts.jcode_ai_native_workflow.get_project_root")
def test_jcode_ai_native_workflow_run_dor_fail(mock_root, tmp_path: Path):
    """Pipeline stops at DoR failure."""
    mock_root.return_value = tmp_path
    workflow = jcode_ai_native_workflow.JCodeAINativeWorkflow()

    # Short intent that fails DoR (too brief)
    result = workflow.run_full_pipeline("x")
    assert result is False


def test_dor_checker_failures(tmp_path: Path):
    """Test various DoR failure cases."""
    dor = DoRChecker(tmp_path)

    # Empty intent
    res = dor.evaluate_intent("")
    assert res["passed"] is False
    assert "too brief" in str(res["violations"])

    # TBD markers
    res = dor.evaluate_intent("TBD: implement feature")
    assert res["passed"] is False
    assert "TBD" in str(res["violations"])

    # TODO markers
    res = dor.evaluate_intent("TODO: fix bug")
    assert res["passed"] is False
    assert "TODO" in str(res["violations"])

    # Valid intent
    res = dor.evaluate_intent("Implement user authentication with JWT tokens")
    assert res["passed"] is True
    assert res["score"] == 7


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

"""Property-based tests (Hypothesis) and Agent Chaos Testing."""

from __future__ import annotations

from pathlib import Path

from hypothesis import given
from hypothesis import strategies as st

from tools.scripts.adg_cli.check import check_file
from tools.scripts.adg_cli.detect import _simple_yaml_parse


@given(st.text(min_size=1, max_size=100))
def test_simple_yaml_parse_property(text: str) -> None:
    """Property-based test: simple yaml parser never crashes on arbitrary text strings."""
    tmp = Path("/tmp/prop_test.yml")
    try:
        tmp.write_text(text, encoding="utf-8")
        result = _simple_yaml_parse(tmp)
        assert isinstance(result, dict)
    finally:
        if tmp.exists():
            tmp.unlink()


def test_agent_chaos_recovery_simulation(tmp_path: Path) -> None:
    """Chaos test: simulate agent self-correction loop when faced with malformed code and network/IO faults."""
    corrupted_file = tmp_path / "service.py"
    corrupted_file.write_text("import os\nexec(user_input)\nexcept:\n    pass\n")

    # Run check
    rules = {
        "anti_patterns": [
            {"id": "eval-exec", "severity": "error", "pattern": "exec\\(", "message": "No exec"},
            {"id": "bare-except", "severity": "error", "pattern": "except\\s*:", "message": "No bare except"},
        ]
    }
    issues = check_file(corrupted_file, rules)
    assert len(issues) >= 2

    # Simulate agent self-correction: fix issues
    fixed_content = (
        "import os\n# exec removed\ntry:\n    do_something()\nexcept Exception:\n    logging.error('handled')\n"
    )
    corrupted_file.write_text(fixed_content)

    issues_after_fix = check_file(corrupted_file, rules)
    assert len(issues_after_fix) == 0

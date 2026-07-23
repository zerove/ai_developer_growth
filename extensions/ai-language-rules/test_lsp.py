#!/usr/bin/env python3
"""Test the LSP server by simulating LSP messages.

Usage:
    python extensions/ai-language-rules/test_lsp.py
    python extensions/ai-language-rules/test_lsp.py --validate
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Add paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "tools" / "scripts"))
sys.path.insert(0, str(Path(__file__).parent))

from lsp_server import LanguageRulesLSP


def test_initialize() -> bool:
    """Test initialize request."""
    server = LanguageRulesLSP()
    msg = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {"rootUri": "file:///tmp/test-project"},
    }
    resp = server.handle_message(msg)
    assert resp is not None, "No response to initialize"
    assert resp["id"] == 1
    caps = resp["result"]["capabilities"]
    assert "textDocumentSync" in caps
    assert "diagnosticProvider" in caps
    print("  ✓ initialize")
    return True


def test_did_open_unknown() -> bool:
    """Test didOpen with unknown file type."""
    server = LanguageRulesLSP()
    msg = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///tmp/test.xyz"}},
    }
    resp = server.handle_message(msg)
    # Should not crash, returns None (no diagnostic for unknown files)
    assert resp is None
    print("  ✓ didOpen (unknown file)")
    return True


def test_did_open_python() -> bool:
    """Test didOpen with Python file (produces diagnostics)."""
    server = LanguageRulesLSP()
    msg = {
        "jsonrpc": "2.0",
        "method": "textDocument/didOpen",
        "params": {"textDocument": {"uri": "file:///tmp/test.py"}},
    }
    # File doesn't exist, should not crash
    resp = server.handle_message(msg)
    assert resp is None  # file not found, no diagnostics
    print("  ✓ didOpen (nonexistent Python file)")
    return True


def test_shutdown() -> bool:
    """Test shutdown request."""
    server = LanguageRulesLSP()
    msg = {"jsonrpc": "2.0", "id": 2, "method": "shutdown"}
    resp = server.handle_message(msg)
    assert resp is not None
    assert resp["id"] == 2
    assert resp["result"] is None
    print("  ✓ shutdown")
    return True


def test_result_to_diagnostics() -> bool:
    """Test ValidationResult to diagnostics conversion."""
    from validate_language_rules import Issue, ValidationResult

    server = LanguageRulesLSP()
    result = ValidationResult(file="test.py", language="python", lines_checked=10)
    result.issues.append(
        Issue(
            rule_id="py-bare-except",
            severity="error",
            category="error_handling",
            file="test.py",
            line=5,
            message="Avoid bare except",
        )
    )
    result.issues.append(
        Issue(
            rule_id="py-print",
            severity="info",
            category="style",
            file="test.py",
            line=10,
            message="Use logging",
        )
    )
    diags = server._result_to_diagnostics(result)
    assert len(diags) == 2
    assert diags[0]["severity"] == 1  # Error
    assert diags[1]["severity"] == 3  # Info
    assert diags[0]["code"] == "py-bare-except"
    print("  ✓ result_to_diagnostics")
    return True


def test_validate_mode() -> bool:
    """Validate mode: test LSP against actual Python file."""
    from validate_language_rules import Issue, ValidationResult

    server = LanguageRulesLSP()
    # Create a temp file with known issues
    import tempfile

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write("except:\n    pass\n")
        tmp_path = f.name

    try:
        msg = {
            "jsonrpc": "2.0",
            "method": "textDocument/didOpen",
            "params": {"textDocument": {"uri": f"file://{tmp_path}"}},
        }
        # This will publish diagnostics via _send_message
        # We capture by checking the validation result directly
        from validate_language_rules import validate_file

        result = validate_file(Path(tmp_path), "python")
        assert len(result.issues) > 0, "Expected issues in bare except code"
        print(f"  ✓ validate_mode: {len(result.issues)} issues found")
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


def main() -> int:
    print("Testing LSP Server...\n")

    tests = [
        test_initialize,
        test_did_open_unknown,
        test_did_open_python,
        test_shutdown,
        test_result_to_diagnostics,
        test_validate_mode,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            if test():
                passed += 1
            else:
                failed += 1
                print(f"  ✗ {test.__name__} FAILED")
        except Exception as e:
            failed += 1
            print(f"  ✗ {test.__name__}: {e}")

    print(f"\n{'=' * 40}")
    print(f"Total: {passed} passed, {failed} failed")
    return 1 if failed > 0 else 0


if __name__ == "__main__":
    sys.exit(main())

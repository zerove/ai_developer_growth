#!/usr/bin/env python3
"""
Language Server Protocol (LSP) implementation for AI Language Rules.

Provides real-time diagnostics in Zed editor by reading YAML rules
and checking code against anti-patterns, naming conventions, and thresholds.

Usage:
    python lsp_server.py --stdio
    python lsp_server.py --port 8080
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import threading
from pathlib import Path
from typing import Any

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "tools" / "scripts"))

from validate_language_rules import (
    EXTENSION_MAP,
    ValidationResult,
    load_custom_rules,
    load_rules,
    validate_file,
)


class LanguageRulesLSP:
    """Minimal LSP server for language rules diagnostics."""

    def __init__(self) -> None:
        self.project_dir: Path | None = None
        self.custom_rules: dict[str, Any] | None = None
        self._request_id = 0

    def handle_message(self, message: dict[str, Any]) -> dict[str, Any] | None:
        """Handle an LSP message and return response if needed."""
        method = message.get("method", "")
        msg_id = message.get("id")

        if method == "initialize":
            return self._handle_initialize(msg_id, message)
        elif method == "initialized":
            return None  # No response needed
        elif method == "textDocument/didOpen":
            self._handle_did_open(message)
            return None
        elif method == "textDocument/didSave":
            self._handle_did_save(message)
            return None
        elif method == "textDocument/didChange":
            self._handle_did_change(message)
            return None
        elif method == "shutdown":
            return {"jsonrpc": "2.0", "id": msg_id, "result": None}
        elif method == "exit":
            sys.exit(0)

        return None

    def _handle_initialize(self, msg_id: int | None, message: dict[str, Any]) -> dict[str, Any]:
        """Handle initialize request."""
        params = message.get("params", {})
        root_uri = params.get("rootUri", "")
        if root_uri and root_uri.startswith("file://"):
            self.project_dir = Path(root_uri[7:])
            self.custom_rules = load_custom_rules(self.project_dir)

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "capabilities": {
                    "textDocumentSync": 1,  # Full sync
                    "diagnosticProvider": {
                        "interFileDependencies": False,
                        "workspaceDiagnostics": False,
                    },
                }
            },
        }

    def _handle_did_open(self, message: dict[str, Any]) -> None:
        """Handle textDocument/didOpen - publish diagnostics."""
        params = message.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        self._publish_diagnostics_for_uri(uri)

    def _handle_did_save(self, message: dict[str, Any]) -> None:
        """Handle textDocument/didSave - re-check diagnostics."""
        params = message.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        self._publish_diagnostics_for_uri(uri)

    def _handle_did_change(self, message: dict[str, Any]) -> None:
        """Handle textDocument/didChange - debounced re-check."""
        params = message.get("params", {})
        uri = params.get("textDocument", {}).get("uri", "")
        # For now, check immediately (debounce can be added later)
        self._publish_diagnostics_for_uri(uri)

    def _publish_diagnostics_for_uri(self, uri: str) -> None:
        """Validate file and publish diagnostics."""
        if not uri.startswith("file://"):
            return

        filepath = Path(uri[7:])
        if not filepath.exists():
            return

        language = EXTENSION_MAP.get(filepath.suffix.lower())
        if language is None:
            return

        result = validate_file(filepath, language, custom_rules=self.custom_rules)
        diagnostics = self._result_to_diagnostics(result)

        notification = {
            "jsonrpc": "2.0",
            "method": "textDocument/publishDiagnostics",
            "params": {
                "uri": uri,
                "diagnostics": diagnostics,
            },
        }
        self._send_message(notification)

    def _result_to_diagnostics(self, result: ValidationResult) -> list[dict[str, Any]]:
        """Convert ValidationResult to LSP diagnostics."""
        diagnostics = []
        for issue in result.issues:
            severity = {
                "error": 1,  # DiagnosticSeverity.Error
                "warning": 2,  # DiagnosticSeverity.Warning
                "info": 3,  # DiagnosticSeverity.Information
            }.get(issue.severity, 3)

            diag: dict[str, Any] = {
                "range": {
                    "start": {"line": max(0, issue.line - 1), "character": issue.column},
                    "end": {"line": max(0, issue.line - 1), "character": issue.column + 10},
                },
                "severity": severity,
                "source": "ai-language-rules",
                "message": issue.message,
                "code": issue.rule_id,
                "codeDescription": {
                    "href": f"https://github.com/1jehuang/jcode/rules/{issue.rule_id}"
                },
            }

            # Add related information for fixable issues
            if issue.fix_hint:
                diag["data"] = {
                    "fixHint": issue.fix_hint,
                    "category": issue.category,
                }

            diagnostics.append(diag)

        return diagnostics

    def _send_message(self, message: dict[str, Any]) -> None:
        """Send an LSP message to stdout."""
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        sys.stdout.write(header + content)
        sys.stdout.flush()

    def read_message(self) -> dict[str, Any] | None:
        """Read an LSP message from stdin."""
        # Read headers
        content_length = 0
        while True:
            line = sys.stdin.readline()
            if not line:
                return None
            line = line.strip()
            if line == "":
                break
            if line.startswith("Content-Length:"):
                content_length = int(line.split(":")[1].strip())

        if content_length == 0:
            return None

        # Read body
        body = sys.stdin.read(content_length)
        return json.loads(body)

    def run(self) -> None:
        """Main LSP loop."""
        while True:
            message = self.read_message()
            if message is None:
                break

            response = self.handle_message(message)
            if response is not None:
                self._send_message(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Language Rules LSP Server")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    parser.add_argument("--port", type=int, help="Use TCP transport on specified port")
    args = parser.parse_args()

    server = LanguageRulesLSP()

    if args.port:
        import socketserver

        class LSPHandler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                server._send_message = lambda msg: self.wfile.write(
                    (f"Content-Length: {len(json.dumps(msg))}\r\n\r\n" + json.dumps(msg)).encode()
                )
                server.read_message = lambda: json.loads(
                    self.rfile.readline().decode().strip()
                )
                server.run()

        with socketserver.TCPServer(("localhost", args.port), LSPHandler) as httpd:
            print(f"LSP server listening on port {args.port}", file=sys.stderr)
            httpd.serve_forever()
    else:
        server.run()


if __name__ == "__main__":
    main()

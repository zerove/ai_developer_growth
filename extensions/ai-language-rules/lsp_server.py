#!/usr/bin/env python3
"""
Language Server Protocol (LSP) implementation for AI Language Rules.

Provides real-time diagnostics in Zed/Sublime editors by running `adg check --json`
against the current ADG rules engine (699+ rules across 26 languages + 9 frameworks).

Usage:
    python lsp_server.py --stdio
    python lsp_server.py --port 8080
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


class LanguageRulesLSP:
    """Minimal LSP server using ADG CLI for diagnostics."""

    def __init__(self) -> None:
        self.project_dir: Path | None = None

    def handle_message(self, message: dict) -> dict | None:
        """Handle an LSP message and return response if needed."""
        method = message.get("method", "")
        msg_id = message.get("id")

        if method == "initialize":
            return self._handle_initialize(msg_id, message)
        elif method == "initialized":
            return None
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

    def _handle_initialize(self, msg_id: int | None, message: dict) -> dict:
        params = message.get("params", {})
        root_uri = params.get("rootUri", "")
        if root_uri and root_uri.startswith("file://"):
            self.project_dir = Path(root_uri[7:])

        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "capabilities": {
                    "textDocumentSync": 1,
                    "diagnosticProvider": {
                        "interFileDependencies": False,
                        "workspaceDiagnostics": False,
                    },
                }
            },
        }

    def _handle_did_open(self, message: dict) -> None:
        uri = message.get("params", {}).get("textDocument", {}).get("uri", "")
        self._publish_diagnostics_for_uri(uri)

    def _handle_did_save(self, message: dict) -> None:
        uri = message.get("params", {}).get("textDocument", {}).get("uri", "")
        self._publish_diagnostics_for_uri(uri)

    def _handle_did_change(self, message: dict) -> None:
        uri = message.get("params", {}).get("textDocument", {}).get("uri", "")
        self._publish_diagnostics_for_uri(uri)

    def _run_adg_check(self, filepath: Path) -> dict:
        """Run `adg check --json` on the given file."""
        try:
            result = subprocess.run(
                ["adg", "check", str(filepath), "--severity", "warning", "--json"],
                capture_output=True,
                text=True,
                timeout=15,
            )
            if result.returncode in (0, 1) and result.stdout:
                return json.loads(result.stdout)
            return {"issues": [], "summary": {"error": 0, "warning": 0, "info": 0}}
        except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
            print(f"ADG check failed: {e}", file=sys.stderr)
            return {"issues": [], "summary": {"error": 0, "warning": 0, "info": 0}}

    def _publish_diagnostics_for_uri(self, uri: str) -> None:
        if not uri.startswith("file://"):
            return

        filepath = Path(uri[7:])
        if not filepath.exists():
            return

        result = self._run_adg_check(filepath)
        diagnostics = self._result_to_diagnostics(result.get("issues", []))

        self._send_message(
            {
                "jsonrpc": "2.0",
                "method": "textDocument/publishDiagnostics",
                "params": {"uri": uri, "diagnostics": diagnostics},
            }
        )

    def _result_to_diagnostics(self, issues: list[dict]) -> list[dict]:
        diagnostics = []
        for issue in issues:
            severity = {"error": 1, "warning": 2}.get(issue.get("severity", "info"), 3)

            diag = {
                "range": {
                    "start": {"line": max(0, issue.get("line", 1) - 1), "character": issue.get("column", 0)},
                    "end": {"line": max(0, issue.get("line", 1) - 1), "character": issue.get("column", 0) + 10},
                },
                "severity": severity,
                "source": "ai-language-rules",
                "message": f"[{issue.get('rule_id', '?')}] {issue.get('message', '')}",
                "code": issue.get("rule_id", ""),
            }

            if issue.get("fix_hint"):
                diag["data"] = {
                    "fixHint": issue["fix_hint"],
                    "category": issue.get("category", ""),
                }

            diagnostics.append(diag)

        return diagnostics

    def _send_message(self, message: dict) -> None:
        content = json.dumps(message)
        header = f"Content-Length: {len(content)}\r\n\r\n"
        sys.stdout.write(header + content)
        sys.stdout.flush()

    def read_message(self) -> dict | None:
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

        body = sys.stdin.read(content_length)
        return json.loads(body)

    def run(self) -> None:
        while True:
            message = self.read_message()
            if message is None:
                break
            response = self.handle_message(message)
            if response is not None:
                self._send_message(response)


def main() -> None:
    parser = argparse.ArgumentParser(description="AI Language Rules LSP Server (ADG backend)")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    parser.add_argument("--port", type=int, help="Use TCP transport on specified port")
    args = parser.parse_args()

    server = LanguageRulesLSP()

    if args.port:
        import socketserver

        class LSPHandler(socketserver.StreamRequestHandler):
            def handle(self) -> None:
                server._send_message = lambda msg: self.wfile.write(
                    (f"Content-Length: {len(json.dumps(msg))}\r\n\r\n{json.dumps(msg)}").encode()
                )
                server.read_message = lambda: json.loads(self.rfile.readline().decode().strip())
                server.run()

        with socketserver.TCPServer(("localhost", args.port), LSPHandler) as httpd:
            print(f"LSP server listening on port {args.port}", file=sys.stderr)
            httpd.serve_forever()
    else:
        server.run()


if __name__ == "__main__":
    main()

"""
ADG LSP Server - Language Server Protocol implementation for ADG Governance.

Provides IDE integration via the Language Server Protocol standard.
Any editor supporting LSP (Zed, VSCode, Neovim, Sublime, etc.) can use this.

Usage:
    python -m tools.lsp.server --stdio
    python -m tools.lsp.server --port 8080

Features:
    - Real-time diagnostics on file open/save/change
    - Quick fixes (code actions)
    - Code lenses showing issue summaries
    - Hover information for governance rules
    - SARIF import support
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

# Try importing lsprotocol; fall back to basic implementation
try:
    from lsprotocol import types
    from pygls.server import LanguageServer

    HAS_PYGLS = True
except ImportError:
    HAS_PYGLS = False

# Import ADG core
from tools.scripts.adg_cli import (
    check_file,
    load_project_config,
    load_rules_for_language,
)

logger = logging.getLogger("adg-lsp")

# Supported file extensions
SUPPORTED_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "typescript",
    ".jsx": "javascript",
    ".go": "go",
    ".rs": "rust",
    ".java": "java",
    ".kt": "kotlin",
    ".rb": "ruby",
    ".php": "php",
    ".swift": "swift",
    ".c": "c",
    ".cpp": "cpp",
    ".cs": "csharp",
    ".h": "c",
    ".hh": "cpp",
    ".hpp": "cpp",
    ".dart": "dart",
    ".scala": "scala",
}


# ─────────────────────────────────────────────────────────────
# Standalone LSP Server (without pygls)
# ─────────────────────────────────────────────────────────────


class AdgLanguageServer:
    """Lightweight LSP server that speaks JSON-RPC over stdio."""

    def __init__(self):
        self.workspace_root: str = "."
        self.documents: dict[str, str] = {}
        self.rules_cache: dict[str, dict] = {}
        self.config: dict[str, Any] = {
            "severity_filter": "warning",
            "enable_on_save": True,
            "enable_code_lens": True,
            "enable_quick_fix": True,
            "trend_enabled": False,
            "exclude_patterns": ["node_modules", ".git", "target", "__pycache__"],
        }
        self._request_id = 0

    def handle_request(self, method: str, params: dict) -> Any:
        """Route incoming LSP requests."""
        handlers = {
            "initialize": self._handle_initialize,
            "initialized": lambda p: {},
            "textDocument/didOpen": self._handle_did_open,
            "textDocument/didChange": self._handle_did_change,
            "textDocument/didSave": self._handle_did_save,
            "textDocument/didClose": self._handle_did_close,
            "textDocument/diagnostic": self._handle_diagnostic,
            "textDocument/codeAction": self._handle_code_action,
            "textDocument/codeLens": self._handle_code_lens,
            "textDocument/hover": self._handle_hover,
            "workspace/didChangeConfiguration": self._handle_config_change,
            "workspace/symbol": self._handle_workspace_symbol,
        }

        handler = handlers.get(method)
        if handler:
            return handler(params)
        return None

    def _handle_initialize(self, params: dict) -> dict:
        """Handle initialize request."""
        if "rootUri" in params:
            self.workspace_root = params["rootUri"] or "."
        elif "rootPath" in params:
            self.workspace_root = params["rootPath"] or "."

        # Load project config
        root_path = Path(self.workspace_root.replace("file://", ""))
        if root_path.exists():
            project_config = load_project_config(root_path)
            if project_config:
                self.config.update(project_config)

        return {
            "capabilities": {
                "textDocumentSync": {
                    "openClose": True,
                    "change": 2,  # Incremental
                    "save": {"includeText": True},
                },
                "codeActionProvider": {
                    "codeActionKinds": ["quickfix"],
                },
                "codeLensProvider": {"resolveProvider": False},
                "hoverProvider": True,
                "diagnosticProvider": {
                    "interFileDependencies": False,
                    "workspaceDiagnostics": False,
                },
            }
        }

    def _handle_did_open(self, params: dict) -> None:
        """Handle textDocument/didOpen."""
        text_doc = params.get("textDocument", {})
        uri = text_doc.get("uri", "")
        self.documents[uri] = text_doc.get("text", "")

    def _handle_did_change(self, params: dict) -> None:
        """Handle textDocument/didChange."""
        uri = params.get("textDocument", {}).get("uri", "")
        content_changes = params.get("contentChanges", [])
        if content_changes:
            self.documents[uri] = content_changes[-1].get("text", "")

    def _handle_did_save(self, params: dict) -> None:
        """Handle textDocument/didSave."""
        pass  # Diagnostics are requested by client

    def _handle_did_close(self, params: dict) -> None:
        """Handle textDocument/didClose."""
        uri = params.get("textDocument", {}).get("uri", "")
        self.documents.pop(uri, None)

    def _handle_diagnostic(self, params: dict) -> list[dict]:
        """Handle textDocument/diagnostic - return diagnostics for a document."""
        uri = params.get("textDocument", {}).get("uri", "")
        file_path = Path(uri.replace("file://", ""))

        if not file_path.exists():
            return []

        ext = file_path.suffix.lower()
        language = SUPPORTED_EXTENSIONS.get(ext)
        if not language:
            return []

        # Check exclusions
        file_str = str(file_path)
        if any(pat in file_str for pat in self.config.get("exclude_patterns", [])):
            return []

        # Get rules
        rules = self._get_rules(language)

        # Check file
        severity_filter = self.config.get("severity_filter", "warning")
        issues = check_file(file_path, rules, severity_filter)

        # Convert to LSP diagnostics
        diagnostics = []
        for issue in issues:
            severity_map = {
                "error": 1,  # Error
                "warning": 2,  # Warning
                "info": 3,  # Information
            }
            diagnostics.append(
                {
                    "range": {
                        "start": {"line": max(0, issue.line - 1), "character": max(0, issue.column - 1)},
                        "end": {"line": max(0, issue.line - 1), "character": issue.column + 80},
                    },
                    "severity": severity_map.get(issue.severity, 2),
                    "code": issue.rule_id,
                    "source": "adg",
                    "message": f"[{issue.rule_id}] {issue.message}\nFix: {issue.fix_hint}",
                    "data": {
                        "category": issue.category,
                        "fix_hint": issue.fix_hint,
                    },
                }
            )

        return diagnostics

    def _handle_code_action(self, params: dict) -> list[dict]:
        """Handle textDocument/codeAction - return quick fixes."""
        if not self.config.get("enable_quick_fix", True):
            return []

        diagnostics = params.get("context", {}).get("diagnostics", [])
        actions = []

        for diag in diagnostics:
            if diag.get("source") != "adg":
                continue

            rule_id = diag.get("code", "")
            data = diag.get("data", {})

            # Fix action
            actions.append(
                {
                    "title": f'ADG: Auto-fix "{rule_id}"',
                    "kind": "quickfix",
                    "diagnostics": [diag],
                    "command": {
                        "command": "adg.fix",
                        "title": "Apply Fix",
                        "arguments": [params.get("textDocument", {}).get("uri", ""), rule_id],
                    },
                }
            )

            # Suppress action
            actions.append(
                {
                    "title": f'ADG: Suppress "{rule_id}"',
                    "kind": "quickfix",
                    "diagnostics": [diag],
                    "command": {
                        "command": "adg.suppress",
                        "title": "Suppress Rule",
                        "arguments": [rule_id],
                    },
                }
            )

        return actions

    def _handle_code_lens(self, params: dict) -> list[dict]:
        """Handle textDocument/codeLens - show issue summary."""
        if not self.config.get("enable_code_lens", True):
            return []

        uri = params.get("textDocument", {}).get("uri", "")
        diagnostics = self._handle_diagnostic({"textDocument": {"uri": uri}})

        if not diagnostics:
            return []

        error_count = sum(1 for d in diagnostics if d.get("severity") == 1)
        warn_count = sum(1 for d in diagnostics if d.get("severity") == 2)
        info_count = sum(1 for d in diagnostics if d.get("severity") == 3)

        summary = f"ADG: {len(diagnostics)} issues"
        if error_count:
            summary += f" ({error_count} errors)"
        if warn_count:
            summary += f" ({warn_count} warnings)"

        return [
            {
                "range": {"start": {"line": 0, "character": 0}, "end": {"line": 0, "character": 0}},
                "command": {
                    "title": summary,
                    "command": "adg.showOutput",
                },
            }
        ]

    def _handle_hover(self, params: dict) -> dict | None:
        """Handle textDocument/hover - show rule info on hover."""
        uri = params.get("textDocument", {}).get("uri", "")
        position = params.get("position", {})
        line = position.get("line", 0)

        # Get diagnostics for this line
        diagnostics = self._handle_diagnostic({"textDocument": {"uri": uri}})
        line_issues = [d for d in diagnostics if d["range"]["start"]["line"] == line]

        if not line_issues:
            return None

        # Build hover content
        lines = ["**ADG Governance Issues**\n"]
        for issue in line_issues[:5]:
            rule_id = issue.get("code", "")
            message = issue.get("message", "").split("\n")[0]
            lines.append(f"- `{rule_id}`: {message}")

        return {
            "contents": {
                "kind": "markdown",
                "value": "\n".join(lines),
            }
        }

    def _handle_config_change(self, params: dict) -> None:
        """Handle workspace/didChangeConfiguration."""
        settings = params.get("settings", {})
        if "adg" in settings:
            self.config.update(settings["adg"])

    def _handle_workspace_symbol(self, params: dict) -> list[dict]:
        """Handle workspace/symbol - list all rules."""
        query = params.get("query", "")
        symbols = []

        for lang in ["python", "javascript", "typescript", "rust", "go", "java"]:
            rules = self._get_rules(lang)
            for pattern in rules.get("anti_patterns", []):
                rule_id = pattern.get("id", "")
                if query and query.lower() not in rule_id.lower():
                    continue
                symbols.append(
                    {
                        "name": rule_id,
                        "kind": 12,  # Event
                        "location": {
                            "uri": f"file://{self.workspace_root}/rules/{lang}",
                            "range": {
                                "start": {"line": 0, "character": 0},
                                "end": {"line": 0, "character": 0},
                            },
                        },
                    }
                )

        return symbols

    def _get_rules(self, language: str) -> dict:
        """Get rules for a language, with caching."""
        if language not in self.rules_cache:
            self.rules_cache[language] = load_rules_for_language(language)
        return self.rules_cache[language]


# ─────────────────────────────────────────────────────────────
# JSON-RPC Transport
# ─────────────────────────────────────────────────────────────


def read_message() -> tuple[str, Any]:
    """Read a JSON-RPC message from stdin."""
    # Read Content-Length header
    content_length = 0
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            raise EOFError
        line_str = line.decode("utf-8").strip()
        if line_str.startswith("Content-Length:"):
            content_length = int(line_str.split(":")[1].strip())
        elif line_str == "":
            break

    if content_length == 0:
        raise ValueError("No Content-Length found")

    # Read body
    body = sys.stdin.buffer.read(content_length)
    message = json.loads(body.decode("utf-8"))
    method = message.get("method", "")
    params = message.get("params", {})
    msg_id = message.get("id")

    return method, params, msg_id


def write_message(response: dict) -> None:
    """Write a JSON-RPC response to stdout."""
    body = json.dumps(response)
    content = f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"
    sys.stdout.buffer.write(content.encode("utf-8"))
    sys.stdout.buffer.flush()


def send_notification(method: str, params: dict) -> None:
    """Send a JSON-RPC notification."""
    write_message({"jsonrpc": "2.0", "method": method, "params": params})


# ─────────────────────────────────────────────────────────────
# Main Loop
# ─────────────────────────────────────────────────────────────


def run_stdio_server():
    """Run the LSP server over stdio."""
    server = AdgLanguageServer()

    logger.info("ADG LSP Server starting (stdio mode)")

    while True:
        try:
            method, params, msg_id = read_message()
            logger.debug(f"Request: {method}")

            result = server.handle_request(method, params)

            if msg_id is not None:
                response = {"jsonrpc": "2.0", "id": msg_id}
                if result is not None:
                    response["result"] = result
                write_message(response)

            # Send diagnostics after document changes
            if method in ("textDocument/didOpen", "textDocument/didChange", "textDocument/didSave"):
                uri = params.get("textDocument", {}).get("uri", "")
                if uri:
                    diagnostics = server._handle_diagnostic({"textDocument": {"uri": uri}})
                    send_notification(
                        "textDocument/publishDiagnostics",
                        {
                            "uri": uri,
                            "diagnostics": diagnostics,
                        },
                    )

        except EOFError:
            break
        except Exception as e:
            logger.error(f"Error handling {method}: {e}")
            if msg_id is not None:
                write_message(
                    {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32603, "message": str(e)},
                    }
                )


def run_tcp_server(port: int):
    """Run the LSP server over TCP."""
    import socket

    server = AdgLanguageServer()
    logger.info(f"ADG LSP Server starting (TCP mode on port {port})")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", port))
    sock.listen(1)
    logger.info(f"Listening on 127.0.0.1:{port}")

    conn, addr = sock.accept()
    logger.info(f"Client connected from {addr}")

    # Replace stdin/stdout with socket
    sys.stdin = conn.makefile("rb")
    sys.stdout = conn.makefile("wb")

    run_stdio_server()


# ─────────────────────────────────────────────────────────────
# Entry Point
# ─────────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(description="ADG LSP Server")
    parser.add_argument("--stdio", action="store_true", help="Use stdio transport")
    parser.add_argument("--port", type=int, default=8080, help="TCP port (default: 8080)")
    parser.add_argument("--log-level", default="INFO", help="Log level")
    args = parser.parse_args()

    logging.basicConfig(level=getattr(logging, args.log_level.upper()))

    if args.stdio or not args.port:
        run_stdio_server()
    else:
        run_tcp_server(args.port)


if __name__ == "__main__":
    main()

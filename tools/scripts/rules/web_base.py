"""Web server base class for rule tools.

Provides shared HTTP server functionality for rule_visualize.py and
rule_editor.py, eliminating code duplication.

Usage:
    from rules.web_base import RuleWebServer, HTML_PAGE

    class MyHandler(RuleWebServer):
        def handle_api(self, path, query):
            if path == "/api/data":
                return {"result": "ok"}
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any
from urllib.parse import parse_qs, urlparse


class RuleWebServer(BaseHTTPRequestHandler):
    """Base HTTP handler for rule-related web tools.

    Subclasses should override:
    - handle_api(path, query) -> dict for API endpoints
    - page_title: str for the page title
    - get_html_content() -> str for the main HTML page
    """

    page_title: str = "AI Language Rules"
    _html_content: str = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return

        if path.startswith("/api/"):
            self._handle_api_request(path, query)
            return

        # Serve HTML page
        html = self.get_html_content()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(html.encode())

    def do_POST(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path

        if path.startswith("/api/"):
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length) if content_length > 0 else b""
            try:
                data = json.loads(body) if body else {}
            except json.JSONDecodeError:
                data = {}

            query = parse_qs(parsed.query)
            self._handle_api_request(path, query, data)
            return

        self.send_response(404)
        self.end_headers()

    def _handle_api_request(self, path: str, query: dict[str, list[str]], data: dict[str, Any] | None = None) -> None:
        try:
            result = self.handle_api(path, query, data)
            self._send_json(result)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def handle_api(self, path: str, query: dict[str, list[str]], data: dict[str, Any] | None = None) -> Any:
        """Override this to handle API requests. Return a JSON-serializable object."""
        return {"error": "Not implemented"}

    def get_html_content(self) -> str:
        """Override this to return the full HTML page."""
        return f"<html><body><h1>{self.page_title}</h1></body></html>"

    def _send_json(
        self, data: dict[str, object] | list[object] | str | int | float | bool | None, status: int = 200
    ) -> None:
        body = json.dumps(data, ensure_ascii=False, default=str).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        """Suppress default logging for cleaner output."""
        pass


def run_server(
    handler_class: type[RuleWebServer],
    port: int = 8080,
    host: str = "127.0.0.1",
) -> None:
    """Start a rule web server on the given port."""
    server = HTTPServer((host, port), handler_class)
    title = getattr(handler_class, "page_title", "Rule Tool")
    print(f"  {title} running at http://{host}:{port}")
    print("  Press Ctrl+C to stop")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        server.server_close()

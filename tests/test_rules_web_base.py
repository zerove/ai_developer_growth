"""Tests for rules/web_base.py (24% → target 85%)."""

from __future__ import annotations

import json
from io import BytesIO
from typing import Any
from unittest.mock import MagicMock, patch

from tools.scripts.rules.web_base import RuleWebServer, run_server


def _make_handler(
    method: str,
    path: str,
    body: bytes = b"",
    headers: dict[str, str] | None = None,
) -> RuleWebServer:
    """Create a RuleWebServer instance with mocked internals."""
    handler = RuleWebServer.__new__(RuleWebServer)

    # Mock request properties
    handler.path = path
    handler.requestline = f"{method} {path} HTTP/1.1"
    handler.request_version = "HTTP/1.1"
    handler.client_address = ("127.0.0.1", 12345)

    # Mock headers
    hdrs = {"Content-Length": str(len(body))}
    if headers:
        hdrs.update(headers)
    handler.headers = hdrs

    # Mock rfile / wfile
    handler.rfile = BytesIO(body)
    handler.wfile = BytesIO()

    # Mock send_response / send_header / end_headers
    handler.send_response = MagicMock()
    handler.send_header = MagicMock()
    handler.end_headers = MagicMock()

    return handler


class TestDoGet:
    """Tests for do_GET()."""

    def test_html_page(self) -> None:
        h = _make_handler("GET", "/")
        h.do_GET()
        h.send_response.assert_called_with(200)
        h.wfile.seek(0)
        content = h.wfile.read().decode()
        assert "AI Language Rules" in content

    def test_favicon_returns_204(self) -> None:
        h = _make_handler("GET", "/favicon.ico")
        h.do_GET()
        h.send_response.assert_called_with(204)

    def test_api_endpoint(self) -> None:
        h = _make_handler("GET", "/api/rules")
        h.page_title = "Test"
        h.do_GET()
        h.send_response.assert_called_with(200)
        h.wfile.seek(0)
        data = json.loads(h.wfile.read())
        assert "error" in data  # default handle_api returns error

    def test_custom_page_title(self) -> None:
        h = _make_handler("GET", "/")
        h.page_title = "Custom Title"
        h.do_GET()
        h.wfile.seek(0)
        assert b"Custom Title" in h.wfile.read()


class TestDoPost:
    """Tests for do_POST()."""

    def test_post_to_api(self) -> None:
        body = json.dumps({"key": "value"}).encode()
        h = _make_handler("POST", "/api/save", body=body)
        h.do_POST()
        h.send_response.assert_called_with(200)

    def test_post_no_api_returns_404(self) -> None:
        h = _make_handler("POST", "/not-api")
        h.do_POST()
        h.send_response.assert_called_with(404)

    def test_post_invalid_json(self) -> None:
        h = _make_handler("POST", "/api/save", body=b"not-json")
        h.do_POST()
        h.send_response.assert_called_with(200)

    def test_post_empty_body(self) -> None:
        h = _make_handler("POST", "/api/save")
        h.do_POST()
        h.send_response.assert_called_with(200)


class TestHandleApiRequest:
    """Tests for _handle_api_request()."""

    def test_exception_returns_500(self) -> None:
        h = _make_handler("GET", "/api/error")
        h.handle_api = MagicMock(side_effect=ValueError("boom"))
        h._handle_api_request("/api/error", {})
        h.send_response.assert_called_with(500)
        h.wfile.seek(0)
        data = json.loads(h.wfile.read())
        assert "error" in data


class TestHandleApi:
    """Tests for default handle_api()."""

    def test_default_returns_not_implemented(self) -> None:
        h = _make_handler("GET", "/api/test")
        result = h.handle_api("/api/test", {})
        assert result == {"error": "Not implemented"}


class TestGetHtmlContent:
    """Tests for default get_html_content()."""

    def test_default_html(self) -> None:
        h = _make_handler("GET", "/")
        h.page_title = "My Title"
        html = h.get_html_content()
        assert "My Title" in html


class TestSendJson:
    """Tests for _send_json()."""

    def test_send_dict(self) -> None:
        h = _make_handler("GET", "/")
        h._send_json({"ok": True})
        h.send_response.assert_called_with(200)
        h.wfile.seek(0)
        data = json.loads(h.wfile.read())
        assert data["ok"] is True

    def test_send_with_custom_status(self) -> None:
        h = _make_handler("GET", "/")
        h._send_json({"err": True}, status=400)
        h.send_response.assert_called_with(400)

    def test_send_list(self) -> None:
        h = _make_handler("GET", "/")
        h._send_json([1, 2, 3])
        h.wfile.seek(0)
        assert json.loads(h.wfile.read()) == [1, 2, 3]

    def test_send_string(self) -> None:
        h = _make_handler("GET", "/")
        h._send_json("text")
        h.wfile.seek(0)
        assert json.loads(h.wfile.read()) == "text"

    def test_send_none(self) -> None:
        h = _make_handler("GET", "/")
        h._send_json(None)
        h.wfile.seek(0)
        assert json.loads(h.wfile.read()) is None


class TestLogMessage:
    """Tests for log_message() - should suppress output."""

    def test_no_output(self, capsys: Any) -> None:
        h = _make_handler("GET", "/")
        h.log_message("test %s", "arg")
        assert capsys.readouterr().out == ""


class TestRunServer:
    """Tests for run_server()."""

    @patch("tools.scripts.rules.web_base.HTTPServer")
    def test_starts_server(self, mock_server_cls: MagicMock) -> None:
        mock_server = MagicMock()
        mock_server_cls.return_value = mock_server
        run_server(RuleWebServer, port=9999, host="0.0.0.0")
        mock_server_cls.assert_called_once_with(("0.0.0.0", 9999), RuleWebServer)
        mock_server.serve_forever.assert_called_once()

    @patch("tools.scripts.rules.web_base.HTTPServer")
    def test_keyboard_interrupt_stops(self, mock_server_cls: MagicMock, capsys: Any) -> None:
        mock_server = MagicMock()
        mock_server.serve_forever.side_effect = KeyboardInterrupt
        mock_server_cls.return_value = mock_server
        run_server(RuleWebServer, port=8888)
        mock_server.server_close.assert_called_once()
        assert "stopped" in capsys.readouterr().out.lower()

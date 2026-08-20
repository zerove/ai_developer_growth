"""Tests for claude_provider.py - ClaudeProvider generate via HTTP."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.claude_provider import ClaudeProvider


class TestClaudeGenerate:
    """Tests for ClaudeProvider.generate."""

    def test_generate_success(self):
        """generate() returns the assistant message content on 200."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "Hello from Claude"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key="test-claude-key")
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            result = provider.generate(
                "What is AI?", "You are helpful.", "claude-sonnet-4-20250514"
            )
            assert result == "Hello from Claude"
            mock_post.assert_called_once()
            mock_response.raise_for_status.assert_called_once()

    def test_generate_correct_endpoint(self):
        """generate() hits the /messages endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key="key")
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "claude-sonnet-4-20250514")
            url = mock_post.call_args[0][0]
            assert url == f"{ClaudeProvider.DEFAULT_BASE_URL}/messages"

    def test_generate_custom_base_url(self):
        """generate() uses custom api_base when provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(
            api_key="key", api_base="https://proxy.example.com/v1"
        )
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "claude-sonnet-4-20250514")
            url = mock_post.call_args[0][0]
            assert url == "https://proxy.example.com/v1/messages"

    def test_generate_headers(self):
        """generate() sets x-api-key, anthropic-version, and Content-Type headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key="sk-ant-test")
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "claude-sonnet-4-20250514")
            _, kwargs = mock_post.call_args
            headers = kwargs["headers"]
            assert headers["x-api-key"] == "sk-ant-test"
            assert headers["anthropic-version"] == "2023-06-01"
            assert headers["Content-Type"] == "application/json"

    def test_generate_payload_structure(self):
        """generate() sends correct model, max_tokens, system, and messages."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key="key")
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("test prompt", "test system", "claude-sonnet-4-20250514")
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]

            assert payload["model"] == "claude-sonnet-4-20250514"
            assert payload["max_tokens"] == 4096
            assert payload["system"] == "test system"
            assert len(payload["messages"]) == 1
            assert payload["messages"][0]["role"] == "user"
            assert payload["messages"][0]["content"] == "test prompt"

    def test_generate_http_error_raises(self):
        """generate() propagates HTTPError on non-200 responses."""
        provider = ClaudeProvider(api_key="bad-key")
        with patch("src.providers.claude_provider.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "403 Forbidden"
            )
            mock_post.return_value = mock_response

            with pytest.raises(requests.HTTPError):
                provider.generate("prompt", "sys", "claude-sonnet-4-20250514")

    def test_generate_timeout_error_raises(self):
        """generate() propagates Timeout on network timeout."""
        provider = ClaudeProvider(api_key="key")
        with patch(
            "src.providers.claude_provider.requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(requests.Timeout):
                provider.generate("prompt", "sys", "claude-sonnet-4-20250514")

    def test_generate_connection_error_raises(self):
        """generate() propagates ConnectionError when server is unreachable."""
        provider = ClaudeProvider(api_key="key")
        with patch(
            "src.providers.claude_provider.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            with pytest.raises(requests.ConnectionError):
                provider.generate("prompt", "sys", "claude-sonnet-4-20250514")

    def test_generate_passes_timeout(self):
        """generate() passes timeout=60 to requests.post."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key="key")
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "claude-sonnet-4-20250514")
            _, kwargs = mock_post.call_args
            assert kwargs["timeout"] == 60

    def test_generate_empty_key_sends_empty_header(self):
        """generate() sends empty x-api-key when api_key is None."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "ok"}]}
        mock_response.raise_for_status = MagicMock()

        provider = ClaudeProvider(api_key=None)
        with patch(
            "src.providers.claude_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "claude-sonnet-4-20250514")
            _, kwargs = mock_post.call_args
            assert kwargs["headers"]["x-api-key"] == ""

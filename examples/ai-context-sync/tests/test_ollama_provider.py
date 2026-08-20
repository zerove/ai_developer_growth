"""Tests for ollama_provider.py - OllamaProvider generate via HTTP."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.ollama_provider import OllamaProvider


class TestOllamaGenerate:
    """Tests for OllamaProvider.generate."""

    def test_generate_success(self):
        """generate() returns the assistant message content on 200."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Hello from Ollama"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            result = provider.generate("What is AI?", "You are helpful.", "llama3")
            assert result == "Hello from Ollama"
            mock_post.assert_called_once()
            mock_response.raise_for_status.assert_called_once()

    def test_generate_default_url(self):
        """generate() uses localhost:11434 when no api_base is set."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "llama3")
            url = mock_post.call_args[0][0]
            assert url == f"{OllamaProvider.DEFAULT_BASE_URL}/api/chat"

    def test_generate_custom_base_url(self):
        """generate() uses custom api_base when provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider(api_base="http://remote-host:11434")
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "llama3")
            url = mock_post.call_args[0][0]
            assert url == "http://remote-host:11434/api/chat"

    def test_generate_no_auth_headers(self):
        """generate() does not set any Authorization header (local server)."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "llama3")
            _, kwargs = mock_post.call_args
            # Ollama doesn't use auth headers
            assert "headers" not in kwargs

    def test_generate_payload_structure(self):
        """generate() sends correct model, messages, and stream=False."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("test prompt", "test system", "llama3")
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]

            assert payload["model"] == "llama3"
            assert payload["stream"] is False
            assert len(payload["messages"]) == 2
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "test system"
            assert payload["messages"][1]["role"] == "user"
            assert payload["messages"][1]["content"] == "test prompt"

    def test_generate_connection_error_raises(self):
        """generate() propagates ConnectionError when Ollama is not running."""
        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            with pytest.raises(requests.ConnectionError):
                provider.generate("prompt", "sys", "llama3")

    def test_generate_http_error_raises(self):
        """generate() propagates HTTPError on non-200 responses."""
        provider = OllamaProvider()
        with patch("src.providers.ollama_provider.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError(
                "500 Internal"
            )
            mock_post.return_value = mock_response

            with pytest.raises(requests.HTTPError):
                provider.generate("prompt", "sys", "llama3")

    def test_generate_timeout_error_raises(self):
        """generate() propagates Timeout on network timeout."""
        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(requests.Timeout):
                provider.generate("prompt", "sys", "llama3")

    def test_generate_passes_timeout(self):
        """generate() passes timeout=120 to requests.post."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "ok"}}
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "llama3")
            _, kwargs = mock_post.call_args
            assert kwargs["timeout"] == 120

    def test_generate_non_json_response_raises(self):
        """generate() raises when response body is not valid JSON."""
        mock_response = MagicMock()
        mock_response.json.side_effect = ValueError("No JSON object could be decoded")
        mock_response.raise_for_status = MagicMock()

        provider = OllamaProvider()
        with patch(
            "src.providers.ollama_provider.requests.post", return_value=mock_response
        ):
            with pytest.raises(ValueError):
                provider.generate("prompt", "sys", "llama3")

    def test_provider_needs_no_api_key(self):
        """OllamaProvider can be instantiated without an api_key."""
        provider = OllamaProvider()
        assert provider.api_key is None
        assert provider.api_base is None

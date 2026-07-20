"""Tests for openai_provider.py - OpenAIProvider generate via HTTP."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.openai_provider import OpenAIProvider


class TestOpenAIGenerate:
    """Tests for OpenAIProvider.generate."""

    def test_generate_success(self):
        """generate() returns the assistant message content on 200."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello from OpenAI"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="test-openai-key")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            result = provider.generate("What is AI?", "You are helpful.", "gpt-4o")
            assert result == "Hello from OpenAI"
            mock_post.assert_called_once()
            mock_response.raise_for_status.assert_called_once()

    def test_generate_correct_endpoint(self):
        """generate() hits the /chat/completions endpoint."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="key")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "gpt-4o")
            url = mock_post.call_args[0][0]
            assert url == f"{OpenAIProvider.DEFAULT_BASE_URL}/chat/completions"

    def test_generate_custom_base_url(self):
        """generate() uses custom api_base when provided."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="key", api_base="https://proxy.example.com/v1")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "gpt-4o")
            url = mock_post.call_args[0][0]
            assert url == "https://proxy.example.com/v1/chat/completions"

    def test_generate_headers(self):
        """generate() sets Authorization and Content-Type headers."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="sk-test-123")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "gpt-4o")
            _, kwargs = mock_post.call_args
            headers = kwargs["headers"]
            assert headers["Authorization"] == "Bearer sk-test-123"
            assert headers["Content-Type"] == "application/json"

    def test_generate_payload_structure(self):
        """generate() sends correct model, messages, and temperature."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="key")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("test prompt", "test system", "gpt-4o")
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]

            assert payload["model"] == "gpt-4o"
            assert payload["temperature"] == 0.3
            assert payload["messages"][0]["role"] == "system"
            assert payload["messages"][0]["content"] == "test system"
            assert payload["messages"][1]["role"] == "user"
            assert payload["messages"][1]["content"] == "test prompt"

    def test_generate_http_error_raises(self):
        """generate() propagates HTTPError on non-200 responses."""
        provider = OpenAIProvider(api_key="bad-key")
        with patch("src.providers.openai_provider.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("401 Unauthorized")
            mock_post.return_value = mock_response

            with pytest.raises(requests.HTTPError):
                provider.generate("prompt", "sys", "gpt-4o")

    def test_generate_timeout_error_raises(self):
        """generate() propagates Timeout on network timeout."""
        provider = OpenAIProvider(api_key="key")
        with patch(
            "src.providers.openai_provider.requests.post",
            side_effect=requests.Timeout("timed out"),
        ):
            with pytest.raises(requests.Timeout):
                provider.generate("prompt", "sys", "gpt-4o")

    def test_generate_connection_error_raises(self):
        """generate() propagates ConnectionError when server is unreachable."""
        provider = OpenAIProvider(api_key="key")
        with patch(
            "src.providers.openai_provider.requests.post",
            side_effect=requests.ConnectionError("refused"),
        ):
            with pytest.raises(requests.ConnectionError):
                provider.generate("prompt", "sys", "gpt-4o")

    def test_generate_passes_timeout(self):
        """generate() passes timeout=30 to requests.post."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "ok"}}]
        }
        mock_response.raise_for_status = MagicMock()

        provider = OpenAIProvider(api_key="key")
        with patch(
            "src.providers.openai_provider.requests.post", return_value=mock_response
        ) as mock_post:
            provider.generate("prompt", "sys", "gpt-4o")
            _, kwargs = mock_post.call_args
            assert kwargs["timeout"] == 30

"""Tests for gemini_provider.py - GeminiProvider generate via HTTP."""

import os
import sys
from unittest.mock import MagicMock, patch

import pytest
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.gemini_provider import GeminiProvider


class TestGeminiGenerate:
    """Tests for GeminiProvider.generate."""

    def test_generate_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "Hello from Gemini"}]}}]}
        mock_response.raise_for_status = MagicMock()

        provider = GeminiProvider(api_key="test-gemini-key")
        with patch("src.providers.gemini_provider.requests.post", return_value=mock_response) as mock_post:
            result = provider.generate("What is AI?", "You are helpful.", "gemini-2.5-flash")
            assert result == "Hello from Gemini"
            mock_post.assert_called_once()
            mock_response.raise_for_status.assert_called_once()

    def test_generate_url_construction(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        mock_response.raise_for_status = MagicMock()

        provider = GeminiProvider(api_key="key", api_base="https://custom.api.com/v1")
        with patch("src.providers.gemini_provider.requests.post", return_value=mock_response) as mock_post:
            provider.generate("prompt", "sys", "my-model")
            call_args = mock_post.call_args
            url = call_args[0][0]
            assert url == "https://custom.api.com/v1/models/my-model:generateContent"

    def test_generate_default_url(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}
        mock_response.raise_for_status = MagicMock()

        provider = GeminiProvider(api_key="key")
        with patch("src.providers.gemini_provider.requests.post", return_value=mock_response) as mock_post:
            provider.generate("prompt", "sys", "gemini-2.5-flash")
            url = mock_post.call_args[0][0]
            assert url.startswith(GeminiProvider.DEFAULT_BASE_URL)
            assert "gemini-2.5-flash" in url

    def test_generate_payload_structure(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"candidates": [{"content": {"parts": [{"text": "response"}]}}]}
        mock_response.raise_for_status = MagicMock()

        provider = GeminiProvider(api_key="key")
        with patch("src.providers.gemini_provider.requests.post", return_value=mock_response) as mock_post:
            provider.generate("test prompt", "test system", "gemini-2.5-flash")
            _, kwargs = mock_post.call_args
            payload = kwargs["json"]
            headers = kwargs["headers"]

            # Check headers
            assert headers["x-goog-api-key"] == "key"
            assert headers["Content-Type"] == "application/json"

            # Check payload structure
            assert payload["contents"][0]["role"] == "user"
            assert payload["contents"][0]["parts"][0]["text"] == "test prompt"
            assert payload["systemInstruction"]["parts"][0]["text"] == "test system"
            assert payload["generationConfig"]["temperature"] == 0.3

    def test_generate_http_error_raises(self):
        provider = GeminiProvider(api_key="bad-key")
        with patch("src.providers.gemini_provider.requests.post") as mock_post:
            mock_response = MagicMock()
            mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")
            mock_post.return_value = mock_response

            with pytest.raises(requests.HTTPError):
                provider.generate("prompt", "sys", "gemini-2.5-flash")

    def test_generate_connection_error_raises(self):
        provider = GeminiProvider(api_key="key")
        with patch("src.providers.gemini_provider.requests.post", side_effect=requests.ConnectionError("refused")):
            with pytest.raises(requests.ConnectionError):
                provider.generate("prompt", "sys", "gemini-2.5-flash")

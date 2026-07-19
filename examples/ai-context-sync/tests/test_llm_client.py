"""Tests for llm_client.py - LLMClient and LLMCache."""

import os
import sys
import tempfile
import pytest
from unittest.mock import patch, MagicMock
import requests

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.llm_client import LLMClient, LLMCache
from src.exceptions import LLMError


class TestLLMCache:
    def test_cache_set_and_get(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LLMCache(cache_dir=tmpdir, ttl=3600)
            cache.set("openai", "gpt-4o", "prompt1", "sys1", "response1")
            result = cache.get("openai", "gpt-4o", "prompt1", "sys1")
            assert result == "response1"

    def test_cache_miss(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LLMCache(cache_dir=tmpdir, ttl=3600)
            result = cache.get("openai", "gpt-4o", "nonexistent", "sys")
            assert result is None

    def test_cache_expired(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LLMCache(cache_dir=tmpdir, ttl=0)
            cache.set("openai", "gpt-4o", "prompt1", "sys1", "response1")
            result = cache.get("openai", "gpt-4o", "prompt1", "sys1")
            assert result is None

    def test_cache_different_keys(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            cache = LLMCache(cache_dir=tmpdir, ttl=3600)
            cache.set("openai", "gpt-4o", "prompt1", "sys1", "resp1")
            cache.set("openai", "gpt-4o", "prompt2", "sys1", "resp2")
            assert cache.get("openai", "gpt-4o", "prompt1", "sys1") == "resp1"
            assert cache.get("openai", "gpt-4o", "prompt2", "sys1") == "resp2"


class TestLLMClientCache:
    def test_cache_hit_skips_api(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "cached"}}]}
        mock_response.raise_for_status = MagicMock()
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
                with patch("src.llm_client.LLMCache") as MockCache:
                    mock_cache = MagicMock()
                    mock_cache.get.return_value = "cached response"
                    MockCache.return_value = mock_cache
                    client = LLMClient(cache_enabled=True)
                    result = client.generate("Hello")
                    assert result == "cached response"
                    mock_cache.get.assert_called_once()

    def test_cache_disabled(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "fresh"}}]}
        mock_response.raise_for_status = MagicMock()
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response) as mock_post:
                client = LLMClient(cache_enabled=False)
                result = client.generate("Hello")
                assert result == "fresh"
                mock_post.assert_called_once()


class TestLLMClient:
    def test_init_with_env_key(self):
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            client = LLMClient(cache_enabled=False)
            assert client.api_key == "test-key"
            assert client.provider_name == "openai"
            assert client.model == "gpt-4o"

    def test_init_without_env_key(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient(cache_enabled=False)
            assert client.api_key is None

    def test_generate_mock_response(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient(cache_enabled=False)
            result = client.generate("Hello")
            assert "[Mock Response]" in result

    def test_generate_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"choices": [{"message": {"content": "Hi there"}}]}
        mock_response.raise_for_status = MagicMock()
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response) as mock_post:
                client = LLMClient(cache_enabled=False)
                result = client.generate("Hello")
                assert result == "Hi there"
                mock_post.assert_called_once()

    def test_generate_raises_on_failure(self):
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with patch("requests.post", side_effect=requests.ConnectionError("timeout")):
                client = LLMClient(cache_enabled=False)
                with pytest.raises(LLMError):
                    client.generate("Hello")

    def test_init_unsupported_provider(self):
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with pytest.raises(LLMError, match="Unsupported provider"):
                LLMClient(provider="unsupported", cache_enabled=False)


class TestClaudeProvider:
    def test_claude_generate_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"content": [{"text": "Claude response"}]}
        mock_response.raise_for_status = MagicMock()
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with patch("requests.post", return_value=mock_response) as mock_post:
                client = LLMClient(provider="claude", model="claude-3-5-sonnet-20241022", cache_enabled=False)
                result = client.generate("Hello")
                assert result == "Claude response"
                mock_post.assert_called_once()
                call_args = mock_post.call_args
                assert "anthropic-version" in call_args[1]["headers"]

    def test_claude_generate_raises_on_failure(self):
        with patch.dict(os.environ, {"AI_SYNC_KEY": "test-key"}):
            with patch("requests.post", side_effect=requests.ConnectionError("timeout")):
                client = LLMClient(provider="claude", cache_enabled=False)
                with pytest.raises(LLMError):
                    client.generate("Hello")


class TestOllamaProvider:
    def test_ollama_generate_success(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Ollama response"}}
        mock_response.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_response) as mock_post:
            client = LLMClient(provider="ollama", model="llama3", cache_enabled=False)
            result = client.generate("Hello")
            assert result == "Ollama response"
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            assert "localhost:11434" in call_args[0][0]

    def test_ollama_no_api_key_required(self):
        with patch.dict(os.environ, {}, clear=True):
            client = LLMClient(provider="ollama", model="llama3", cache_enabled=False)
            assert client.api_key is None
            mock_response = MagicMock()
            mock_response.json.return_value = {"message": {"content": "Real response"}}
            mock_response.raise_for_status = MagicMock()
            with patch("requests.post", return_value=mock_response):
                result = client.generate("Hello")
                assert "Mock Response" not in result

    def test_ollama_custom_base_url(self):
        mock_response = MagicMock()
        mock_response.json.return_value = {"message": {"content": "Custom URL response"}}
        mock_response.raise_for_status = MagicMock()
        with patch("requests.post", return_value=mock_response) as mock_post:
            client = LLMClient(provider="ollama", model="llama3", api_base="http://custom:8080", cache_enabled=False)
            client.generate("Hello")
            call_args = mock_post.call_args
            assert "custom:8080" in call_args[0][0]

"""Tests for base.py - LLMProvider base class."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.providers.base import LLMProvider


class TestLLMProviderInit:
    """Tests for LLMProvider.__init__."""

    def test_stores_api_key(self):
        """__init__ stores api_key when provided."""
        provider = LLMProvider(api_key="my-key")
        assert provider.api_key == "my-key"

    def test_stores_api_base(self):
        """__init__ stores api_base when provided."""
        provider = LLMProvider(api_base="https://custom.api.com/v1")
        assert provider.api_base == "https://custom.api.com/v1"

    def test_stores_both(self):
        """__init__ stores both api_key and api_base when provided."""
        provider = LLMProvider(api_key="key", api_base="https://example.com")
        assert provider.api_key == "key"
        assert provider.api_base == "https://example.com"

    def test_defaults_to_none(self):
        """__init__ defaults api_key and api_base to None."""
        provider = LLMProvider()
        assert provider.api_key is None
        assert provider.api_base is None

    def test_default_api_key_none(self):
        """__init__ accepts api_base without api_key."""
        provider = LLMProvider(api_base="https://example.com")
        assert provider.api_key is None
        assert provider.api_base == "https://example.com"

    def test_default_api_base_none(self):
        """__init__ accepts api_key without api_base."""
        provider = LLMProvider(api_key="key")
        assert provider.api_key == "key"
        assert provider.api_base is None


class TestLLMProviderGenerate:
    """Tests for LLMProvider.generate (abstract)."""

    def test_generate_raises_not_implemented(self):
        """generate() on base class raises NotImplementedError."""
        provider = LLMProvider()
        with pytest.raises(NotImplementedError):
            provider.generate("prompt", "system", "model")

    def test_subclass_must_implement_generate(self):
        """A subclass that doesn't override generate() still raises NotImplementedError."""

        class IncompleteProvider(LLMProvider):
            pass

        provider = IncompleteProvider(api_key="key")
        with pytest.raises(NotImplementedError):
            provider.generate("prompt", "system", "model")


class TestLLMProviderSubclassing:
    """Tests for proper subclassing of LLMProvider."""

    def test_subclass_can_override_generate(self):
        """A subclass can override generate() and return a value."""

        class FakeProvider(LLMProvider):
            def generate(self, prompt, system_prompt, model):
                return f"response to {prompt}"

        provider = FakeProvider(api_key="key", api_base="https://fake.com")
        result = provider.generate("hello", "sys", "model")
        assert result == "response to hello"

    def test_subclass_inherits_init(self):
        """A subclass inherits __init__ and stores attributes."""

        class FakeProvider(LLMProvider):
            def generate(self, prompt, system_prompt, model):
                return "ok"

        provider = FakeProvider(api_key="k", api_base="b")
        assert provider.api_key == "k"
        assert provider.api_base == "b"

    def test_subclass_isinstance(self):
        """Subclass instances are recognized as LLMProvider."""

        class FakeProvider(LLMProvider):
            def generate(self, prompt, system_prompt, model):
                return "ok"

        assert isinstance(FakeProvider(), LLMProvider)

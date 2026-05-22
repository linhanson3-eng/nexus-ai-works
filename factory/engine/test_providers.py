"""Tests for ProviderRegistry."""

from __future__ import annotations

import os
from copy import deepcopy

import pytest

from factory.engine.providers import Provider, ProviderRegistry


@pytest.fixture
def registry():
    r = ProviderRegistry(_providers={})
    r.register("anthropic", "https://api.anthropic.com/v1", api_key="sk-test", provider_type="anthropic")
    r.register("deepseek", "https://api.deepseek.com", api_key="sk-ds", provider_type="deepseek")
    return r


class TestProvider:
    def test_is_configured_true(self):
        p = Provider(name="test", base_url="https://example.com", api_key="sk")
        assert p.is_configured is True

    def test_is_configured_false(self):
        p = Provider(name="test", base_url="")
        assert p.is_configured is False


class TestProviderRegistry:
    def test_resolve_with_provider_prefix(self, registry):
        provider, model = registry.resolve("anthropic/claude-sonnet-4-6")
        assert provider is not None
        assert provider.name == "anthropic"
        assert provider.base_url == "https://api.anthropic.com/v1"
        assert provider.api_key == "sk-test"
        assert model == "claude-sonnet-4-6"

    def test_resolve_no_slash(self, registry):
        provider, model = registry.resolve("claude-sonnet-4-6")
        assert provider is None
        assert model == "claude-sonnet-4-6"

    def test_resolve_unknown_provider(self, registry):
        provider, model = registry.resolve("unknown/gpt-4")
        assert provider is None
        assert model == "gpt-4"

    def test_resolve_deepseek(self, registry):
        provider, model = registry.resolve("deepseek/deepseek-v4")
        assert provider is not None
        assert provider.name == "deepseek"
        assert model == "deepseek-v4"

    def test_get_existing(self, registry):
        p = registry.get("anthropic")
        assert p is not None
        assert p.base_url == "https://api.anthropic.com/v1"

    def test_get_missing(self, registry):
        assert registry.get("nonexistent") is None

    def test_register_new(self, registry):
        registry.register("openai", "https://api.openai.com/v1", api_key="sk-oai")
        p = registry.get("openai")
        assert p is not None
        assert p.api_key == "sk-oai"

    def test_register_overwrite(self, registry):
        registry.register("anthropic", "https://new-api.anthropic.com", api_key="sk-new")
        p = registry.get("anthropic")
        assert p.base_url == "https://new-api.anthropic.com"
        assert p.api_key == "sk-new"

    def test_len(self, registry):
        assert len(registry) == 2

    def test_contains(self, registry):
        assert "anthropic" in registry
        assert "nonexistent" not in registry

    def test_slash_in_model_name(self, registry):
        """Model names with slashes should handle the first slash only."""
        provider, model = registry.resolve("anthropic/us.anthropic.claude-sonnet-4-6-v1")
        assert provider is not None
        assert model == "us.anthropic.claude-sonnet-4-6-v1"


class TestLoadDefaults:
    def test_load_defaults_creates_registry(self):
        registry = ProviderRegistry.load_defaults()
        assert len(registry) > 0
        assert "anthropic" in registry

    def test_load_defaults_env_override(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-from-env")
        monkeypatch.setenv("OPENAI_API_KEY", "")
        registry = ProviderRegistry.load_defaults()
        p = registry.get("anthropic")
        assert p is not None
        assert p.api_key == "sk-from-env"

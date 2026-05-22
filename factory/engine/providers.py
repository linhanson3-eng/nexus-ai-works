"""Provider registry — pluggable model provider resolution.

Resolves ``"provider/model-name"`` strings to (base_url, api_key) pairs.
Providers are configured in ~/.factory/settings.json with environment
variable overrides for api_key.

Usage:
    registry = ProviderRegistry.load_defaults()
    provider, model = registry.resolve("anthropic/claude-sonnet-4-6")
    # provider.base_url → "https://api.anthropic.com/v1"
    # model → "claude-sonnet-4-6"
"""

from __future__ import annotations

import os
from copy import deepcopy
from dataclasses import dataclass


@dataclass(frozen=True)
class Provider:
    """A model provider with connection details."""

    name: str
    base_url: str
    api_key: str = ""
    provider_type: str = ""

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url)


@dataclass
class ProviderRegistry:
    """Pluggable provider registry.

    Provider configs are keyed by provider name (e.g. "anthropic", "deepseek").
    Model strings follow the ``"provider/model-name"`` convention.
    """

    _providers: dict[str, Provider]

    def register(
        self, name: str, base_url: str, *, api_key: str = "", provider_type: str = ""
    ) -> None:
        """Add or update a provider."""
        self._providers[name] = Provider(
            name=name,
            base_url=base_url,
            api_key=api_key,
            provider_type=provider_type or name,
        )

    def get(self, name: str) -> Provider | None:
        return self._providers.get(name)

    def resolve(self, model_str: str) -> tuple[Provider | None, str]:
        """Split ``"provider/model-name"`` into (Provider, actual_model).

        If the string has no ``/`` prefix, returns (None, model_str)
        so the caller can fall back to a default base_url.
        """
        if "/" not in model_str:
            return None, model_str
        provider_name, _, actual_model = model_str.partition("/")
        provider = self._providers.get(provider_name)
        return provider, actual_model

    @classmethod
    def load_defaults(cls) -> ProviderRegistry:
        """Load providers from SettingsStore with environment variable override.

        Priority: env var > settings.json > built-in defaults.
        """
        from factory.settings.store import SettingsStore

        store = SettingsStore()
        stored = store.list_providers()

        registry = cls(_providers={})
        _ENV_MAP: dict[str, str] = {
            "anthropic": "ANTHROPIC_API_KEY",
            "deepseek": "DEEPSEEK_API_KEY",
            "openai": "OPENAI_API_KEY",
            "moonshot": "MOONSHOT_API_KEY",
        }

        for name, cfg in stored.items():
            api_key = cfg.get("api_key", "")
            env_var = _ENV_MAP.get(name, "")
            if env_var:
                env_key = os.environ.get(env_var, "")
                if env_key:
                    api_key = env_key
            registry.register(
                name=name,
                base_url=cfg.get("base_url", ""),
                api_key=api_key,
                provider_type=cfg.get("provider_type", name),
            )

        return registry

    def __len__(self) -> int:
        return len(self._providers)

    def __contains__(self, name: str) -> bool:
        return name in self._providers

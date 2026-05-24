from __future__ import annotations

"""Settings persistence layer.

Providers, web search, tool profiles, and plugin registrations are stored
in a JSON file at ~/.factory/settings.json so they survive
project restarts without requiring a database migration.
"""


import json
import logging
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from factory.env import env_bool
from factory.security.crypto import encrypt as _encrypt, decrypt as _decrypt

logger = logging.getLogger(__name__)


SETTINGS_PATH = Path.home() / ".factory" / "settings.json"

_ENV_API_KEYS: dict[str, str] = {
    "anthropic": "ANTHROPIC_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "openai": "OPENAI_API_KEY",
    "moonshot": "MOONSHOT_API_KEY",
    "siliconflow": "SILICONFLOW_API_KEY",
}


def _apply_env_api_keys(providers: dict) -> None:
    """Fill api_key from environment variables when available."""
    for name, env_var in _ENV_API_KEYS.items():
        key = os.environ.get(env_var, "")
        if key and name in providers:
            providers[name]["api_key"] = key


DEFAULT_PROVIDERS = {
    "anthropic": {
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
        "models": ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
    },
    "deepseek": {
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
        "models": ["deepseek-chat", "deepseek-reasoner"],
    },
    "openai": {
        "provider_type": "openai",
        "base_url": "https://api.openai.com/v1",
        "api_key": "",
        "models": ["gpt-5.4", "gpt-5.4-mini", "gpt-5.3-codex", "o4-mini"],
    },
    "siliconflow": {
        "provider_type": "siliconflow",
        "base_url": "https://api.siliconflow.cn/v1",
        "api_key": "",
        "models": [
            "deepseek-ai/DeepSeek-V3",
            "deepseek-ai/DeepSeek-R1",
            "Qwen/Qwen3-235B-A22B",
            "Pro/zai-org/GLM-4.5",
        ],
    },
    "moonshot": {
        "provider_type": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "",
        "models": ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
    },
}

DEFAULT_SEARCH = {
    "tavily_api_key": "",
    "brave_api_key": "",
    "searxng_base_url": "",
    "active_provider": "tavily",
    "deep_search_enabled": False,
    "max_results": 5,
}


@dataclass
class SettingsStore:
    """Read-write store for persistent settings.

    Usage:
        store = SettingsStore()
        providers = store.list_providers()
        store.save_provider("deepseek", api_key="sk-xxx")
        store.save_search(tavily_api_key="tvly-xxx")
    """

    _data: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        self._load()

    # ── internal ──────────────────────────────────────────

    def _load(self) -> None:
        if SETTINGS_PATH.exists():
            try:
                self._data = json.loads(SETTINGS_PATH.read_text())
            except (json.JSONDecodeError, OSError):
                self._data = {}
        if not self._data:
            self._data = {
                "providers": deepcopy(DEFAULT_PROVIDERS),
                "plugins": {},
                "tools": {},
                "search": deepcopy(DEFAULT_SEARCH),
            }
        else:
            self._decrypt_provider_keys()
            self._decrypt_search_keys()
            # Merge in any new default providers not yet in saved data
            for name, cfg in DEFAULT_PROVIDERS.items():
                if name not in self._data.get("providers", {}):
                    self._data.setdefault("providers", {})[name] = deepcopy(cfg)
        # Always apply environment variable API keys (env takes priority over stored)
        _apply_env_api_keys(self._data.get("providers", {}))

    def _save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        # Encrypt keys before persisting, decrypt back after for runtime use
        self._encrypt_provider_keys()
        self._encrypt_search_keys()
        try:
            tmp = str(SETTINGS_PATH) + ".tmp"
            with open(tmp, "w") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, str(SETTINGS_PATH))
        finally:
            self._decrypt_provider_keys()
            self._decrypt_search_keys()

    def _encrypt_provider_keys(self) -> None:
        """Encrypt api_key fields before persisting to disk."""
        for provider in self._data.get("providers", {}).values():
            key = provider.get("api_key", "")
            if key and not key.startswith("$e$"):
                try:
                    provider["api_key"] = "$e$" + _encrypt(key)
                except Exception as exc:
                    logger.error("Failed to encrypt API key: %s", exc)

    def _decrypt_provider_keys(self) -> None:
        """Decrypt api_key fields after loading from disk."""
        for provider in self._data.get("providers", {}).values():
            key = provider.get("api_key", "")
            if key.startswith("$e$"):
                try:
                    provider["api_key"] = _decrypt(key[3:])
                except Exception as exc:
                    logger.error("Failed to decrypt API key: %s", exc)
                    provider["api_key"] = ""

    def _encrypt_search_keys(self) -> None:
        """Encrypt search API keys before persisting."""
        search = self._data.get("search", {})
        for field in ("tavily_api_key", "brave_api_key"):
            key = search.get(field, "")
            if key and not key.startswith("$e$"):
                try:
                    search[field] = "$e$" + _encrypt(key)
                except Exception as exc:
                    logger.error("Failed to encrypt search key %s: %s", field, exc)

    def _decrypt_search_keys(self) -> None:
        """Decrypt search API keys after loading."""
        search = self._data.get("search", {})
        for field in ("tavily_api_key", "brave_api_key"):
            key = search.get(field, "")
            if key and key.startswith("$e$"):
                try:
                    search[field] = _decrypt(key[3:])
                except Exception as exc:
                    logger.error("Failed to decrypt search key %s: %s", field, exc)
                    search[field] = key

    # ── providers ─────────────────────────────────────────

    def list_providers(self, *, mask_keys: bool = False) -> dict[str, dict]:
        result = deepcopy(self._data.get("providers", {}))
        if mask_keys:
            for p in result.values():
                k = p.get("api_key", "")
                if k and len(k) > 8:
                    p["api_key"] = k[:4] + "..." + k[-4:]
        return result

    def get_provider(self, name: str) -> dict | None:
        providers = self._data.get("providers", {})
        return deepcopy(providers.get(name))

    def save_provider(self, name: str, /, **fields: str) -> dict:
        providers = self._data.setdefault("providers", {})
        if name not in providers:
            providers[name] = {"provider_type": name, "base_url": "", "api_key": ""}
        providers[name].update(fields)
        self._save()
        return {"name": name, **providers[name]}

    def delete_provider(self, name: str) -> bool:
        providers = self._data.get("providers", {})
        if name not in providers:
            return False
        del providers[name]
        self._save()
        return True

    def sync_models(self, name: str) -> dict:
        """Fetch model list from the provider's /v1/models endpoint.

        Returns:
            {"name": str, "models": [...], "updated": int, "error": str|None}
        """
        import ssl
        import urllib.request

        providers = self._data.get("providers", {})
        provider = providers.get(name)
        if not provider:
            return {"name": name, "models": [], "updated": 0, "error": "Provider not found"}

        base_url: str = provider.get("base_url", "").rstrip("/")
        api_key: str = provider.get("api_key", "")

        if not base_url:
            return {"name": name, "models": [], "updated": 0, "error": "No base_url configured"}

        # Try OpenAI-compatible /v1/models endpoint
        models_url = f"{base_url}/models"
        headers = {"Accept": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        # Allow unverified SSL only when explicitly opted in
        ctx = ssl.create_default_context()
        if env_bool("ALLOW_INSECURE_SSL"):
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE

        try:
            req = urllib.request.Request(models_url, headers=headers)
            with urllib.request.urlopen(req, timeout=15, context=ctx) as resp:
                body = json.loads(resp.read())

            # Parse OpenAI-compatible response: {"data": [{"id": "model-name"}, ...]}
            data = body.get("data", [])
            if isinstance(data, list):
                models = [m["id"] for m in data if isinstance(m, dict) and "id" in m]
            else:
                models = []
        except (OSError, ValueError, KeyError) as exc:
            return {"name": name, "models": provider.get("models", []), "updated": 0, "error": str(exc)}
        except Exception as exc:
            logger.exception("Unexpected error syncing models for %s", name)
            return {"name": name, "models": provider.get("models", []), "updated": 0, "error": str(exc)}

        # Filter out non-chat models: embedding, reranker, speech, OCR, image/video gen, translation
        exclude_keywords = [
            "embedding", "moderation", "whisper", "tts", "dall-e",
            "reranker", "rerank", "speech", "asr", "sensevoice", "cosyvoice",
            "ocr", "kolors", "wan", "image-edit", "image-turbo", "z-image",
            "mt-", "bge-", "paddleocr", "captioner",
        ]
        models = [m for m in models if not any(k in m.lower() for k in exclude_keywords)]

        # Deduplicate Pro/ and LoRA/ variants: prefer base model, drop prefixes
        seen: set[str] = set()
        deduped: list[str] = []
        prefixed: set[str] = set()
        for m in models:
            if m.startswith("Pro/") or m.startswith("LoRA/"):
                prefixed.add(m)
            else:
                if m not in seen:
                    seen.add(m)
                    deduped.append(m)
        # Add prefixed variants only if base model not present
        for m in models:
            if m.startswith("Pro/") or m.startswith("LoRA/"):
                base = m.split("/", 1)[1] if "/" in m else m
                if base not in seen:
                    seen.add(base)
                    deduped.append(m)
        models = deduped

        # Update stored models
        provider["models"] = models
        self._save()
        return {"name": name, "models": models, "updated": len(models), "error": None}

    # ── search ────────────────────────────────────────────

    def get_search(self) -> dict:
        if "search" not in self._data:
            self._data["search"] = deepcopy(DEFAULT_SEARCH)
            self._save()
        return deepcopy(self._data["search"])

    def save_search(self, /, **fields: str | bool | int) -> dict:
        search = self._data.setdefault("search", {})
        search.update(fields)
        self._save()
        return deepcopy(search)

    def write_search_manifest(self, workspace: str | Path) -> Path:
        """Generate a .claw-search.json manifest from search settings.

        The claw-code-agent SearchRuntime auto-discovers this file.
        """
        search = self.get_search()
        providers: list[dict] = []

        if search.get("tavily_api_key"):
            providers.append({
                "name": "tavily",
                "provider": "tavily",
                "base_url": "https://api.tavily.com/search",
                "apiKeyEnv": "TAVILY_API_KEY",
            })
        if search.get("brave_api_key"):
            providers.append({
                "name": "brave",
                "provider": "brave",
                "base_url": "https://api.search.brave.com/res/v1/web/search",
                "apiKeyEnv": "BRAVE_SEARCH_API_KEY",
            })
        if search.get("searxng_base_url"):
            providers.append({
                "name": "searxng",
                "provider": "searxng",
                "base_url": search["searxng_base_url"],
            })

        manifest_path = Path(workspace) / ".claw-search.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(json.dumps({
            "providers": providers,
            "activeProvider": search.get("active_provider", "tavily"),
        }, indent=2), encoding="utf-8")
        return manifest_path

    # ── plugins ───────────────────────────────────────────

    def list_plugins(self) -> dict[str, dict]:
        return deepcopy(self._data.get("plugins", {}))

    def save_plugin(self, name: str, /, **fields: str) -> dict:
        plugins = self._data.setdefault("plugins", {})
        if name not in plugins:
            plugins[name] = {"enabled": False}
        plugins[name].update(fields)
        self._save()
        return {"name": name, **plugins[name]}

    def delete_plugin(self, name: str) -> bool:
        plugins = self._data.get("plugins", {})
        if name not in plugins:
            return False
        del plugins[name]
        self._save()
        return True

    # ── tools ─────────────────────────────────────────────

    def list_tools(self) -> dict[str, dict]:
        return deepcopy(self._data.get("tools", {}))

    def save_tool(self, name: str, /, **fields: str) -> dict:
        tools = self._data.setdefault("tools", {})
        if name not in tools:
            tools[name] = {}
        tools[name].update(fields)
        self._save()
        return {"name": name, **tools[name]}

    def delete_tool(self, name: str) -> bool:
        tools = self._data.get("tools", {})
        if name not in tools:
            return False
        del tools[name]
        self._save()
        return True

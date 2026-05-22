"""Settings persistence layer.

Providers, web search, tool profiles, and plugin registrations are stored
in a JSON file at ~/.factory/settings.json so they survive
project restarts without requiring a database migration.
"""

from __future__ import annotations

import json
import os
from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


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
            providers = deepcopy(DEFAULT_PROVIDERS)
            _apply_env_api_keys(providers)
            self._data = {
                "providers": providers,
                "plugins": {},
                "tools": {},
                "search": deepcopy(DEFAULT_SEARCH),
            }

    def _save(self) -> None:
        SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp = str(SETTINGS_PATH) + ".tmp"
        with open(tmp, "w") as f:
            json.dump(self._data, f, indent=2, ensure_ascii=False)
        os.replace(tmp, str(SETTINGS_PATH))

    # ── providers ─────────────────────────────────────────

    def list_providers(self) -> dict[str, dict]:
        return deepcopy(self._data.get("providers", {}))

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

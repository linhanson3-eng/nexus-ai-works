"""Settings persistence layer.

Providers, tool profiles, and plugin registrations are stored
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

DEFAULT_PROVIDERS = {
    "anthropic": {
        "provider_type": "anthropic",
        "base_url": "https://api.anthropic.com/v1",
        "api_key": "",
    },
    "deepseek": {
        "provider_type": "deepseek",
        "base_url": "https://api.deepseek.com",
        "api_key": "",
    },
    "moonshot": {
        "provider_type": "moonshot",
        "base_url": "https://api.moonshot.cn/v1",
        "api_key": "",
    },
}


@dataclass
class SettingsStore:
    """Read-write store for persistent settings.

    Usage:
        store = SettingsStore()
        providers = store.list_providers()
        store.save_provider("deepseek", api_key="sk-xxx")
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
            self._data = {"providers": deepcopy(DEFAULT_PROVIDERS), "plugins": {}, "tools": {}}

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

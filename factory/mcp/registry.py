"""MCP Server Registry -- manages known MCP servers and marketplace discovery."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import yaml

from factory.mcp.client import MCPServerConfig


@dataclass
class MarketplaceEntry:
    """A server entry from the Anthropic MCP marketplace."""

    name: str
    description: str
    category: str = ""
    install_command: str = ""
    transport: str = "stdio"
    homepage: str = ""


class MCPRegistry:
    """Registry of MCP servers from config files and marketplace."""

    def __init__(self, config_dir: Path | None = None) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        if config_dir:
            self._load_config(config_dir)

    def _load_config(self, config_dir: Path) -> None:
        """Load MCP server configs from mcp_servers.yaml."""
        path = config_dir / "mcp_servers.yaml"
        if not path.exists():
            return
        with open(path, encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        for entry in data.get("servers", []):
            if "args" in entry and isinstance(entry["args"], list):
                entry["args"] = tuple(entry["args"])
            config = MCPServerConfig(**entry)
            self._servers[config.name] = config

    def list_servers(self) -> list[MCPServerConfig]:
        """List all registered server configs."""
        return list(self._servers.values())

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get a registered server config by name."""
        return self._servers.get(name)

    def add_server(self, config: MCPServerConfig) -> None:
        """Register a new server config."""
        self._servers[config.name] = config

    def remove_server(self, name: str) -> None:
        """Remove a server config by name."""
        self._servers.pop(name, None)

    async def fetch_marketplace(self) -> list[MarketplaceEntry]:
        """Return well-known MCP servers.

        Can be extended to fetch from a live registry.
        """
        return self._builtin_entries()

    def search_marketplace(self, query: str) -> list[MarketplaceEntry]:
        """Search marketplace entries by name or description."""
        entries = self._builtin_entries()
        q = query.lower()
        return [
            e for e in entries
            if q in e.name.lower() or q in e.description.lower()
        ]

    @staticmethod
    def _builtin_entries() -> list[MarketplaceEntry]:
        """Built-in marketplace entries for sync access (no network needed)."""
        return [
            MarketplaceEntry(
                name="filesystem",
                description="File system access and manipulation",
                category="tools",
                install_command="npx -y @modelcontextprotocol/server-filesystem /tmp",
                transport="stdio",
            ),
            MarketplaceEntry(
                name="github",
                description="GitHub API access -- repos, issues, PRs, search",
                category="tools",
                install_command="npx -y @modelcontextprotocol/server-github",
                transport="stdio",
            ),
            MarketplaceEntry(
                name="postgres",
                description="PostgreSQL database access with read-only queries",
                category="database",
                install_command="npx -y @modelcontextprotocol/server-postgres",
                transport="stdio",
            ),
            MarketplaceEntry(
                name="brave-search",
                description="Web search via Brave Search API",
                category="search",
                install_command="npx -y @modelcontextprotocol/server-brave-search",
                transport="stdio",
            ),
            MarketplaceEntry(
                name="memory",
                description="Persistent memory system for knowledge graphs",
                category="memory",
                install_command="npx -y @modelcontextprotocol/server-memory",
                transport="stdio",
            ),
            MarketplaceEntry(
                name="slack",
                description="Slack workspace integration",
                category="communication",
                install_command="npx -y @modelcontextprotocol/server-slack",
                transport="stdio",
            ),
        ]

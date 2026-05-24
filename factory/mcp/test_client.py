from __future__ import annotations
"""MCP Client tests."""


import tempfile
from pathlib import Path

import pytest

from factory.mcp.client import MCPClient, MCPServerConfig, MCPTool


class TestMCPServerConfig:
    """Frozen dataclass tests."""

    def test_default_values(self) -> None:
        config = MCPServerConfig(name="test-server")
        assert config.name == "test-server"
        assert config.transport == "stdio"
        assert config.command == ""
        assert config.args == ()
        assert config.env == {}
        assert config.cwd == ""
        assert config.url == ""
        assert config.description == ""

    def test_full_config(self) -> None:
        config = MCPServerConfig(
            name="github",
            transport="stdio",
            command="npx",
            args=("-y", "@modelcontextprotocol/server-github"),
            env={"GITHUB_TOKEN": "xxx"},
            description="GitHub API access",
        )
        assert config.name == "github"
        assert config.transport == "stdio"
        assert config.command == "npx"
        assert config.args == ("-y", "@modelcontextprotocol/server-github")

    def test_is_frozen(self) -> None:
        config = MCPServerConfig(name="test")
        with pytest.raises(Exception):
            config.name = "changed"  # type: ignore[misc]

    def test_http_transport_config(self) -> None:
        config = MCPServerConfig(
            name="remote-server",
            transport="http",
            url="https://mcp.example.com/sse",
            description="Remote MCP server",
        )
        assert config.transport == "http"
        assert config.url == "https://mcp.example.com/sse"


class TestMCPTool:
    """MCPTool frozen dataclass tests."""

    def test_basic_tool(self) -> None:
        tool = MCPTool(server_name="github", name="search_repos")
        assert tool.server_name == "github"
        assert tool.name == "search_repos"
        assert tool.description == ""
        assert tool.input_schema == {}

    def test_tool_with_schema(self) -> None:
        schema = {
            "type": "object",
            "properties": {"query": {"type": "string"}},
        }
        tool = MCPTool(
            server_name="github",
            name="search_repos",
            description="Search repos",
            input_schema=schema,
        )
        assert tool.description == "Search repos"
        assert tool.input_schema == schema


class TestMCPClientRegistration:
    """Tests for server registration and lookup (no actual connections)."""

    @pytest.fixture
    def client(self) -> MCPClient:
        return MCPClient()

    @pytest.mark.asyncio
    async def test_add_and_get_server(self, client: MCPClient) -> None:
        config = MCPServerConfig(name="filesystem", command="npx")
        await client.add_server(config)
        retrieved = client.get_server("filesystem")
        assert retrieved is not None
        assert retrieved.name == "filesystem"

    @pytest.mark.asyncio
    async def test_list_servers(self, client: MCPClient) -> None:
        await client.add_server(MCPServerConfig(name="server-a"))
        await client.add_server(MCPServerConfig(name="server-b"))
        servers = client.list_servers()
        assert len(servers) == 2
        names = {s.name for s in servers}
        assert names == {"server-a", "server-b"}

    @pytest.mark.asyncio
    async def test_get_nonexistent_server(self, client: MCPClient) -> None:
        assert client.get_server("nonexistent") is None

    @pytest.mark.asyncio
    async def test_connect_unknown_server_raises(self, client: MCPClient) -> None:
        with pytest.raises(ValueError, match="Unknown server"):
            await client.connect("nonexistent")

    @pytest.mark.asyncio
    async def test_close_all_clean(self, client: MCPClient) -> None:
        await client.add_server(MCPServerConfig(name="server-a"))
        await client.add_server(MCPServerConfig(name="server-b"))
        await client.close_all()
        # Server configs remain registered; close_all only disconnects
        assert len(client.list_servers()) == 2


class TestMCPRegistry:
    """Registry tests with YAML config loading."""

    @pytest.fixture
    def config_dir(self) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            yield tmp

    def _write_config(self, config_dir: str, content: str) -> None:
        path = Path(config_dir) / "mcp_servers.yaml"
        path.write_text(content, encoding="utf-8")

    def test_load_from_yaml(self, config_dir: str) -> None:
        from factory.mcp.registry import MCPRegistry

        self._write_config(
            config_dir,
            """
servers:
  - name: filesystem
    transport: stdio
    command: npx
    args:
      - "-y"
      - "@modelcontextprotocol/server-filesystem"
      - "/tmp"
    description: "File system access"
""",
        )
        registry = MCPRegistry(Path(config_dir))
        servers = registry.list_servers()
        assert len(servers) == 1
        assert servers[0].name == "filesystem"
        assert servers[0].transport == "stdio"

    def test_load_empty_config(self, config_dir: str) -> None:
        from factory.mcp.registry import MCPRegistry

        self._write_config(config_dir, "servers: []")
        registry = MCPRegistry(Path(config_dir))
        assert registry.list_servers() == []

    def test_load_nonexistent_file(self, config_dir: str) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry(Path(config_dir) / "nonexistent")
        assert registry.list_servers() == []

    def test_add_and_remove_server(self) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry()
        config = MCPServerConfig(name="test", command="echo")
        registry.add_server(config)
        assert len(registry.list_servers()) == 1
        registry.remove_server("test")
        assert registry.list_servers() == []

    def test_get_server(self) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry()
        config = MCPServerConfig(name="test", command="echo")
        registry.add_server(config)
        assert registry.get_server("test") is not None
        assert registry.get_server("nonexistent") is None

    def test_marketplace_fetch(self) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry()
        import asyncio

        entries = asyncio.run(registry.fetch_marketplace())
        assert len(entries) >= 4
        names = {e.name for e in entries}
        assert "filesystem" in names
        assert "github" in names

    def test_marketplace_search(self) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry()
        results = registry.search_marketplace("database")
        assert len(results) >= 1
        assert any("postgres" in r.name for r in results)

    def test_marketplace_search_no_match(self) -> None:
        from factory.mcp.registry import MCPRegistry

        registry = MCPRegistry()
        results = registry.search_marketplace("nonexistent_xyz_123")
        assert results == []

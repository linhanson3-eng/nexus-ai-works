"""MCP Client -- wraps Python mcp SDK for tool discovery and invocation."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import stdio_client, StdioServerParameters
from mcp.client.streamable_http import streamable_http_client


@dataclass(frozen=True)
class MCPServerConfig:
    """Configuration for connecting to an MCP server."""

    name: str
    transport: str = "stdio"
    command: str = ""
    args: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    cwd: str = ""
    url: str = ""
    description: str = ""


@dataclass(frozen=True)
class MCPTool:
    """A tool discovered from an MCP server."""

    server_name: str
    name: str
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=dict)


class MCPClient:
    """Client for connecting to MCP servers and invoking tools."""

    def __init__(self) -> None:
        self._servers: dict[str, MCPServerConfig] = {}
        self._sessions: dict[str, ClientSession] = {}
        self._tools: dict[str, list[MCPTool]] = {}
        self._transports: dict[str, Any] = {}

    async def add_server(self, config: MCPServerConfig) -> None:
        """Register an MCP server config."""
        self._servers[config.name] = config

    async def connect(self, server_name: str) -> None:
        """Establish connection to a server via its configured transport."""
        if server_name in self._sessions:
            return
        config = self._servers.get(server_name)
        if not config:
            raise ValueError(f"Unknown server: {server_name}")

        if config.transport == "http" and config.url:
            transport_ctx = streamable_http_client(config.url)
            read, write, _ = await transport_ctx.__aenter__()
            session = ClientSession(read, write)
            await session.initialize()
            self._transports[server_name] = transport_ctx
        else:
            params = StdioServerParameters(
                command=config.command,
                args=list(config.args),
                env=config.env if config.env else None,
            )
            transport_ctx = stdio_client(params)
            read, write = await transport_ctx.__aenter__()
            session = ClientSession(read, write)
            await session.initialize()
            self._transports[server_name] = transport_ctx

        self._sessions[server_name] = session

    async def list_tools(self, server_name: str) -> list[MCPTool]:
        """Discover tools from a server. Results cached after first call."""
        if server_name in self._tools:
            return self._tools[server_name]
        await self.connect(server_name)
        session = self._sessions[server_name]
        result = await session.list_tools()
        tools = [
            MCPTool(
                server_name=server_name,
                name=t.name,
                description=t.description or "",
                input_schema=t.inputSchema if hasattr(t, "inputSchema") else {},
            )
            for t in result.tools
        ]
        self._tools[server_name] = tools
        return tools

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> Any:
        """Invoke a tool on a remote MCP server."""
        await self.connect(server_name)
        session = self._sessions[server_name]
        result = await session.call_tool(tool_name, arguments)
        if hasattr(result, "content") and result.content:
            texts = [
                c.text for c in result.content if hasattr(c, "text") and c.text
            ]
            return "\n".join(texts) if texts else str(result.content)
        return str(result)

    async def close_server(self, server_name: str) -> None:
        """Disconnect a single server."""
        self._tools.pop(server_name, None)
        self._sessions.pop(server_name, None)
        transport = self._transports.pop(server_name, None)
        if transport:
            try:
                await transport.__aexit__(None, None, None)
            except Exception:
                pass

    async def close_all(self) -> None:
        """Disconnect all servers."""
        for name in list(self._sessions.keys()):
            await self.close_server(name)

    def get_server(self, name: str) -> MCPServerConfig | None:
        """Get a registered server config by name."""
        return self._servers.get(name)

    def list_servers(self) -> list[MCPServerConfig]:
        """List all registered server configs."""
        return list(self._servers.values())

"""Nexus platform tools registered directly in the agent's tool registry.

These are the same tools exposed via the MCP endpoint, but registered
as native AgentTool instances so agent can use them without HTTP MCP.

Only stdio MCP is supported by the vendor SDK — HTTP MCP servers
(like our gateway/mcp endpoint) are ignored by .mcp.json discovery.
"""
from __future__ import annotations

import json
from typing import Any

from factory.engine.bridge import AgentTool, ToolExecutionResult


# ── Tool parameter schemas (same as MCP TOOL_DEFINITIONS inputSchema) ──

_PARAMS = {
    "nexus_execute_task": {
        "type": "object",
        "properties": {
            "task": {"type": "string", "description": "任务描述"},
            "mode": {"type": "string", "enum": ["continue", "fork", "spawn", "btw"], "default": "spawn"},
            "parent_session_id": {"type": "string", "description": "父会话ID (fork需要)"},
            "workshop": {"type": "string", "description": "工作区名称"},
            "model": {"type": "string", "description": "模型名称(可选，如 deepseek/deepseek-v4-pro)"},
            "agent_name": {"type": "string", "description": "指定 Agent 名称(可选，默认第一个)"},
        },
        "required": ["task", "workshop"],
    },
    "nexus_list_sessions": {
        "type": "object",
        "properties": {"workshop": {"type": "string"}},
        "required": ["workshop"],
    },
    "nexus_stop_session": {
        "type": "object",
        "properties": {
            "session_id": {"type": "string"},
            "reason": {"type": "string"},
        },
        "required": ["session_id"],
    },
    "nexus_get_status": {
        "type": "object",
        "properties": {"workshop": {"type": "string"}},
        "required": [],
    },
    "nexus_cross_review": {
        "type": "object",
        "properties": {
            "workshop": {"type": "string", "description": "工作区名称"},
            "target": {"type": "string", "description": "要审查的文件路径"},
            "models": {
                "type": "array",
                "items": {"type": "string"},
                "description": "审查模型列表(至少2个)",
            },
            "focus": {"type": "string", "description": "审查重点(可选)"},
        },
        "required": ["workshop", "target", "models"],
    },
    "nexus_review_loop": {
        "type": "object",
        "properties": {
            "workshop": {"type": "string", "description": "工作区名称"},
            "target": {"type": "string", "description": "要审查并修复的文件路径"},
            "models": {
                "type": "array", "items": {"type": "string"},
                "description": "审查模型列表(至少2个)",
            },
            "fix_model": {"type": "string", "description": "执行修复的模型(默认用models[0])"},
            "focus": {"type": "string", "description": "审查重点(可选)"},
        },
        "required": ["workshop", "target", "models"],
    },
    "nexus_read_board": {
        "type": "object",
        "properties": {"workshop": {"type": "string"}},
        "required": ["workshop"],
    },
    "nexus_read_workspace": {
        "type": "object",
        "properties": {
            "workshop": {"type": "string"},
            "path": {"type": "string"},
        },
        "required": ["workshop", "path"],
    },
    "nexus_write_workspace": {
        "type": "object",
        "properties": {
            "workshop": {"type": "string"},
            "path": {"type": "string"},
            "content": {"type": "string"},
        },
        "required": ["workshop", "path", "content"],
    },
    "nexus_list_workspace": {
        "type": "object",
        "properties": {
            "workshop": {"type": "string"},
            "path": {"type": "string", "description": "子路径(默认根目录)"},
        },
        "required": ["workshop"],
    },
}


def _build_tool(
    tool_name: str,
    description: str,
    org: Any,
    kanban_store: Any,
    session_manager: Any,
    settings_store: Any,
) -> AgentTool:
    """Create an AgentTool that calls the MCP execute_tool under the hood."""
    from gateway.mcp.tools import execute_tool
    import asyncio as _asyncio

    def handler(arguments: dict[str, Any], context) -> str:
        # Handler runs in thread pool (via _asyncio.to_thread). Create a fresh
        # event loop per call because the main loop is in another thread.
        loop = _asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(
                execute_tool(
                    tool_name, arguments,
                    org=org, kanban_store=kanban_store,
                    session_manager=session_manager,
                    mcp_token_payload={},
                    settings_store=settings_store,
                ),
            )
        finally:
            loop.close()

        if result.get("isError"):
            return f"Error: {result['content'][0]['text']}"
        return result["content"][0]["text"]

    return AgentTool(
        name=tool_name,
        description=description,
        parameters=_PARAMS[tool_name],
        handler=handler,
    )


# ── Tool cache: build once, reuse across runs ──

_NEXUS_TOOLS_CACHE: dict[str, AgentTool] | None = None


def register_nexus_tools(
    engine: Any,
    org: Any,
    kanban_store: Any,
    session_manager: Any,
    settings_store: Any,
) -> None:
    """Register all nexus platform tools on the engine's tool registry.

    Tools are built once and cached. Subsequent calls are a no-op
    (checked via engine.tool_registry).
    """
    global _NEXUS_TOOLS_CACHE

    if "nexus_get_status" in engine.tool_registry:
        return  # already registered on this engine

    if _NEXUS_TOOLS_CACHE is None:
        _NEXUS_TOOLS_CACHE = {}
        tool_specs = [
            ("nexus_execute_task", "创建或继续Agent任务。mode: spawn(新任务)/fork(继承父上下文)/continue(继续)/btw(旁路)"),
            ("nexus_cross_review", "并行启动多个不同模型独立审查代码，汇总对比结论(consensus+unique+conflicts)"),
            ("nexus_review_loop", "审查→修复→验证闭环: 交叉审查→自动修复→再审查对比"),
            ("nexus_list_sessions", "列出所有session及fork/spawn关系"),
            ("nexus_stop_session", "停止指定session"),
            ("nexus_get_status", "获取工作区状态(agent数/看板/运行中任务)"),
            ("nexus_read_board", "读取看板状态"),
            ("nexus_read_workspace", "读取workspace文件内容"),
            ("nexus_write_workspace", "写入文件到workspace"),
            ("nexus_list_workspace", "列出workspace目录文件"),
        ]
        for name, desc in tool_specs:
            _NEXUS_TOOLS_CACHE[name] = _build_tool(
                name, desc, org, kanban_store, session_manager, settings_store,
            )

    engine.tool_registry.update(_NEXUS_TOOLS_CACHE)

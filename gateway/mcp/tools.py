from __future__ import annotations

"""MCP tools — ai-factory capabilities exposed over JSON-RPC 2.0.

Tool design follows Agor's pattern: merged modes (not split tools),
tool discovery built-in, workspace-level read/write, isError standardization.
"""

import json
from pathlib import Path
from typing import Any


TOOL_DEFINITIONS: list[dict[str, Any]] = [

    # ── Tool discovery ──
    {
        "name": "nexus_list_tools",
        "description": "列出所有可用的 MCP tools，可按关键词搜索",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "可选的搜索关键词，匹配 tool name 和 description",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_describe_tool",
        "description": "获取指定 tool 的详细描述和参数说明",
        "inputSchema": {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "tool 名称"},
            },
            "required": ["name"],
        },
    },

    # ── 会话执行 (合并 continue/fork/spawn/btw) ──
    {
        "name": "nexus_execute_task",
        "description": (
            "执行一个 Agent 任务。通过 mode 参数控制执行模式:\n"
            "- continue: 在当前会话中继续执行\n"
            "- fork: 在当前会话的同一层级创建 fork，探索替代方案\n"
            "- spawn: 创建子会话处理子任务\n"
            "- btw: 旁路询问——不阻塞目标 session，完成后自动 callback 结果回调用方 (Phase 2)"
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "task": {"type": "string", "description": "任务描述"},
                "mode": {
                    "type": "string",
                    "enum": ["continue", "fork", "spawn", "btw"],
                    "default": "continue",
                    "description": "执行模式",
                },
                "parent_session_id": {
                    "type": "string",
                    "description": "父会话 ID (fork/spawn/btw 模式需要)",
                },
                "workshop": {
                    "type": "string",
                    "description": "工作区名称",
                },
                "model": {
                    "type": "string",
                    "description": "模型名称 (可选)",
                },
            },
            "required": ["task", "workshop"],
        },
    },

    # ── 平台感知 ──
    {
        "name": "nexus_get_status",
        "description": "获取 ai-factory 整体状态: Workshop 列表、Agent 数、看板、运行中任务",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {
                    "type": "string",
                    "description": "可选——指定工作区名称以获取详细状态",
                },
            },
            "required": [],
        },
    },
    {
        "name": "nexus_read_board",
        "description": "读取指定 Workshop 的看板状态（列、卡片、执行进度）",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string"},
            },
            "required": ["workshop"],
        },
    },

    # ── Workspace 读写 ──
    {
        "name": "nexus_read_workspace",
        "description": "读取 Workshop 目录中的文件内容",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的文件路径"},
            },
            "required": ["workshop", "path"],
        },
    },
    {
        "name": "nexus_write_workspace",
        "description": "写入文件到 Workshop 目录",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的文件路径"},
                "content": {"type": "string", "description": "文件内容"},
            },
            "required": ["workshop", "path", "content"],
        },
    },
    {
        "name": "nexus_list_workspace",
        "description": "列出 Workshop 目录中的文件",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
                "path": {"type": "string", "description": "相对于 workspace 根目录的子路径 (默认根目录)"},
            },
            "required": ["workshop"],
        },
    },

    # ── 工作流 ──
    {
        "name": "nexus_run_workflow",
        "description": "执行一个工作流模板 (DAG 并行调度)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string"},
                "workflow_name": {"type": "string"},
                "task": {"type": "string"},
            },
            "required": ["workshop", "workflow_name", "task"],
        },
    },
]


def _err(text: str) -> dict[str, Any]:
    """Standardized error response with isError flag."""
    return {"content": [{"type": "text", "text": text}], "isError": True}


async def execute_tool(
    tool_name: str,
    arguments: dict[str, Any],
    *,
    org: Any,
    kanban_store: Any,
    session_manager: Any,
    mcp_token_payload: dict[str, Any],
) -> dict[str, Any]:
    """Execute a tool call and return MCP-compatible result."""
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(org, kanban_store)
    workshop_name = arguments.get("workshop", "")

    # ── Tool discovery ──

    if tool_name == "nexus_list_tools":
        query = (arguments.get("query", "") or "").lower()
        tools = TOOL_DEFINITIONS
        if query:
            tools = [
                t for t in tools
                if query in t["name"].lower() or query in t["description"].lower()
            ]
        result = [
            {"name": t["name"], "description": t["description"].split("\n")[0]}
            for t in tools
        ]
        return {"content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False, indent=2)}]}

    if tool_name == "nexus_describe_tool":
        name = arguments["name"]
        for t in TOOL_DEFINITIONS:
            if t["name"] == name:
                return {"content": [{"type": "text", "text": json.dumps(t, ensure_ascii=False, indent=2)}]}
        return _err(f"Tool not found: {name}")

    # ── 平台状态 ──

    if tool_name == "nexus_get_status":
        if workshop_name:
            ws = mgr.get(workshop_name)
            if ws is None:
                return _err(f"工作区 {workshop_name} 不存在")
            status = mgr.status(workshop_name)
            return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}
        status = org.status()
        return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}

    if tool_name == "nexus_read_board":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        status = mgr.status(workshop_name)
        if status is None:
            return _err(f"无法获取 {workshop_name} 状态")
        return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}

    # ── Workspace 读写 ──

    if tool_name == "nexus_read_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        file_path = ws.workspace / arguments["path"]
        try:
            content = file_path.read_text("utf-8")
            return {"content": [{"type": "text", "text": content}]}
        except FileNotFoundError:
            return _err(f"文件不存在: {arguments['path']}")
        except UnicodeDecodeError:
            return _err(f"文件不是文本格式: {arguments['path']}")

    if tool_name == "nexus_write_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        file_path = ws.workspace / arguments["path"]
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(arguments["content"], "utf-8")
        return {"content": [{"type": "text", "text": f"已写入: {arguments['path']}"}]}

    if tool_name == "nexus_list_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        subpath = ws.workspace / (arguments.get("path", "") or ".")
        if not subpath.exists():
            return _err(f"路径不存在: {arguments.get('path', '.')}")
        entries = []
        for p in sorted(subpath.iterdir()):
            entries.append({
                "name": p.name,
                "type": "dir" if p.is_dir() else "file",
                "size": p.stat().st_size if p.is_file() else 0,
            })
        return {"content": [{"type": "text", "text": json.dumps(entries, ensure_ascii=False, indent=2)}]}

    # ── 合并式会话执行 ──

    if tool_name == "nexus_execute_task":
        task = arguments.get("task", "")
        mode = arguments.get("mode", "continue")
        parent_id = arguments.get("parent_session_id", "")
        model = arguments.get("model", "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        if not ws.spec.agents:
            return _err("工作区没有 Agent")

        agent_spec = ws.spec.agents[0]
        from factory.memory import MemoryStore
        from factory.runner import NexusAgentRunner

        store = MemoryStore(":memory:")
        runner = NexusAgentRunner(agent_spec, ws, store)
        if model:
            runner.set_model_override(model)

        prefixed_task = task
        if mode == "fork":
            prefixed_task = f"[FORK from session {parent_id}]\n\n探索替代方案: {task}"
        elif mode == "spawn":
            prefixed_task = f"[SPAWN sub-session, parent={parent_id}]\n\n子任务: {task}"
        elif mode == "btw":
            prefixed_task = f"[BTW inquiry to session {parent_id}]\n\n旁路询问: {task}"

        result = await runner.run(prefixed_task)
        text = result.content[:5000] or "(empty response)"

        output = {
            "session_id": result.session_id,
            "mode": mode,
            "output": text,
            "turns": result.turns,
            "tools_used": result.tools_used,
            "model": result.model,
        }
        return {"content": [{"type": "text", "text": json.dumps(output, ensure_ascii=False, indent=2)}]}

    # ── 工作流 ──

    if tool_name == "nexus_run_workflow":
        workflow_name = arguments.get("workflow_name", "")
        task = arguments.get("task", "")
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        from factory.workflow.engine import WorkflowRunner
        tmpl = org.workflow_store.load(workflow_name) if org.workflow_store else None
        if tmpl is None:
            return _err(f"工作流 {workflow_name} 不存在")
        runner = WorkflowRunner(ws)
        result = await runner.run(tmpl, task)
        return {"content": [{"type": "text", "text": result.final_output or str(result.node_results)}]}

    return _err(f"Unknown tool: {tool_name}")

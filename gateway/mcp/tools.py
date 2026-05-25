from __future__ import annotations

"""MCP tools — ai-factory capabilities exposed over JSON-RPC 2.0.

Tool design follows Agor's pattern: merged modes (not split tools),
tool discovery built-in, workspace-level read/write, isError standardization.
"""

import json
from pathlib import Path
from typing import Any


def _safe_path(workspace_root: Path, relative: str) -> Path | None:
    """Resolve relative path inside workspace. Returns None if path escapes."""
    resolved = (workspace_root / relative).resolve()
    if not resolved.is_relative_to(workspace_root.resolve()):
        return None
    return resolved


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

    # ── 会话控制 ──
    {
        "name": "nexus_stop_session",
        "description": "停止正在执行的会话。Agent 发现子任务跑偏或质量不达标时，主动停止该会话",
        "inputSchema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "要停止的会话 ID"},
                "reason": {"type": "string", "description": "停止原因"},
            },
            "required": ["session_id"],
        },
    },
    {
        "name": "nexus_list_sessions",
        "description": "列出当前工作区的所有会话（含父子关系），用于了解 fork/spawn 树结构",
        "inputSchema": {
            "type": "object",
            "properties": {
                "workshop": {"type": "string", "description": "工作区名称"},
            },
            "required": ["workshop"],
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
    settings_store: Any = None,
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
        file_path = _safe_path(ws.workspace, arguments["path"])
        if file_path is None:
            return _err(f"路径越界: {arguments['path']}")
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
        file_path = _safe_path(ws.workspace, arguments["path"])
        if file_path is None:
            return _err(f"路径越界: {arguments['path']}")
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(arguments["content"], "utf-8")
        return {"content": [{"type": "text", "text": f"已写入: {arguments['path']}"}]}

    if tool_name == "nexus_list_workspace":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")
        subpath = _safe_path(ws.workspace, arguments.get("path", "") or ".")
        if subpath is None:
            return _err(f"路径越界: {arguments.get('path', '.')}")
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

        from factory.engine.bridge import (
            AgentLoopEngine,
            EngineConfig,
            create_agent,
            create_model_config,
        )
        from factory.engine.providers import ProviderRegistry

        # Resolve model + api_key via provider registry (same as runner)
        effective_model = model or getattr(agent_spec, 'model', '') or "deepseek/deepseek-v4-pro"
        if settings_store is not None:
            registry = ProviderRegistry.from_store(settings_store)
        else:
            from factory.settings import SettingsStore
            registry = ProviderRegistry.from_store(SettingsStore())

        model_cfg = create_model_config(effective_model, registry=registry)
        engine_cfg = EngineConfig(
            cwd=ws.workspace,
            max_turns=getattr(agent_spec, 'max_turns', 30),
            session_directory=str(ws.workspace / ".sessions"),
        )
        agent = create_agent(model_cfg, engine_cfg)
        engine = AgentLoopEngine(agent, engine_config=engine_cfg)

        if mode == "fork" and parent_id:
            # Real fork: clone parent's full conversation history, new session ID
            result = await engine.fork(task, parent_id)
        elif mode == "spawn":
            # Real spawn: clean context, no parent history inheritance
            result = await engine.spawn(task)
        elif mode == "btw" and parent_id:
            # Btw: fork variant — ephemeral by-call, auto-callback result to parent
            result = await engine.fork(task, parent_id)
        elif mode == "continue" and parent_id:
            # Resume existing session
            result = await engine.resume(task, parent_id)
        else:
            result = await engine.run(task)

        # Extract fields from AgentRunResult (matches runner.py's conversion)
        output_text = getattr(result, 'final_output', '') or ''
        session_id_out = result.session_id or ""
        stop_reason = getattr(result, 'stop_reason', '') or ''
        is_error = stop_reason and stop_reason not in ("end_turn", "stop", "max_tokens")
        turns_val = getattr(result, 'turns', 0)
        cost_val = getattr(result, 'total_cost_usd', 0.0) or 0.0
        tc = getattr(result, 'tool_calls', None)
        tools_list = tc if isinstance(tc, list) else []

        # Record to SessionTree
        from factory.workflow.session_tree import SessionNode, SessionType, SessionStatus, SessionTree

        st = SessionTree(workshop_name=workshop_name)
        node = SessionNode(
            session_id=session_id_out,
            parent_id=parent_id,
            session_type=SessionType(mode if mode != "continue" else "root"),
            workshop_name=workshop_name,
            task=task,
            status=SessionStatus.FAILED if is_error else SessionStatus.COMPLETED,
            agent_name=agent_spec.name,
            model=effective_model,
            output=output_text[:5000],
            error=stop_reason if is_error else "",
            turns=turns_val,
            cost_usd=cost_val,
            tools_used=tools_list,
        )
        st.add(node)

        output = {
            "session_id": session_id_out,
            "mode": mode,
            "output": output_text[:5000],
            "turns": turns_val,
            "tools_used": tools_list,
            "model": effective_model,
            "error": stop_reason if is_error else None,
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

    # ── 会话控制 ──

    if tool_name == "nexus_stop_session":
        target_id = arguments["session_id"]
        reason = arguments.get("reason", "手动停止")

        st = SessionTree(workshop_name=workshop_name)
        node = st.get(target_id)
        if node is None:
            return _err(f"会话 {target_id} 不存在")

        # Mark session as failed in the tree
        node.status = SessionStatus.FAILED
        node.error = reason
        st._save()

        return {"content": [{"type": "text", "text": json.dumps({
            "session_id": target_id,
            "status": "stopped",
            "reason": reason,
        }, ensure_ascii=False)}]}

    if tool_name == "nexus_list_sessions":
        ws = mgr.get(workshop_name)
        if ws is None:
            return _err(f"工作区 {workshop_name} 不存在")

        from factory.workflow.session_tree import SessionTree
        st = SessionTree(workshop_name=workshop_name)
        nodes = st.all_nodes()
        result_list = []
        for n in nodes:
            result_list.append({
                "session_id": n.session_id,
                "parent_id": n.parent_id,
                "type": n.session_type.value if n.session_type else "root",
                "task": n.task[:120],
                "status": n.status.value if n.status else "unknown",
                "agent": n.agent_name,
                "turns": n.turns,
            })
        return {"content": [{"type": "text", "text": json.dumps(result_list, ensure_ascii=False, indent=2)}]}

    return _err(f"Unknown tool: {tool_name}")

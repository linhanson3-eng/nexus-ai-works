"""Agent run and chat endpoints."""

from __future__ import annotations

import asyncio
import json
import logging
import re

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from gateway.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["agent"])

from factory.env import env_int

REQUEST_TIMEOUT = env_int("AGENT_REQUEST_TIMEOUT", 600, min=10, max=3600)


class AgentRunRequest(BaseModel):
    model: str = ""
    reasoning_effort: str = ""  # "low" | "medium" | "high" | "xhigh"
    task: str = Field(..., max_length=10000)
    workshop: str = Field("", max_length=200)


class AgentChatRequest(BaseModel):
    message: str = Field(..., max_length=5000)


def _org(request: Request):
    return request.app.state.org


def _kanban_store(request: Request):
    return request.app.state.kanban_store


def _session_manager(request: Request):
    return request.app.state.session_manager


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/agent/run/stream", dependencies=[Depends(require_auth)])
async def agent_run_stream(body: AgentRunRequest, request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.runner import NexusAgentRunner
    from factory.memory import MemoryStore

    task = body.task.strip()
    workshop_name = body.workshop
    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)

    # Reject new agent runs during graceful shutdown
    if getattr(request.app.state, "shutdown", None) and request.app.state.shutdown.is_shutting_down:
        return JSONResponse(content={"detail": "Server is shutting down"}, status_code=503)

    org = _org(request)
    mgr = WorkshopManager(org, _kanban_store(request))
    ws = mgr.get(workshop_name) if workshop_name else (org.workshops[0] if org.workshops else None)
    if ws is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
    workshop_name = ws.name

    if not ws.spec.agents:
        return JSONResponse(content={"detail": "No agents in workshop"}, status_code=400)
    agent_spec = ws.spec.agents[0]
    store = MemoryStore(":memory:")
    runner = NexusAgentRunner(agent_spec, ws, store)
    runner._request_id = request_id  # attach for log tracing
    if body.model:
        runner.set_model_override(body.model)
    if body.reasoning_effort:
        runner.set_reasoning_effort(body.reasoning_effort)

    request_id = getattr(request.state, "request_id", "")

    async def event_stream():
        yield _sse("status", {"event": "started", "task": task[:200], "workshop": workshop_name, "request_id": request_id[:8]})

        agent_task = asyncio.create_task(
            asyncio.wait_for(runner.run(task), timeout=REQUEST_TIMEOUT)
        )

        while True:
            done, _ = await asyncio.wait([agent_task], timeout=15.0)
            if agent_task in done:
                break
            yield ": heartbeat\n\n"

        try:
            result = await agent_task
            if result.session_id:
                _session_manager(request).set(workshop_name, result.session_id)

            for evt in result.events:
                yield _sse(evt.get("type", "event"), evt)
                await asyncio.sleep(0.015)

            yield _sse("completed", {
                "reply": result.content[:3000],
                "turns": result.turns,
                "cost_usd": result.cost_usd,
                "tools_used": result.tools_used,
                "session_id": result.session_id,
                "model": result.model,
            })
            if result.error:
                yield _sse("error", {"message": result.error})
        except Exception:
            logger.exception("Agent run SSE failed")
            yield _sse("error", {"message": "An internal error occurred. Please try again."})
        yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ── Agent Chat ──


@router.post("/agent/chat", dependencies=[Depends(require_auth)])
async def agent_chat(body: AgentChatRequest, request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.workflow.engine import WorkflowRunner

    message = body.message.strip()
    if not message:
        return JSONResponse(content={"reply": "请输入消息。", "actions": []})

    org = _org(request)
    mgr = WorkshopManager(org, _kanban_store(request))

    intent, params = _parse_intent(message)

    if intent == "create_workshop":
        name = params.get("name", "未命名工作区")
        workflow = params.get("workflow", "")
        ws = mgr.create(name=name, workflow_name=workflow or "simple")
        status = mgr.status(name)
        agent_count = status.get("total_agents", 1) if status else 1
        board_id = status.get("kanban_board_id", "") if status else ""
        reply = (
            f"工作区 **{name}** 已创建\n\n"
            f"- 工作流: `{workflow}`\n"
            f"- Agent: {agent_count} 个（含 super agent）\n"
            f"- 看板: {'已自动生成' if board_id else '创建失败'}\n"
            f"- 工作目录: `workspaces/{name}/`\n\n"
            f"现在可以对它说：**「在 {name} 执行工作流」** 或 **「查看 {name} 的看板」**"
        )
        return JSONResponse(content={"reply": reply, "actions": [
            {"label": "查看工作区", "href": "/workshops"},
            {"label": "查看看板", "href": "/kanban"},
        ]})

    elif intent == "delete_workshop":
        name = params.get("name", "")
        if not name:
            return JSONResponse(content={"reply": "请指定要删除的工作区名称，比如「删除 测试工作区」"})
        deleted = mgr.delete(name)
        if deleted:
            return JSONResponse(content={"reply": f"工作区 **{name}** 已删除。"})
        else:
            return JSONResponse(content={"reply": f"工作区 **{name}** 不存在。"})

    elif intent == "run_workflow":
        name = params.get("workshop", "")
        task = params.get("task", "")
        workflow = params.get("workflow", "")
        if not name or not task:
            return JSONResponse(content={"reply": "请指定工作区和任务，比如「在 工作区名 执行 工作流名」"})
        ws = mgr.get(name)
        if ws is None:
            return JSONResponse(content={"reply": f"工作区 **{name}** 不存在。先说「创建 {name} 工作区」来新建一个。"})
        tmpl = org.workflow_store.load(workflow) if workflow else None
        if tmpl is None:
            available = [w["name"] for w in org.workflow_store.list_all()]
            return JSONResponse(content={"reply": f"工作流 **{workflow}** 不存在。可用: {', '.join(available)}"})
        runner = WorkflowRunner(ws)
        result = await runner.run(tmpl, task)
        node_lines = []
        for nid, nr in result.node_results.items():
            icon = "✓" if nr.status.value == "passed" else "✗"
            node_lines.append(f"  {icon} **{nr.node_id}** ({nr.agent_name}): {nr.output[:200]}")
        reply = f"工作流 **{workflow}** 在 **{name}** 执行完毕\n\n" + "\n".join(node_lines)
        return JSONResponse(content={"reply": reply, "actions": [
            {"label": "查看看板", "href": "/kanban"},
            {"label": f"查看 {name}", "href": "/workshops"},
        ]})

    elif intent == "list_workshops":
        workshops = mgr.list_all()
        if not workshops:
            return JSONResponse(content={"reply": "当前没有工作区。对我说「创建一个 XX 工作区」来开始。"})
        lines = ["当前工作区：\n"]
        for w in workshops:
            kb = "已绑定看板" if w.has_kanban else "无看板"
            lines.append(f"- **{w.name}** — {w.agent_count} agents, 工作流 `{w.workflow_name}`, {kb}")
        return JSONResponse(content={"reply": "\n".join(lines), "actions": [
            {"label": "查看全部工作区", "href": "/workshops"},
        ]})

    elif intent == "list_kanban":
        boards = _kanban_store(request).list_boards()
        if not boards:
            return JSONResponse(content={"reply": "当前没有看板。创建工作区时会自动生成看板。"})
        lines = ["当前看板：\n"]
        for b in boards:
            lists = _kanban_store(request).get_lists(b["id"])
            total = sum(len(_kanban_store(request).get_cards(lst["id"])) for lst in lists)
            lines.append(f"- **{b['name']}** — {len(lists)} 列表, {total} 卡片")
        return JSONResponse(content={"reply": "\n".join(lines), "actions": [
            {"label": "打开看板", "href": "/kanban"},
        ]})

    elif intent == "help":
        return JSONResponse(content={"reply": (
            "我是 Nexus AI Works 助手，可以帮你：\n\n"
            "**工作区管理**\n"
            "- 「创建 XXX 工作区」— 新建工作区，自动配 Agent + 看板\n"
            "- 「删除 XXX 工作区」— 删除工作区\n"
            "- 「查看所有工作区」— 列出工作区\n\n"
            "**工作流执行**\n"
            "- 「在 XXX 执行 (工作流名)」— 运行工作流\n\n"
            "**看板**\n"
            "- 「查看看板」— 列出所有看板\n\n"
            "直接跟我说你想做什么就行。"
        )})

    else:
        reply = (
            f"收到：「{message}」\n\n"
            f"我可以帮你管理工作区、运行工作流、查看看板。\n"
            f"试试对我说：**「创建一个开发工作区」** 或 **「帮助」**"
        )
        return JSONResponse(content={"reply": reply})



# ── Session History ──

@router.get("/agent/session/{session_id}", dependencies=[Depends(require_auth)])
async def get_session(session_id: str, request: Request):
    """Load conversation history from a persisted session."""
    from pathlib import Path
    from factory.vendor.claw_code_agent.session_store import load_agent_session

    sessions_dir = Path(".port_sessions/agent")
    try:
        stored = load_agent_session(session_id, directory=sessions_dir)
        messages = []
        for msg in stored.messages:
            role = msg.get("role", "")
            content = msg.get("content", "") or ""
            if role in ("user", "assistant"):
                messages.append({"role": role, "content": str(content)})
        return JSONResponse(content={
            "session_id": stored.session_id,
            "messages": messages,
            "turns": stored.turns,
            "cost_usd": stored.total_cost_usd,
        })
    except Exception as exc:
        logger.warning("Failed to load session %s: %s", session_id, exc)
        return JSONResponse(content={"session_id": session_id, "messages": []})

@router.get("/agent/sessions", dependencies=[Depends(require_auth)])
async def list_sessions(request: Request):
    """List recent sessions."""
    from pathlib import Path
    import json

    sessions_dir = Path(".port_sessions/agent")
    sessions = []
    if sessions_dir.exists():
        for f in sorted(sessions_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)[:20]:
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                user_msgs = [m.get("content", "")[:80] for m in data.get("messages", []) if m.get("role") == "user"]
                sessions.append({
                    "session_id": data.get("session_id", f.stem),
                    "preview": user_msgs[0] if user_msgs else "",
                    "turns": data.get("turns", 0),
                    "cost_usd": data.get("total_cost_usd", 0),
                })
            except Exception as exc:
                logger.debug("Skipping corrupted session file %s: %s", f.name, exc)
    return JSONResponse(content={"sessions": sessions})


def _parse_intent(message: str) -> tuple[str, dict]:
    """Simple intent parser for agent chat."""
    msg = message.strip()

    m = re.search(r'(?:创建|新建)\s*(.+?)\s*(?:工作区|workshop)?\s*$', msg)
    if m:
        name = m.group(1).strip()
        return ("create_workshop", {"name": name})

    m = re.search(r'(?:删除|删掉)\s*(.+?)\s*(?:工作区|workshop)?\s*$', msg)
    if m:
        return ("delete_workshop", {"name": m.group(1).strip()})

    m = re.search(r'(?:在\s*)?(.+?)\s*(?:执行|运行|跑)\s*(.+?)(?:\s*工作流)?\s*$', msg)
    if m:
        return ("run_workflow", {"workshop": m.group(1).strip(), "task": m.group(2).strip()})

    if re.search(r'(?:查看|列出|所有)\s*(?:工作区|workshop)|工作区列表|有哪些工作区', msg):
        return ("list_workshops", {})

    if re.search(r'(?:查看|列出|所有)\s*(?:看板|kanban)|看板列表', msg):
        return ("list_kanban", {})

    if re.search(r'^(?:帮助|help|能做什么|功能|怎么用)', msg, re.IGNORECASE):
        return ("help", {})

    return ("unknown", {})

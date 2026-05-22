"""Agent run, chat, and interactive questioning endpoints."""

from __future__ import annotations

import asyncio
import json
import re

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

router = APIRouter(prefix="/api", tags=["agent"])


def _org(request: Request):
    return request.app.state.org


def _kanban_store(request: Request):
    return request.app.state.kanban_store


def _session_manager(request: Request):
    return request.app.state.session_manager


def _question_bridge(request: Request):
    return request.app.state.question_bridge


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.post("/agent/run")
async def agent_run(request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.runner import NexusAgentRunner
    from factory.memory import MemoryStore

    body = await request.json()
    task = body.get("task", "").strip()
    workshop_name = body.get("workshop", "")
    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)

    org = _org(request)
    mgr = WorkshopManager(org, _kanban_store(request))
    if workshop_name:
        ws = mgr.get(workshop_name)
        if ws is None:
            return JSONResponse(content={"detail": f"Workshop not found: {workshop_name}"}, status_code=404)
    else:
        if not org.workshops:
            return JSONResponse(content={"detail": "No workshops configured"}, status_code=404)
        ws = org.workshops[0]
        workshop_name = ws.name

    if not ws.spec.agents:
        return JSONResponse(content={"detail": "No agents in workshop"}, status_code=400)
    agent_spec = ws.spec.agents[0]
    store = MemoryStore(":memory:")

    runner = NexusAgentRunner(agent_spec, ws, store)
    runner.record_chat("system", f"任务开始: {task}", "gateway")

    try:
        result = await runner.run(task)
        if result.session_id:
            _session_manager(request).set(workshop_name, result.session_id)
        return JSONResponse(content={
            "reply": result.content[:5000],
            "tools_used": result.tools_used,
            "turns": result.turns,
            "cost_usd": result.cost_usd,
            "session_id": result.session_id,
            "error": result.error,
        })
    except Exception as exc:
        return JSONResponse(content={"reply": f"执行失败: {exc}", "error": str(exc)}, status_code=500)


@router.post("/agent/run/stream")
async def agent_run_stream(request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.runner import NexusAgentRunner
    from factory.memory import MemoryStore

    body = await request.json()
    task = body.get("task", "").strip()
    workshop_name = body.get("workshop", "")
    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)

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

    async def event_stream():
        yield _sse("status", {"event": "started", "task": task[:200], "workshop": workshop_name})
        try:
            result = await runner.run(task)
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
            })
            if result.error:
                yield _sse("error", {"message": result.error})
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
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


# ── Interactive Questioning ──


@router.get("/agent/question/{request_id}")
async def poll_question(request_id: str, request: Request):
    question = _question_bridge(request).get_question(request_id)
    return JSONResponse(content={
        "request_id": request_id,
        "has_question": bool(question),
        "question": question,
    })


@router.post("/agent/answer")
async def submit_answer(request: Request):
    body = await request.json()
    request_id = body.get("request_id", "")
    answer = body.get("answer", "")
    if not request_id:
        return JSONResponse(content={"detail": "request_id required"}, status_code=400)
    ok = _question_bridge(request).submit_answer(request_id, answer)
    return JSONResponse(content={"request_id": request_id, "accepted": ok})


# ── Agent Chat ──


@router.post("/agent/chat")
async def agent_chat(request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.workflow.engine import WorkflowRunner

    body = await request.json()
    message = body.get("message", "").strip()
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

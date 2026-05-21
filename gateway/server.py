"""FastAPI Gateway — REST + WebSocket API for the AI Factory platform.

Provides endpoints for workshop management, workflow execution,
kanban board management, and real-time WebSocket updates.
"""

from __future__ import annotations

import asyncio
from typing import Any

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse


class KanbanWSManager:
    """WebSocket connection manager with board-room based routing.

    Each board gets a "room". Clients subscribe to a board by connecting
    to /ws/boards/{board_id}. All clients on the same board receive updates
    when any kanban mutation occurs.
    """

    def __init__(self):
        self._rooms: dict[str, set[WebSocket]] = {}

    async def connect(self, board_id: str, ws: WebSocket) -> None:
        await ws.accept()
        if board_id not in self._rooms:
            self._rooms[board_id] = set()
        self._rooms[board_id].add(ws)

    def disconnect(self, board_id: str, ws: WebSocket) -> None:
        if board_id in self._rooms:
            self._rooms[board_id].discard(ws)
            if not self._rooms[board_id]:
                del self._rooms[board_id]

    async def broadcast(self, board_id: str, event: str, payload: Any) -> None:
        if board_id not in self._rooms:
            return
        import json

        message = json.dumps({"event": event, "data": payload})
        disconnected: list[WebSocket] = []
        for ws in self._rooms[board_id]:
            try:
                await ws.send_text(message)
            except Exception:
                disconnected.append(ws)
        for ws in disconnected:
            self.disconnect(board_id, ws)

    @property
    def rooms(self) -> dict[str, int]:
        return {bid: len(clients) for bid, clients in self._rooms.items()}


def create_app(org, kanban_store):
    """Factory function: create a FastAPI app wired to the given org and kanban store.

    Args:
        org: OrgEngine instance with .status(), .workshops, etc.
        kanban_store: KanbanStore instance for board/Card CRUD.
    """
    app = FastAPI(title="AI Factory Gateway", version="1.0.0")
    ws_manager = KanbanWSManager()

    from factory.settings import SettingsStore

    settings_store = SettingsStore()

    # Attach shared state to app for route access
    app.state.org = org
    app.state.kanban_store = kanban_store
    app.state.ws_manager = ws_manager
    app.state.settings_store = settings_store

    # --- CORS ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Health ---
    @app.get("/health")
    async def health():
        return {"status": "ok", "version": "1.0.0"}

    # --- Board CRUD ---

    @app.post("/api/boards")
    async def create_board(request: Request):
        body = await request.json()
        name = body.get("name", "Untitled Board")
        workshop_name = body.get("workshop_name", "")
        description = body.get("description", "")
        board = kanban_store.create_board(
            name=name, workshop_name=workshop_name, description=description,
        )
        return JSONResponse(
            content={
                "id": board.id, "name": board.name,
                "workshop_name": board.workshop_name,
                "description": board.description,
                "created_at": board.created_at,
                "updated_at": board.updated_at,
            },
            status_code=201,
        )

    @app.get("/api/boards")
    async def list_boards(request: Request):
        workshop_name = request.query_params.get("workshop_name", "")
        boards = kanban_store.list_boards(workshop_name)
        return JSONResponse(content=boards)

    @app.get("/api/boards/{board_id}")
    async def get_board(board_id: str):
        full = kanban_store.get_board_full(board_id)
        if not full:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content=full)

    @app.delete("/api/boards/{board_id}")
    async def delete_board(board_id: str):
        existing = kanban_store.get_board(board_id)
        if not existing:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        kanban_store.delete_board(board_id)
        return JSONResponse(content={"deleted": board_id})

    # --- List CRUD ---

    @app.post("/api/boards/{board_id}/lists")
    async def create_list(board_id: str, request: Request):
        existing = kanban_store.get_board(board_id)
        if not existing:
            return JSONResponse(content={"detail": "Board not found"}, status_code=404)
        body = await request.json()
        name = body.get("name", "Untitled List")
        position = body.get("position", -1)
        color = body.get("color", "")
        lst = kanban_store.create_list(board_id, name, position=position, color=color)
        await ws_manager.broadcast(board_id, "list_created", {"id": lst.id, "name": lst.name})
        return JSONResponse(
            content={"id": lst.id, "board_id": lst.board_id, "name": lst.name,
                      "position": lst.position, "color": lst.color},
            status_code=201,
        )

    @app.get("/api/boards/{board_id}/lists")
    async def get_lists(board_id: str):
        lists = kanban_store.get_lists(board_id)
        return JSONResponse(content=lists)

    @app.put("/api/lists/{list_id}/move")
    async def move_list(list_id: str, request: Request):
        existing = kanban_store.get_list(list_id)
        if not existing:
            return JSONResponse(content={"detail": "List not found"}, status_code=404)
        body = await request.json()
        new_position = body.get("position", 0)
        kanban_store.move_list(list_id, new_position)
        board_id = existing["board_id"]
        await ws_manager.broadcast(board_id, "list_moved", {"id": list_id, "position": new_position})
        return JSONResponse(content={"id": list_id, "position": new_position})

    @app.delete("/api/lists/{list_id}")
    async def delete_list(list_id: str):
        existing = kanban_store.get_list(list_id)
        if not existing:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        board_id = existing["board_id"]
        kanban_store.delete_list(list_id)
        await ws_manager.broadcast(board_id, "list_deleted", {"id": list_id})
        return JSONResponse(content={"deleted": list_id})

    # --- Card CRUD ---

    @app.post("/api/lists/{list_id}/cards")
    async def create_card(list_id: str, request: Request):
        existing = kanban_store.get_list(list_id)
        if not existing:
            return JSONResponse(content={"detail": "List not found"}, status_code=404)
        body = await request.json()
        card = kanban_store.create_card(
            list_id=list_id,
            title=body.get("title", ""),
            description=body.get("description", ""),
            position=body.get("position", -1),
            labels=body.get("labels"),
            assignee=body.get("assignee", ""),
            due_date=body.get("due_date"),
            source_agent=body.get("source_agent", ""),
            source_task_id=body.get("source_task_id", ""),
            task_status=body.get("task_status", "todo"),
        )
        board_id = existing["board_id"]
        payload = {
            "id": card.id, "list_id": card.list_id, "title": card.title,
            "description": card.description, "position": card.position,
            "labels": list(card.labels), "assignee": card.assignee,
            "due_date": card.due_date, "task_status": card.task_status,
            "source_agent": card.source_agent, "source_task_id": card.source_task_id,
            "created_at": card.created_at, "updated_at": card.updated_at,
        }
        await ws_manager.broadcast(board_id, "card_created", payload)
        return JSONResponse(content=payload, status_code=201)

    @app.get("/api/lists/{list_id}/cards")
    async def get_cards(list_id: str):
        cards = kanban_store.get_cards(list_id)
        return JSONResponse(content=cards)

    @app.get("/api/cards/{card_id}")
    async def get_card(card_id: str):
        card = kanban_store.get_card(card_id)
        if not card:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content=card)

    @app.put("/api/cards/{card_id}")
    async def update_card(card_id: str, request: Request):
        existing = kanban_store.get_card(card_id)
        if not existing:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        body = await request.json()
        kanban_store.update_card(card_id, **body)
        updated = kanban_store.get_card(card_id)
        # Determine board_id for WebSocket broadcast
        list_info = kanban_store.get_list(existing["list_id"])
        if list_info:
            await ws_manager.broadcast(list_info["board_id"], "card_updated", updated)
        return JSONResponse(content=updated)

    @app.put("/api/cards/{card_id}/move")
    async def move_card(card_id: str, request: Request):
        existing = kanban_store.get_card(card_id)
        if not existing:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        body = await request.json()
        target_list_id = body.get("list_id", "")
        position = body.get("position", -1)
        if not target_list_id:
            return JSONResponse(content={"detail": "list_id required"}, status_code=400)
        kanban_store.move_card(card_id, target_list_id, position=position)
        moved = kanban_store.get_card(card_id)
        list_info = kanban_store.get_list(target_list_id)
        if list_info:
            await ws_manager.broadcast(list_info["board_id"], "card_moved", moved)
        return JSONResponse(content=moved)

    @app.delete("/api/cards/{card_id}")
    async def delete_card(card_id: str):
        existing = kanban_store.get_card(card_id)
        if not existing:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        list_info = kanban_store.get_list(existing["list_id"])
        kanban_store.delete_card(card_id)
        if list_info:
            await ws_manager.broadcast(list_info["board_id"], "card_deleted", {"id": card_id})
        return JSONResponse(content={"deleted": card_id})

    # --- Agent Sync ---

    @app.get("/api/cards/agent/{agent_name}")
    async def get_cards_by_agent(agent_name: str):
        cards = kanban_store.get_cards_by_agent(agent_name)
        return JSONResponse(content=cards)

    @app.post("/api/cards/upsert-from-task")
    async def upsert_card_from_task(request: Request):
        body = await request.json()
        card = kanban_store.upsert_card_from_task(
            agent_name=body.get("agent_name", ""),
            task_id=body.get("task_id", ""),
            title=body.get("title", ""),
            status=body.get("task_status", "todo"),
            list_id=body.get("list_id", ""),
        )
        payload = {
            "id": card.id, "list_id": card.list_id, "title": card.title,
            "description": card.description, "position": card.position,
            "labels": list(card.labels), "assignee": card.assignee,
            "due_date": card.due_date, "task_status": card.task_status,
            "source_agent": card.source_agent, "source_task_id": card.source_task_id,
            "created_at": card.created_at, "updated_at": card.updated_at,
        }
        return JSONResponse(content=payload)

    # --- Org Status ---

    @app.get("/api/org/status")
    async def org_status():
        status = org.status()
        return JSONResponse(content=status)

    # --- Workshop CRUD ---

    @app.post("/api/workshops")
    async def create_workshop(request: Request):
        from factory.workshop.manager import WorkshopManager
        body = await request.json()
        name = body.get("name", "")
        if not name:
            return JSONResponse(content={"detail": "name is required"}, status_code=400)
        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.create(
            name=name,
            workspace=body.get("workspace", ""),
            agent_names=body.get("agent_names", ["super"]),
            workflow_name=body.get("workflow_name", "simple"),
            model=body.get("model", "anthropic/claude-sonnet-4-6"),
        )
        info = mgr.status(name)
        return JSONResponse(content=info or {}, status_code=201)

    @app.get("/api/workshops")
    async def list_workshops():
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        workshops = mgr.list_all()
        return JSONResponse(content=[{
            "name": w.name, "workspace": w.workspace,
            "agent_count": w.agent_count, "super_agents": w.super_agents,
            "workflow_name": w.workflow_name, "has_kanban": w.has_kanban,
        } for w in workshops])

    @app.get("/api/workshops/{name}")
    async def get_workshop(name: str):
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        status = mgr.status(name)
        if status is None:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content=status)

    @app.delete("/api/workshops/{name}")
    async def delete_workshop(name: str):
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        deleted = mgr.delete(name)
        if not deleted:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={"deleted": name})

    # --- Workflow Execution ---

    @app.post("/api/workshops/{name}/run")
    async def run_workflow(name: str, request: Request):
        from factory.workshop.manager import WorkshopManager
        from factory.workflow.engine import WorkflowRunner
        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.get(name)
        if ws is None:
            return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
        body = await request.json()
        workflow_name = body.get("workflow", "simple")
        task = body.get("task", "")
        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)
        tmpl = org.workflows.get(workflow_name)
        if tmpl is None:
            return JSONResponse(content={"detail": f"Unknown workflow: {workflow_name}"}, status_code=404)
        runner = WorkflowRunner(ws)
        result = await runner.run(tmpl, task)
        return JSONResponse(content={
            "status": result.status,
            "template_name": result.template_name,
            "stage_results": {
                sid: {"stage_id": sr.stage_id, "agent_name": sr.agent_name,
                       "status": sr.status, "output": sr.output[:500], "error": sr.error}
                for sid, sr in result.stage_results.items()
            },
            "final_output": result.final_output[:2000],
        })

    @app.get("/api/workflows")
    async def list_workflows():
        workflows = org.workflows.list_all()
        return JSONResponse(content=workflows)

    @app.get("/api/workflows/{name}")
    async def get_workflow(name: str):
        tmpl = org.workflows.get(name)
        if tmpl is None:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={
            "name": tmpl.name, "description": tmpl.description,
            "stages": tmpl.stages,
        })

    # --- Workshop Bridge ---

    @app.get("/api/workshops/{name}/products")
    async def list_workshop_products(name: str):
        from factory.workshop.bridge import WorkshopBridge
        bridge = WorkshopBridge(org.warehouse)
        products = bridge.list_peer_products(name)
        return JSONResponse(content={"workshop": name, "products": products})

    @app.get("/api/workshops/{name}/bridge/{peer}")
    async def get_peer_products(name: str, peer: str):
        from factory.workshop.bridge import WorkshopBridge
        bridge = WorkshopBridge(org.warehouse)
        products = bridge.list_peer_products(peer)
        return JSONResponse(content={"from": name, "peer": peer, "products": products})

    # --- Agent Chat ---

    @app.post("/api/agent/chat")
    async def agent_chat(request: Request):
        from factory.workshop.manager import WorkshopManager
        from factory.workflow.engine import WorkflowRunner

        body = await request.json()
        message = body.get("message", "").strip()
        if not message:
            return JSONResponse(content={"reply": "请输入消息。", "actions": []})

        mgr = WorkshopManager(org, kanban_store)

        # Parse intent and execute
        intent, params = _parse_intent(message)

        if intent == "create_workshop":
            name = params.get("name", "未命名车间")
            workflow = params.get("workflow", "simple")
            ws = mgr.create(name=name, workflow_name=workflow)
            status = mgr.status(name)
            agent_count = status.get("total_agents", 1) if status else 1
            board_id = status.get("kanban_board_id", "") if status else ""
            reply = (
                f"车间 **{name}** 已创建\n\n"
                f"- 工作流: `{workflow}`\n"
                f"- Agent: {agent_count} 个（含 super agent）\n"
                f"- 看板: {'已自动生成' if board_id else '创建失败'}\n"
                f"- 工作目录: `workspaces/{name}/`\n\n"
                f"现在可以对它说：**「在 {name} 执行 code-review」** 或 **「查看 {name} 的看板」**"
            )
            return JSONResponse(content={"reply": reply, "actions": [
                {"label": "查看车间", "href": "/workshops"},
                {"label": "查看看板", "href": "/kanban"},
            ]})

        elif intent == "delete_workshop":
            name = params.get("name", "")
            if not name:
                return JSONResponse(content={"reply": "请指定要删除的车间名称，比如「删除 测试车间」"})
            deleted = mgr.delete(name)
            if deleted:
                return JSONResponse(content={"reply": f"车间 **{name}** 已删除。"})
            else:
                return JSONResponse(content={"reply": f"车间 **{name}** 不存在。"})

        elif intent == "run_workflow":
            name = params.get("workshop", "")
            task = params.get("task", "")
            workflow = params.get("workflow", "simple")
            if not name or not task:
                return JSONResponse(content={"reply": "请指定车间和任务，比如「在 开发部 执行 code-review」"})
            ws = mgr.get(name)
            if ws is None:
                return JSONResponse(content={"reply": f"车间 **{name}** 不存在。先说「创建 {name} 车间」来新建一个。"})
            tmpl = org.workflows.get(workflow)
            if tmpl is None:
                return JSONResponse(content={"reply": f"工作流 **{workflow}** 不存在。可用: {', '.join(org.workflows.list_all())}"})
            runner = WorkflowRunner(ws)
            result = await runner.run(tmpl, task)
            stage_lines = []
            for sid, sr in result.stage_results.items():
                icon = "✓" if sr.status == "passed" else "✗"
                stage_lines.append(f"  {icon} **{sr.stage_id}** ({sr.agent_name}): {sr.output[:200]}")
            reply = f"工作流 **{workflow}** 在 **{name}** 执行完毕\n\n" + "\n".join(stage_lines)
            return JSONResponse(content={"reply": reply, "actions": [
                {"label": "查看看板", "href": "/kanban"},
                {"label": f"查看 {name}", "href": f"/workshops"},
            ]})

        elif intent == "list_workshops":
            workshops = mgr.list_all()
            if not workshops:
                return JSONResponse(content={"reply": "当前没有车间。对我说「创建一个 XX 车间」来开始。"})
            lines = ["当前车间：\n"]
            for w in workshops:
                kb = "已绑定看板" if w.has_kanban else "无看板"
                lines.append(f"- **{w.name}** — {w.agent_count} agents, 工作流 `{w.workflow_name}`, {kb}")
            return JSONResponse(content={"reply": "\n".join(lines), "actions": [
                {"label": "查看全部车间", "href": "/workshops"},
            ]})

        elif intent == "list_kanban":
            boards = kanban_store.list_boards()
            if not boards:
                return JSONResponse(content={"reply": "当前没有看板。创建车间时会自动生成看板。"})
            lines = ["当前看板：\n"]
            for b in boards:
                lists = kanban_store.get_lists(b["id"])
                total = sum(len(kanban_store.get_cards(lst["id"])) for lst in lists)
                lines.append(f"- **{b['name']}** — {len(lists)} 列表, {total} 卡片")
            return JSONResponse(content={"reply": "\n".join(lines), "actions": [
                {"label": "打开看板", "href": "/kanban"},
            ]})

        elif intent == "help":
            return JSONResponse(content={"reply": (
                "我是 AI 工厂助手，可以帮你：\n\n"
                "**车间管理**\n"
                "- 「创建 XXX 车间」— 新建车间，自动配 Agent + 看板\n"
                "- 「删除 XXX 车间」— 删除车间\n"
                "- 「查看所有车间」— 列出车间\n\n"
                "**工作流执行**\n"
                "- 「在 XXX 执行 code-review」— 运行工作流\n\n"
                "**看板**\n"
                "- 「查看看板」— 列出所有看板\n\n"
                "直接跟我说你想做什么就行。"
            )})

        else:
            # General chat / fallback
            reply = (
                f"收到：「{message}」\n\n"
                f"我可以帮你管理车间、运行工作流、查看看板。\n"
                f"试试对我说：**「创建一个开发车间」** 或 **「帮助」**"
            )
            return JSONResponse(content={"reply": reply})


    # --- Settings ---

    @app.get("/api/settings/providers")
    async def list_providers():
        return JSONResponse(content=settings_store.list_providers())

    @app.post("/api/settings/providers")
    async def save_provider(request: Request):
        body = await request.json()
        name = body.pop("name", "")
        if not name:
            return JSONResponse(content={"detail": "name is required"}, status_code=400)
        result = settings_store.save_provider(name, **body)
        return JSONResponse(content=result)

    @app.delete("/api/settings/providers/{name}")
    async def delete_provider(name: str):
        ok = settings_store.delete_provider(name)
        if not ok:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={"deleted": name})

    @app.get("/api/settings/skills")
    async def list_settings_skills():
        from factory.skills import SkillLoader

        loader = SkillLoader()
        skills = loader.list_skills()
        return JSONResponse(content=[
            {"name": s.name, "description": s.description, "version": s.version}
            for s in skills
        ])

    @app.post("/api/settings/skills/sync")
    async def sync_skills():
        from factory.skills import SkillLoader

        loader = SkillLoader()
        skills = loader.list_skills()
        return JSONResponse(content={
            "status": "ok",
            "count": len(skills),
            "skills": [{"name": s.name, "description": s.description} for s in skills],
        })

    @app.get("/api/settings/tools")
    async def list_settings_tools():
        from factory.mcp.registry import MCPRegistry

        from dataclasses import asdict

        registry = MCPRegistry()
        servers = [asdict(s) for s in registry.list_servers()]
        profiles = settings_store.list_tools()
        return JSONResponse(content={
            "mcp_servers": servers,
            "profiles": profiles,
        })

    @app.post("/api/settings/tools")
    async def save_tool(request: Request):
        body = await request.json()
        name = body.pop("name", "")
        if not name:
            return JSONResponse(content={"detail": "name is required"}, status_code=400)
        result = settings_store.save_tool(name, **body)
        return JSONResponse(content=result)

    @app.post("/api/settings/tools/sync")
    async def sync_tools():
        from factory.mcp.registry import MCPRegistry

        from dataclasses import asdict

        registry = MCPRegistry()
        servers = [asdict(s) for s in registry.list_servers()]
        return JSONResponse(content={"status": "ok", "count": len(servers), "servers": servers})

    @app.get("/api/settings/plugins")
    async def list_settings_plugins():
        from factory.channel.adapter import get_adapter, list_adapters as list_channel_names

        names = list_channel_names()
        stored = settings_store.list_plugins()
        result = {}
        for name in names:
            adapter = get_adapter(name)
            result[name] = {
                "name": name,
                "enabled": stored.get(name, {}).get("enabled", True),
                "healthy": adapter.health() if adapter else False,
            }
        for name, cfg in stored.items():
            if name not in result:
                result[name] = {"name": name, "enabled": cfg.get("enabled", False), "healthy": False}
        return JSONResponse(content=result)

    @app.post("/api/settings/plugins")
    async def save_plugin(request: Request):
        body = await request.json()
        name = body.pop("name", "")
        if not name:
            return JSONResponse(content={"detail": "name is required"}, status_code=400)
        result = settings_store.save_plugin(name, **body)
        return JSONResponse(content=result)

    @app.delete("/api/settings/plugins/{name}")
    async def delete_plugin(name: str):
        ok = settings_store.delete_plugin(name)
        if not ok:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={"deleted": name})

    # --- WebSocket ---

    @app.websocket("/ws/boards/{board_id}")
    async def ws_board(ws: WebSocket, board_id: str):
        await ws_manager.connect(board_id, ws)
        try:
            while True:
                data = await ws.receive_text()
                if data == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(board_id, ws)

    return app


def _parse_intent(message: str) -> tuple[str, dict]:
    """Simple intent parser for agent chat."""
    import re

    msg = message.strip()

    # Create workshop: "创建XXX车间", "新建XXX"
    m = re.search(r'(?:创建|新建)\s*(.+?)\s*(?:车间|workshop)?\s*$', msg)
    if m:
        name = m.group(1).strip()
        return ("create_workshop", {"name": name})

    # Delete workshop: "删除XXX", "删掉XXX"
    m = re.search(r'(?:删除|删掉)\s*(.+?)\s*(?:车间|workshop)?\s*$', msg)
    if m:
        return ("delete_workshop", {"name": m.group(1).strip()})

    # Run workflow: "在XXX执行/运行YYY", "XXX执行YYY"
    m = re.search(r'(?:在\s*)?(.+?)\s*(?:执行|运行|跑)\s*(.+?)(?:\s*工作流)?\s*$', msg)
    if m:
        return ("run_workflow", {"workshop": m.group(1).strip(), "task": m.group(2).strip()})

    # List workshops: "查看车间", "列出车间", "所有车间", "车间列表"
    if re.search(r'(?:查看|列出|所有)\s*(?:车间|workshop)|车间列表|有哪些车间', msg):
        return ("list_workshops", {})

    # List kanban: "查看看板", "看板列表", "所有看板"
    if re.search(r'(?:查看|列出|所有)\s*(?:看板|kanban)|看板列表', msg):
        return ("list_kanban", {})

    # Help: "帮助", "help", "能做什么", "功能"
    if re.search(r'^(?:帮助|help|能做什么|功能|怎么用)', msg, re.IGNORECASE):
        return ("help", {})

    return ("unknown", {})


async def serve(app: FastAPI, host: str = "127.0.0.1", port: int = 8600) -> None:
    """Run the FastAPI app with uvicorn programmatically."""
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

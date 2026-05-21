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
    app = FastAPI(title="AI Factory Gateway", version="0.7.0")
    ws_manager = KanbanWSManager()

    # Attach shared state to app for route access
    app.state.org = org
    app.state.kanban_store = kanban_store
    app.state.ws_manager = ws_manager

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
        return {"status": "ok", "version": "0.7.0"}

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

    # --- WebSocket ---

    @app.websocket("/ws/boards/{board_id}")
    async def ws_board(ws: WebSocket, board_id: str):
        await ws_manager.connect(board_id, ws)
        try:
            while True:
                data = await ws.receive_text()
                # Client can send ping messages; echo back
                if data == "ping":
                    await ws.send_text("pong")
        except WebSocketDisconnect:
            ws_manager.disconnect(board_id, ws)

    return app

"""FastAPI Gateway — REST + WebSocket + SSE API for the Nexus AI Works platform.

Provides endpoints for workshop management, workflow execution,
kanban board management, real-time WebSocket updates, and
SSE streaming for agent execution.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

from fastapi import Body, FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse


class AgentSessionManager:
    """Tracks workshop → last_session_id for session resume."""

    def __init__(self):
        self._sessions: dict[str, str] = {}

    def get(self, workshop_name: str) -> str:
        return self._sessions.get(workshop_name, "")

    def set(self, workshop_name: str, session_id: str) -> None:
        self._sessions[workshop_name] = session_id

    def clear(self, workshop_name: str) -> None:
        self._sessions.pop(workshop_name, None)


class QuestionBridge:
    """Bridges interactive questions from Agent to SSE/Frontend.

    When the agent calls ask_user_question, the question is stored here.
    The frontend polls or listens via SSE for pending questions.
    """

    def __init__(self):
        self._pending: dict[str, str] = {}  # request_id → question text
        self._answers: dict[str, str] = {}  # request_id → answer text
        self._events: dict[str, asyncio.Event] = {}

    def set_question(self, request_id: str, question: str) -> None:
        self._pending[request_id] = question
        self._answers.pop(request_id, None)

    def get_question(self, request_id: str) -> str:
        return self._pending.get(request_id, "")

    def submit_answer(self, request_id: str, answer: str) -> bool:
        if request_id not in self._pending:
            return False
        self._answers[request_id] = answer
        self._pending.pop(request_id, None)
        event = self._events.pop(request_id, None)
        if event:
            event.set()
        return True

    async def wait_answer(self, request_id: str, timeout: float = 300.0) -> str:
        event = asyncio.Event()
        self._events[request_id] = event
        try:
            await asyncio.wait_for(event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            return "[TIMEOUT]"
        return self._answers.get(request_id, "[NO_ANSWER]")


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
    app = FastAPI(title="Nexus AI Works Gateway", version="1.0.0")
    ws_manager = KanbanWSManager()
    session_manager = AgentSessionManager()
    question_bridge = QuestionBridge()

    from factory.settings import SettingsStore

    settings_store = SettingsStore()

    from factory.workflow.chain import ChainStore

    chain_store = ChainStore()

    # Attach shared state to app for route access
    app.state.org = org
    app.state.kanban_store = kanban_store
    app.state.ws_manager = ws_manager
    app.state.session_manager = session_manager
    app.state.question_bridge = question_bridge
    app.state.settings_store = settings_store
    app.state.chain_store = chain_store

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
            agent_names=body.get("agent_names", []),
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
            "agent_count": w.agent_count, "agent_names": w.agent_names,
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

    # --- Workshop Export/Import ---

    @app.post("/api/workshops/{name}/export")
    async def export_workshop_api(name: str):
        """Export a workspace as a downloadable .nexus package (zip)."""
        from factory.workshop.manager import WorkshopManager
        import tempfile, zipfile, io

        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.get(name)
        if ws is None:
            return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)

        with tempfile.TemporaryDirectory() as tmpdir:
            pkg_dir = mgr.export_workspace(name, output_dir=tmpdir)
            if pkg_dir is None:
                return JSONResponse(content={"detail": "Export failed"}, status_code=500)

            buf = io.BytesIO()
            with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
                pkg_path = Path(pkg_dir)
                for f in pkg_path.rglob("*"):
                    if f.is_file():
                        zf.write(f, f.relative_to(pkg_path))
            buf.seek(0)

            return StreamingResponse(
                buf,
                media_type="application/zip",
                headers={"Content-Disposition": f'attachment; filename="{name}.nexus.zip"'},
            )

    @app.post("/api/workshops/import")
    async def import_workspace_api(request: Request):
        """Import a .nexus package (upload zip or directory)."""
        from factory.workshop.manager import WorkshopManager
        import tempfile, zipfile, shutil

        content_type = request.headers.get("content-type", "")
        if "multipart/form-data" in content_type:
            form = await request.form()
            file = form.get("file")
            if file is None:
                return JSONResponse(content={"detail": "No file uploaded"}, status_code=400)

            custom_name_raw = form.get("name")
            custom_name = str(custom_name_raw).strip() if custom_name_raw else ""

            with tempfile.TemporaryDirectory() as tmpdir:
                if hasattr(file, "filename") and file.filename:
                    fname = getattr(file, "filename", "upload")
                else:
                    fname = "upload.nexus"
                filepath = Path(tmpdir) / fname
                content = await file.read()
                filepath.write_bytes(content)

                # If it's a zip, extract it
                pkg_dir = Path(tmpdir) / "package"
                if fname.endswith(".zip") or zipfile.is_zipfile(filepath):
                    with zipfile.ZipFile(filepath, "r") as zf:
                        zf.extractall(pkg_dir)
                else:
                    pkg_dir = filepath

                mgr = WorkshopManager(org, kanban_store)
                result = mgr.import_package(str(pkg_dir), custom_name=custom_name)
                if result is None:
                    return JSONResponse(
                        content={"detail": "Import failed (workspace may already exist)"},
                        status_code=409,
                    )
                return JSONResponse(content=result, status_code=201)

        return JSONResponse(content={"detail": "Expected multipart/form-data"}, status_code=400)

    # --- Workshop Agent CRUD ---

    @app.get("/api/workshops/{name}/agents")
    async def list_workshop_agents(name: str):
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        agents = mgr.list_agents(name)
        if agents is None:
            return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
        return JSONResponse(content=agents)

    @app.post("/api/workshops/{name}/agents")
    async def create_workshop_agent(name: str, body: dict = Body(...)):
        from factory.workshop.manager import WorkshopManager
        from config.schema import AgentSpec, AgentPermissions, FilesystemPermission, ShellPermission, SubagentPermission, WarehousePermission, SelfPermission

        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.get(name)
        if ws is None:
            return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)

        agent_name = body.get("name", "").strip()
        if not agent_name:
            return JSONResponse(content={"detail": "Agent name is required"}, status_code=400)

        if agent_name in ws.agents:
            return JSONResponse(content={"detail": f"Agent '{agent_name}' already exists"}, status_code=409)

        mode = body.get("mode", "super")
        perm = body.get("permissions", {})

        spec = AgentSpec(
            name=agent_name,
            mode=mode,
            model=body.get("model", "anthropic/claude-sonnet-4-6"),
            tools=body.get("tools", []),
            system_prompt=body.get("system_prompt", ""),
            guide_file=body.get("guide_file", ""),
            skills=body.get("skills", []),
            permissions=AgentPermissions(
                filesystem=FilesystemPermission(
                    write=["workspace"] if perm.get("file_write", mode == "super") else [],
                ),
                shell=ShellPermission(exec=perm.get("shell_exec", mode == "super")),
                subagent=SubagentPermission(
                    spawn=perm.get("subagent_spawn", mode == "super"),
                    max=5 if perm.get("subagent_spawn", mode == "super") else 0,
                ),
            ),
        )
        result = mgr.add_agent(name, spec)
        if result is None:
            return JSONResponse(content={"detail": "Failed to add agent"}, status_code=500)

        # Write guide file content
        guide_content = body.get("guide_content", "")
        guide_file = body.get("guide_file", "")
        if guide_content and guide_file:
            import os
            filepath = os.path.join(str(ws.workspace), guide_file)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(guide_content)

        return JSONResponse(content=mgr.list_agents(name)[-1] if mgr.list_agents(name) else {}, status_code=201)

    @app.put("/api/workshops/{name}/agents/{agent_name}")
    async def update_workshop_agent(name: str, agent_name: str, body: dict = Body(...)):
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)

        # Write guide file content
        guide_content = body.pop("guide_content", "")
        guide_file = body.get("guide_file", "")
        if guide_content and guide_file:
            ws = mgr.get(name)
            if ws:
                import os
                filepath = os.path.join(str(ws.workspace), guide_file)
                os.makedirs(os.path.dirname(filepath), exist_ok=True)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(guide_content)

        result = mgr.update_agent(name, agent_name, body)
        if result is None:
            return JSONResponse(content={"detail": "Agent or workshop not found"}, status_code=404)
        agents = mgr.list_agents(name)
        updated = next((a for a in agents if a["name"] == agent_name), {}) if agents else {}
        return JSONResponse(content=updated)

    @app.delete("/api/workshops/{name}/agents/{agent_name}")
    async def delete_workshop_agent(name: str, agent_name: str):
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        deleted = mgr.remove_agent(name, agent_name)
        if not deleted:
            return JSONResponse(content={"detail": "Agent or workshop not found"}, status_code=404)
        return JSONResponse(content={"deleted": agent_name})

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
        workflow_name = body.get("workflow", "")
        task = body.get("task", "")
        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)
        tmpl = org.workflow_store.load(workflow_name) if workflow_name else None
        if tmpl is None:
            return JSONResponse(content={"detail": f"Unknown workflow: {workflow_name}"}, status_code=404)
        runner = WorkflowRunner(ws)
        result = await runner.run(tmpl, task)
        return JSONResponse(content={
            "status": result.status.value,
            "template_name": result.template_name,
            "node_results": {
                nid: {"node_id": nr.node_id, "agent_name": nr.agent_name,
                       "status": nr.status.value, "output": nr.output[:500], "error": nr.error}
                for nid, nr in result.node_results.items()
            },
            "final_output": result.final_output[:2000],
        })

    @app.get("/api/workflows")
    async def list_workflows():
        return JSONResponse(content=org.workflow_store.list_all())

    @app.get("/api/workflows/{name}")
    async def get_workflow(name: str):
        tmpl = org.workflow_store.load(name)
        if tmpl is None:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content=tmpl.to_dict())

    @app.post("/api/workflows")
    async def save_workflow(body: dict = Body(...)):
        from factory.workflow.models import WorkflowNode
        nodes = [WorkflowNode.from_dict(n) for n in body.get("nodes", [])]
        from factory.workflow.models import WorkflowTemplate
        tmpl = WorkflowTemplate(
            name=body["name"], description=body.get("description", ""),
            workspace=body.get("workspace", ""), nodes=nodes,
        )
        path = org.workflow_store.save(tmpl)
        return JSONResponse(content={"saved": str(path), **tmpl.to_dict()})

    @app.delete("/api/workflows/{name}")
    async def delete_workflow(name: str):
        deleted = org.workflow_store.delete(name)
        if not deleted:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={"deleted": name})

    @app.post("/api/workflows/{name}/execute")
    async def execute_workflow_stream(name: str, request: Request):
        """Execute a workflow with SSE streaming of per-node status."""
        from factory.workshop.manager import WorkshopManager
        from factory.workflow.engine import WorkflowRunner

        body = await request.json()
        task = body.get("task", "").strip()
        workshop_name = body.get("workshop", "")

        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)

        tmpl = org.workflow_store.load(name)
        if tmpl is None:
            return JSONResponse(content={"detail": f"Workflow not found: {name}"}, status_code=404)

        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.get(workshop_name) if workshop_name else None
        if ws is None:
            return JSONResponse(content={"detail": f"Workshop not found: {workshop_name}"}, status_code=404)

        queue: asyncio.Queue = asyncio.Queue()

        async def on_status(node_id: str, status: str, detail: str) -> None:
            await queue.put(("node_status", {"node_id": node_id, "status": status, "detail": detail[:500]}))

        runner = WorkflowRunner(ws, store=org.workflow_store, on_status=on_status)

        async def event_stream():
            yield _sse("started", {"template": name, "task": task[:200], "workshop": workshop_name})

            run_task = asyncio.ensure_future(runner.run(tmpl, task))

            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield _sse(event, data)
                except asyncio.TimeoutError:
                    if run_task.done():
                        break

            try:
                result = run_task.result()
                yield _sse("completed", {
                    "status": result.status.value,
                    "template_name": result.template_name,
                    "node_results": {
                        nid: {
                            "node_id": nr.node_id, "agent_name": nr.agent_name,
                            "status": nr.status.value, "output": nr.output[:500], "error": nr.error,
                        }
                        for nid, nr in result.node_results.items()
                    },
                    "final_output": result.final_output[:3000],
                })
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

    # --- Cross-Workshop Chain ---

    @app.get("/api/chains")
    async def list_chains():
        return JSONResponse(content=chain_store.list_all())

    @app.get("/api/chains/{name}")
    async def get_chain(name: str):
        chain = chain_store.load(name)
        if chain is None:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content=chain.to_dict())

    @app.post("/api/chains")
    async def save_chain(body: dict = Body(...)):
        from factory.workflow.chain import Chain, ChainStep

        steps = [ChainStep.from_dict(s) for s in body.get("steps", [])]
        chain = Chain(
            name=body["name"],
            description=body.get("description", ""),
            steps=steps,
        )
        path = chain_store.save(chain)
        return JSONResponse(content={"saved": str(path), **chain.to_dict()})

    @app.delete("/api/chains/{name}")
    async def delete_chain(name: str):
        deleted = chain_store.delete(name)
        if not deleted:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={"deleted": name})

    @app.post("/api/chains/{name}/execute")
    async def execute_chain_stream(name: str, request: Request):
        """Execute a cross-workshop chain with SSE streaming."""
        from factory.workflow.chain import ChainRunner

        chain = chain_store.load(name)
        if chain is None:
            return JSONResponse(content={"detail": f"Chain not found: {name}"}, status_code=404)

        body = await request.json()
        task = body.get("task", "").strip()
        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)

        queue: asyncio.Queue = asyncio.Queue()

        async def on_status(event: str, target: str, detail: str) -> None:
            await queue.put((event, {"target": target, "detail": detail[:500]}))

        runner = ChainRunner(org, kanban_store, on_status=on_status)

        async def event_stream():
            yield _sse("started", {"chain": name, "task": task[:200],
                                    "steps": [s.workshop for s in chain.steps]})

            run_task = asyncio.ensure_future(runner.run(chain, task))

            while True:
                try:
                    event, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                    yield _sse(event, data)
                except asyncio.TimeoutError:
                    if run_task.done():
                        break

            try:
                result = run_task.result()
                yield _sse("completed", {
                    "status": result.status,
                    "chain_name": result.chain_name,
                    "step_results": result.step_results,
                    "final_output": result.final_output[:3000],
                })
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

    # --- Workshop Bridge ---

    @app.get("/api/workshops/{name}/files/{filename:path}")
    async def read_workshop_file(name: str, filename: str):
        """Read a file from a workshop's workspace directory."""
        from factory.workshop.manager import WorkshopManager
        mgr = WorkshopManager(org, kanban_store)
        ws = mgr.get(name)
        if ws is None:
            return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
        import os
        filepath = os.path.join(str(ws.workspace), filename)
        if not os.path.isfile(filepath):
            return JSONResponse(content={"detail": "File not found"}, status_code=404)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        return JSONResponse(content={"filename": filename, "content": content})

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
                {"label": f"查看 {name}", "href": f"/workshops"},
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
            boards = kanban_store.list_boards()
            if not boards:
                return JSONResponse(content={"reply": "当前没有看板。创建工作区时会自动生成看板。"})
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
            # General chat / fallback
            reply = (
                f"收到：「{message}」\n\n"
                f"我可以帮你管理工作区、运行工作流、查看看板。\n"
                f"试试对我说：**「创建一个开发工作区」** 或 **「帮助」**"
            )
            return JSONResponse(content={"reply": reply})


    # --- Agent Run (claw-code-agent backed) ---

    @app.post("/api/agent/run")
    async def agent_run(request: Request):
        """Execute agent through the claw-code-agent loop (non-streaming)."""
        from factory.workshop.manager import WorkshopManager
        from factory.runner import NexusAgentRunner
        from factory.memory import MemoryStore

        body = await request.json()
        task = body.get("task", "").strip()
        workshop_name = body.get("workshop", "")
        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)

        mgr = WorkshopManager(org, kanban_store)
        if workshop_name:
            ws = mgr.get(workshop_name)
            if ws is None:
                return JSONResponse(content={"detail": f"Workshop not found: {workshop_name}"}, status_code=404)
        else:
            # Default to first workshop
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
            sid = session_manager.get(workshop_name)
            result = await runner.run(task)
            if result.session_id:
                session_manager.set(workshop_name, result.session_id)
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

    @app.post("/api/agent/run/stream")
    async def agent_run_stream(request: Request):
        """Execute agent with SSE streaming of tool calls and status."""
        from factory.workshop.manager import WorkshopManager
        from factory.runner import NexusAgentRunner
        from factory.memory import MemoryStore

        body = await request.json()
        task = body.get("task", "").strip()
        workshop_name = body.get("workshop", "")
        if not task:
            return JSONResponse(content={"detail": "task is required"}, status_code=400)

        mgr = WorkshopManager(org, kanban_store)
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
                    session_manager.set(workshop_name, result.session_id)

                # Stream per-event deltas for real-time text rendering
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

    # --- Interactive Questioning ---

    @app.get("/api/agent/question/{request_id}")
    async def poll_question(request_id: str):
        """Poll for a pending interactive question from the agent."""
        question = question_bridge.get_question(request_id)
        return JSONResponse(content={
            "request_id": request_id,
            "has_question": bool(question),
            "question": question,
        })

    @app.post("/api/agent/answer")
    async def submit_answer(request: Request):
        """Submit an answer to an interactive agent question."""
        body = await request.json()
        request_id = body.get("request_id", "")
        answer = body.get("answer", "")
        if not request_id:
            return JSONResponse(content={"detail": "request_id required"}, status_code=400)
        ok = question_bridge.submit_answer(request_id, answer)
        return JSONResponse(content={
            "request_id": request_id,
            "accepted": ok,
        })


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
        from factory.skills.marketplace import SkillMarketplace

        mp = SkillMarketplace()
        mp.discover()
        return JSONResponse(content=[
            {"name": s.name, "full_name": s.full_name, "description": s.description,
             "plugin": s.plugin, "source": s.source, "file_path": s.file_path}
            for s in mp.list_all()
        ])

    @app.post("/api/settings/skills/sync")
    async def sync_skills():
        from factory.skills.marketplace import SkillMarketplace

        mp = SkillMarketplace()
        count = mp.discover()
        return JSONResponse(content={
            "status": "ok", "count": count,
            "skills": [
                {"name": s.name, "full_name": s.full_name, "description": s.description,
                 "plugin": s.plugin, "source": s.source}
                for s in mp.list_all()
            ],
        })

    @app.get("/api/settings/skills/{name}")
    async def get_skill_detail(name: str):
        from factory.skills.marketplace import SkillMarketplace

        mp = SkillMarketplace()
        mp.discover()
        skill = mp.get(name)
        if skill is None:
            return JSONResponse(content={"detail": "Not found"}, status_code=404)
        return JSONResponse(content={
            "name": skill.name, "full_name": skill.full_name,
            "description": skill.description, "plugin": skill.plugin,
            "source": skill.source, "file_path": skill.file_path,
            "body": skill.get_body()[:5000],
        })

    @app.get("/api/settings/tools")
    async def list_settings_tools():
        from factory.mcp.registry import MCPRegistry
        from dataclasses import asdict

        registry = MCPRegistry()
        servers = []
        for s in registry.list_servers():
            servers.append({"name": s.name, "description": s.description, "category": s.category, "transport": s.transport})
        for entry in registry.list_marketplace():
            servers.append({
                "name": entry.name, "description": entry.description,
                "category": entry.category, "install_command": entry.install_command,
            })
        return JSONResponse(content=servers)

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
        servers = []
        for s in registry.list_servers():
            servers.append({"name": s.name, "description": s.description, "category": s.category})
        for entry in registry.list_marketplace():
            servers.append({
                "name": entry.name, "description": entry.description,
                "category": entry.category, "install_command": entry.install_command,
            })
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

    # --- Search ---

    @app.get("/api/settings/search")
    async def get_search_config():
        return JSONResponse(content=settings_store.get_search())

    @app.post("/api/settings/search")
    async def save_search_config(body: dict = Body(...)):
        allowed = {"tavily_api_key", "brave_api_key", "searxng_base_url",
                    "active_provider", "deep_search_enabled", "max_results"}
        fields = {k: v for k, v in body.items() if k in allowed}
        result = settings_store.save_search(**fields)
        return JSONResponse(content=result)

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

    # Create workshop: "创建XXX工作区", "新建XXX"
    m = re.search(r'(?:创建|新建)\s*(.+?)\s*(?:工作区|workshop)?\s*$', msg)
    if m:
        name = m.group(1).strip()
        return ("create_workshop", {"name": name})

    # Delete workshop: "删除XXX", "删掉XXX"
    m = re.search(r'(?:删除|删掉)\s*(.+?)\s*(?:工作区|workshop)?\s*$', msg)
    if m:
        return ("delete_workshop", {"name": m.group(1).strip()})

    # Run workflow: "在XXX执行/运行YYY", "XXX执行YYY"
    m = re.search(r'(?:在\s*)?(.+?)\s*(?:执行|运行|跑)\s*(.+?)(?:\s*工作流)?\s*$', msg)
    if m:
        return ("run_workflow", {"workshop": m.group(1).strip(), "task": m.group(2).strip()})

    # List workshops: "查看工作区", "列出工作区", "所有工作区", "工作区列表"
    if re.search(r'(?:查看|列出|所有)\s*(?:工作区|workshop)|工作区列表|有哪些工作区', msg):
        return ("list_workshops", {})

    # List kanban: "查看看板", "看板列表", "所有看板"
    if re.search(r'(?:查看|列出|所有)\s*(?:看板|kanban)|看板列表', msg):
        return ("list_kanban", {})

    # Help: "帮助", "help", "能做什么", "功能"
    if re.search(r'^(?:帮助|help|能做什么|功能|怎么用)', msg, re.IGNORECASE):
        return ("help", {})

    return ("unknown", {})


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def serve(app: FastAPI, host: str = "127.0.0.1", port: int = 8600) -> None:
    """Run the FastAPI app with uvicorn programmatically."""
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

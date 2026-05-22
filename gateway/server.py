"""FastAPI Gateway — REST + WebSocket + SSE API for the Nexus AI Works platform.

Provides endpoints for workshop management, workflow execution,
kanban board management, real-time WebSocket updates, and
SSE streaming for agent execution.
"""

from __future__ import annotations

import asyncio
import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from slowapi.middleware import SlowAPIMiddleware

from gateway.csrf import CSRFTokenMiddleware
from gateway.rate_limit import limiter

# ── Route modules ──
from gateway.routes.health import router as health_router
from gateway.routes.boards import router as boards_router
from gateway.routes.workshops import router as workshops_router
from gateway.routes.workflows import router as workflows_router
from gateway.routes.chains import router as chains_router
from gateway.routes.agent import router as agent_router
from gateway.routes.settings import router as settings_router
from gateway.routes.ws import router as ws_router
from gateway.routes.library import router as library_router
from gateway.routes.market import router as market_router


# ── Core helpers (kept in server.py for closure-free access) ──


class AgentSessionManager:
    """Tracks workshop -> last_session_id for session resume."""

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
        self._pending: dict[str, str] = {}
        self._answers: dict[str, str] = {}
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
        self._rooms: dict[str, set] = {}

    async def connect(self, board_id: str, ws) -> None:
        await ws.accept()
        if board_id not in self._rooms:
            self._rooms[board_id] = set()
        self._rooms[board_id].add(ws)

    def disconnect(self, board_id: str, ws) -> None:
        if board_id in self._rooms:
            self._rooms[board_id].discard(ws)
            if not self._rooms[board_id]:
                del self._rooms[board_id]

    async def broadcast(self, board_id: str, event: str, payload) -> None:
        if board_id not in self._rooms:
            return
        import json

        message = json.dumps({"event": event, "data": payload})
        disconnected = []
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


# ── App factory ──


def create_app(org, kanban_store):
    """Factory function: create a FastAPI app wired to the given org and kanban store.

    Args:
        org: OrgEngine instance with .status(), .workshops, etc.
        kanban_store: KanbanStore instance for board/Card CRUD.
    """
    app = FastAPI(title="Nexus AI Works Gateway", version="1.0.0")
    app.state.limiter = limiter

    ws_manager = KanbanWSManager()
    session_manager = AgentSessionManager()
    question_bridge = QuestionBridge()

    from factory.settings import SettingsStore
    from factory.workflow.chain import ChainStore

    settings_store = SettingsStore()
    chain_store = ChainStore()

    app.state.org = org
    app.state.kanban_store = kanban_store
    app.state.ws_manager = ws_manager
    app.state.session_manager = session_manager
    app.state.question_bridge = question_bridge
    app.state.settings_store = settings_store
    app.state.chain_store = chain_store

    # --- CORS ---
    cors_origins = os.environ.get(
        "CORS_ORIGINS",
        "http://localhost:5173,http://localhost:8600,http://127.0.0.1:5173,http://127.0.0.1:8600",
    ).split(",")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- CSRF ---
    app.add_middleware(
        CSRFTokenMiddleware,
        skip_paths=(
            "/api/csrf-token",
            "/api/agent/run/stream",
            "/api/workflows/",
            "/api/chains/",
            "/ws/",
            "/health",
            "/api/market/",
        ),
    )

    # --- Rate limiting ---
    app.add_middleware(SlowAPIMiddleware)

    # --- Route registration ---
    app.include_router(health_router)
    app.include_router(boards_router)
    app.include_router(workshops_router)
    app.include_router(workflows_router)
    app.include_router(chains_router)
    app.include_router(agent_router)
    app.include_router(settings_router)
    app.include_router(ws_router)
    app.include_router(library_router)
    app.include_router(market_router)

    return app


# ── Server entrypoint ──


async def serve(app: FastAPI, host: str = "127.0.0.1", port: int = 8600) -> None:
    """Run the FastAPI app with uvicorn programmatically."""
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)
    await server.serve()

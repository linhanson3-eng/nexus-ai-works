from __future__ import annotations

"""FastAPI Gateway — REST + WebSocket + SSE API for the Nexus AI Works platform.

Provides endpoints for workshop management, workflow execution,
kanban board management, real-time WebSocket updates, and
SSE streaming for agent execution.
"""


import logging
import os
import signal
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from slowapi.middleware import SlowAPIMiddleware

from gateway.csrf import CSRFTokenMiddleware
from gateway.rate_limit import limiter

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    datefmt="%Y-%m-%dT%H:%M:%S",
)
logger = logging.getLogger(__name__)

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
from gateway.routes.schedules import router as schedules_router
from factory.scheduler.engine import ScheduleEngine


# ── Graceful shutdown state ────────────────────────────────────


class _ShutdownState:
    """Track shutdown state for graceful termination."""

    def __init__(self):
        self._shutting_down = False
        self._active_requests: set[str] = set()

    @property
    def is_shutting_down(self) -> bool:
        return self._shutting_down

    def signal_shutdown(self) -> None:
        self._shutting_down = True

    def enter_request(self, request_id: str) -> None:
        self._active_requests.add(request_id)

    def exit_request(self, request_id: str) -> None:
        self._active_requests.discard(request_id)

    @property
    def pending_count(self) -> int:
        return len(self._active_requests)


shutdown_state = _ShutdownState()


# ── Lifespan ───────────────────────────────────────────────────


@asynccontextmanager
async def _app_lifespan(app: FastAPI):
    """Startup / shutdown lifecycle for the FastAPI app."""
    logger.info("Gateway starting up")
    schedule_engine = app.state.schedule_engine
    schedule_engine.start()
    logger.info("ScheduleEngine started")

    yield

    logger.info("Gateway shutting down — draining %d active requests", shutdown_state.pending_count)
    schedule_engine.stop()
    shutdown_state.signal_shutdown()
    # Give in-flight requests a brief window to complete
    import asyncio
    deadline = asyncio.get_event_loop().time() + 5.0
    while shutdown_state.pending_count > 0 and asyncio.get_event_loop().time() < deadline:
        await asyncio.sleep(0.25)
    if shutdown_state.pending_count > 0:
        logger.warning("Gateway shutdown with %d requests still in-flight", shutdown_state.pending_count)
    else:
        logger.info("Gateway shutdown complete — all requests drained")


# ── Request tracing middleware ──────────────────────────────────


class RequestTracingMiddleware(BaseHTTPMiddleware):
    """Inject X-Request-ID into every request and log start/end with timing."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        request.state.start_time = datetime.now(timezone.utc)

        shutdown_state.enter_request(request_id)
        try:
            response = await call_next(request)
            response.headers["X-Request-ID"] = request_id
            return response
        finally:
            shutdown_state.exit_request(request_id)
            elapsed_ms = (datetime.now(timezone.utc) - request.state.start_time).total_seconds() * 1000
            status = getattr(response, "status_code", 0) if "response" in dir() else 0
            logger.info(
                "%s %s → %s [%s] %.0fms",
                request.method,
                request.url.path,
                status,
                request_id[:8],
                elapsed_ms,
            )


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


def create_app(org: "OrgEngine", kanban_store: "KanbanStore") -> FastAPI:
    """Factory function: create a FastAPI app wired to the given org and kanban store.

    Args:
        org: OrgEngine instance with .status(), .workshops, etc.
        kanban_store: KanbanStore instance for board/Card CRUD.
    """
    app = FastAPI(title="Nexus AI Works Gateway", version="1.0.0", lifespan=_app_lifespan)
    app.state.limiter = limiter
    app.state.shutdown = shutdown_state

    ws_manager = KanbanWSManager()
    session_manager = AgentSessionManager()

    from factory.settings import SettingsStore
    from factory.workflow.chain import ChainStore

    settings_store = SettingsStore()
    chain_store = ChainStore()
    schedule_engine = ScheduleEngine()

    app.state.org = org
    app.state.kanban_store = kanban_store
    app.state.ws_manager = ws_manager

    # Seed demo kanban on first launch (idempotent)
    try:
        kanban_store.seed_demo_board()
    except Exception:
        pass  # non-critical
    app.state.session_manager = session_manager
    app.state.settings_store = settings_store
    app.state.chain_store = chain_store
    app.state.schedule_engine = schedule_engine

    # --- Request tracing (outermost — wraps all other middleware) ---
    app.add_middleware(RequestTracingMiddleware)

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
    # Only skip CSRF for endpoints that are inherently safe:
    # - GET-only read paths (no state mutation)
    # - SSE streaming (uses its own auth)
    # - WebSocket upgrade (validated in ws handler)
    # - Health checks (no auth needed)
    app.add_middleware(
        CSRFTokenMiddleware,
        skip_paths=(
            "/api/csrf-token",
            "/api/agent/run/stream",
            "/ws/",
            "/health",
            "/api/market/health",
        ),
    )

    # --- Max body size (10 MB) ---
    class MaxBodySizeMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            if request.method in ("POST", "PUT", "PATCH"):
                content_length = request.headers.get("content-length")
                if content_length and int(content_length) > 10 * 1024 * 1024:
                    from fastapi.responses import JSONResponse
                    return JSONResponse(
                        content={"detail": "Request body too large"},
                        status_code=413,
                    )
            return await call_next(request)

    app.add_middleware(MaxBodySizeMiddleware)

    # --- Rate limiting ---
    app.add_middleware(SlowAPIMiddleware)

    # --- Security response headers ---
    _is_dev = os.environ.get("NX_ENV", "") == "development"

    class SecurityHeadersMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):
            response = await call_next(request)
            response.headers["X-Content-Type-Options"] = "nosniff"
            response.headers["X-Frame-Options"] = "DENY"
            response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains; preload"
            )
            response.headers["Permissions-Policy"] = (
                "camera=(), microphone=(), geolocation=()"
            )
            if _is_dev:
                # Relaxed CSP for Vite dev server: HMR uses inline scripts + WebSocket
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self' 'unsafe-inline'; "
                    "style-src 'self' 'unsafe-inline'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self'; "
                    "connect-src 'self' ws: wss: http://localhost:*; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            else:
                response.headers["Content-Security-Policy"] = (
                    "default-src 'self'; "
                    "script-src 'self'; "
                    "style-src 'self'; "
                    "img-src 'self' data: https:; "
                    "font-src 'self'; "
                    "connect-src 'self' ws: wss:; "
                    "frame-ancestors 'none'; "
                    "base-uri 'self'; "
                    "form-action 'self'"
                )
            return response

    app.add_middleware(SecurityHeadersMiddleware)

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
    app.include_router(schedules_router)

    return app


# ── Server entrypoint ──


async def serve(app: FastAPI, host: str = "127.0.0.1", port: int = 8600) -> None:
    """Run the FastAPI app with uvicorn programmatically.

    Handles SIGTERM/SIGINT for graceful shutdown: stops accepting new
    connections, drains in-flight requests (up to 5s grace period),
    then exits cleanly.
    """
    import asyncio
    import uvicorn

    config = uvicorn.Config(app, host=host, port=port, log_level="info")
    server = uvicorn.Server(config)

    loop = asyncio.get_event_loop()
    stop_event = asyncio.Event()

    def _handle_signal(sig: signal.Signals) -> None:
        logger.info("Received %s — initiating graceful shutdown", sig.name)
        stop_event.set()

    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, _handle_signal, sig)
        except NotImplementedError:
            # Windows compatibility — signal handlers not supported
            signal.signal(sig, lambda s, f: stop_event.set())

    serve_task = asyncio.ensure_future(server.serve())

    await stop_event.wait()
    logger.info("Stopping server (active requests: %d)...", shutdown_state.pending_count)
    shutdown_state.signal_shutdown()
    server.should_exit = True

    try:
        await asyncio.wait_for(serve_task, timeout=10.0)
    except asyncio.TimeoutError:
        logger.warning("Server did not exit within 10s — forcing shutdown")
    except asyncio.CancelledError:
        pass

    logger.info("Server stopped")

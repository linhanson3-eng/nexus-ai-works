from __future__ import annotations

"""MCP Server — production-grade JSON-RPC 2.0 endpoint.

Transport: POST /mcp with Authorization: Bearer <JWT>
Rate limit: 10 req/s per session (token bucket, concurrent-safe)
Body limit: 1 MB
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.mcp.auth import MCPTokenManager
from gateway.mcp.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

_token_manager: MCPTokenManager | None = None


def _get_token_manager() -> MCPTokenManager:
    global _token_manager
    if _token_manager is None:
        secret = os.environ.get("MCP_TOKEN_SECRET", "")
        if not secret:
            secret = "nexus-mcp-dev-secret-" + str(id(_token_manager))
            logger.warning("MCP_TOKEN_SECRET not set — using ephemeral dev secret")
        _token_manager = MCPTokenManager(secret=secret)
    return _token_manager

MCP_MAX_BODY_BYTES = int(os.environ.get("MCP_MAX_BODY_BYTES", 1_048_576))
MCP_RATE_LIMIT_RPS = float(os.environ.get("MCP_RATE_LIMIT_RPS", 10.0))


# ── Rate limiter (token bucket, per-session, concurrent-safe) ──────

class TokenBucket:
    """Concurrent-safe token bucket with asyncio.Lock per bucket."""

    def __init__(self, rate: float, burst: int = 5):
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()
        self._last_access = time.monotonic()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last = now
            self._last_access = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_access


_rate_buckets: dict[str, TokenBucket] = {}
_rate_bucket_lock = asyncio.Lock()


async def _get_rate_bucket(session_id: str) -> TokenBucket:
    async with _rate_bucket_lock:
        if len(_rate_buckets) % 100 == 0 and len(_rate_buckets) > 0:
            stale = [
                k for k, b in _rate_buckets.items()
                if b.idle_seconds > 300
            ]
            for k in stale:
                del _rate_buckets[k]

        if session_id not in _rate_buckets:
            _rate_buckets[session_id] = TokenBucket(rate=MCP_RATE_LIMIT_RPS)
        return _rate_buckets[session_id]


# ── Auth helpers ────────────────────────────────────────────────────

def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


async def _verify_request(request: Request) -> dict | None:
    token = _extract_token(request)
    if not token:
        return None

    payload = _get_token_manager().verify(token)
    if payload is None:
        return None

    session_id = payload.get("session_id", "")
    if session_id:
        bucket = await _get_rate_bucket(session_id)
        if not await bucket.consume():
            return None

    return payload


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/health")
async def health():
    return {
        "status": "ok",
        "tools_count": len(TOOL_DEFINITIONS),
        "version": "1.0.0",
    }


@router.post("")
async def mcp_handler(request: Request):
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MCP_MAX_BODY_BYTES:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": f"Request body too large (max {MCP_MAX_BODY_BYTES} bytes)"},
                "id": None,
            },
            status_code=413,
        )

    payload = await _verify_request(request)
    if payload is None:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Unauthorized or rate limited — use Authorization: Bearer <token>"},
                "id": None,
            },
            status_code=401,
        )

    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(
            content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400,
        )

    req_id = body.get("id")
    method = body.get("method", "")
    session_id = payload.get("session_id", "")

    logger.info(
        "mcp_request",
        extra={
            "session_id": session_id[:12],
            "method": method,
            "request_id": req_id,
            "workshop": payload.get("workshop_name", ""),
        },
    )

    if method == "tools/list":
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": {"tools": TOOL_DEFINITIONS},
            "id": req_id,
        })

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        start_time = time.monotonic()
        try:
            org = request.app.state.org
            kanban_store = request.app.state.kanban_store
            session_manager = request.app.state.session_manager

            result = await execute_tool(
                tool_name, arguments,
                org=org, kanban_store=kanban_store,
                session_manager=session_manager,
                mcp_token_payload=payload,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            is_error = result.get("isError", False)
            logger.info(
                "mcp_tool_call",
                extra={
                    "session_id": session_id[:12],
                    "tool": tool_name,
                    "args_keys": list(arguments.keys()),
                    "duration_ms": round(duration_ms, 1),
                    "is_error": is_error,
                },
            )

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id,
            })

        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "mcp_tool_error",
                extra={
                    "session_id": session_id[:12],
                    "tool": tool_name,
                    "args_keys": list(arguments.keys()),
                    "duration_ms": round(duration_ms, 1),
                    "error": str(exc)[:200],
                },
            )
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(exc)[:200]},
                "id": req_id,
            })

    return JSONResponse(content={
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": req_id,
    })


@router.post("/token")
async def issue_token(request: Request):
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    workshop_name = body.get("workshop_name", "") or body.get("workshop", "")
    if not workshop_name:
        return JSONResponse(content={"error": "workshop_name is required"}, status_code=400)

    user_id = body.get("user_id", f"workshop:{workshop_name}")

    import uuid
    session_id = f"mcp-{uuid.uuid4().hex[:12]}"
    token = _get_token_manager().issue(
        user_id=user_id,
        session_id=session_id,
        workshop_name=workshop_name,
    )

    logger.info("mcp_token_issued", extra={
        "session_id": session_id[:12],
        "workshop": workshop_name,
    })

    return JSONResponse(content={
        "token": token,
        "session_id": session_id,
        "workshop_name": workshop_name,
        "endpoint": "/mcp",
        "header_format": "Authorization: Bearer <token>",
    })


@router.delete("/token/{jti}")
async def revoke_token(jti: str, request: Request):
    payload = await _verify_request(request)
    if payload is None:
        return JSONResponse(
            content={"error": "Unauthorized or rate limited"},
            status_code=401,
        )

    _get_token_manager().revoke(jti)
    logger.info("mcp_token_revoked", extra={"jti": jti})
    return JSONResponse(content={"status": "revoked", "jti": jti})

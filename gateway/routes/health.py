"""Health check and CSRF token endpoints."""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger(__name__)
router = APIRouter(tags=["health"])


@router.get("/health")
async def health(request: Request):
    checks: dict[str, str] = {}
    ok = True

    # 1. Database connectivity
    try:
        kanban = getattr(request.app.state, "kanban_store", None)
        if kanban and hasattr(kanban, "conn"):
            kanban.conn.execute("SELECT 1").fetchone()
        checks["db"] = "ok"
    except Exception as exc:
        checks["db"] = f"error: {exc}"
        ok = False

    # 2. Config file accessible
    try:
        config_path = "config/org.yaml"
        if os.path.exists(config_path) and os.access(config_path, os.R_OK):
            checks["config"] = "ok"
        else:
            checks["config"] = "missing/unreadable"
            ok = False
    except Exception as exc:
        checks["config"] = f"error: {exc}"
        ok = False

    # 3. Disk space (>100MB available on workspace volume)
    try:
        usage = shutil.disk_usage(os.getcwd())
        free_mb = usage.free // (1024 * 1024)
        checks["disk_free_mb"] = str(free_mb)
        if free_mb < 100:
            checks["disk"] = f"low ({free_mb}MB)"
            ok = False
        else:
            checks["disk"] = "ok"
    except Exception as exc:
        checks["disk"] = f"error: {exc}"

    # 4. Agent engine importable
    try:
        from factory.engine.bridge import create_agent, create_model_config
        checks["engine"] = "ok"
    except Exception as exc:
        checks["engine"] = f"error: {exc}"
        ok = False

    # 5. Settings store loaded
    try:
        settings = getattr(request.app.state, "settings_store", None)
        if settings and settings._data is not None:
            providers = len(settings._data.get("providers", {}))
            checks["settings_providers"] = str(providers)
        else:
            checks["settings_providers"] = "not loaded"
    except Exception:
        checks["settings_providers"] = "error"

    return {
        "status": "ok" if ok else "degraded",
        "version": "1.0.0",
        "checks": checks,
    }


@router.get("/api/csrf-token")
async def csrf_token(request: Request):
    from gateway.csrf import CSRF_COOKIE, COOKIE_MAX_AGE, _generate_token

    token = request.cookies.get(CSRF_COOKIE) or _generate_token()
    resp = JSONResponse(content={"token": token})
    is_secure = request.headers.get("X-Forwarded-Proto", "http") == "https"
    resp.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=False,
        samesite="strict",
        secure=is_secure,
    )
    return resp


@router.get("/api/auth/status")
async def auth_status():
    from gateway.auth import API_KEY_PATH
    return {"key_configured": API_KEY_PATH.exists()}


@router.get("/api/auth/api-key")
async def get_api_key(request: Request):
    """Return the local API key for the web UI. Only accessible from localhost."""
    client_host = request.client.host if request.client else ""
    if client_host not in ("127.0.0.1", "::1", "localhost"):
        return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
    from gateway.auth import get_or_create_api_key
    return {"api_key": get_or_create_api_key()}

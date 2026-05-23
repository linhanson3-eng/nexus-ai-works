"""FastAPI application — main marketplace API routes."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from slowapi import Limiter
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from factory.security.audit import record as audit_record, AuditEvent
from marketplace.auth import create_token, decode_token, hash_password, verify_password
from marketplace.models import (
    LoginRequest,
    MarketplacePackage,
    RegisterRequest,
    Subscription,
    TokenResponse,
    UserInfo,
)
from marketplace.store import MarketplaceStore

# ── App & Store ───────────────────────────────────────────────────────

app = FastAPI(title="Nexus Solution Marketplace", version="1.0.0")

cors_origins = os.environ.get(
    "CORS_ORIGINS",
    "http://localhost:5173,http://localhost:8600",
).split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Content-Type", "Authorization", "X-CSRF-Token"],
)

limiter = Limiter(key_func=get_remote_address, default_limits=["30/minute"])
app.state.limiter = limiter
app.add_middleware(SlowAPIMiddleware)

# Security response headers
class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'; connect-src 'self'; "
            "frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        )
        return response

app.add_middleware(SecurityHeadersMiddleware)

store = MarketplaceStore()
security = HTTPBearer(auto_error=False)
PACKAGES_DIR = Path(__file__).parent / "packages"

# ── Auth helpers ──────────────────────────────────────────────────────


async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict:
    """Extract the current user from the Bearer token, or raise 401."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Missing authorization header")
    payload = decode_token(credentials.credentials)
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security),
) -> dict | None:
    """Extract the current user from the Bearer token, or return None."""
    if credentials is None:
        return None
    return decode_token(credentials.credentials)


# ── Catalog ───────────────────────────────────────────────────────────


@app.get("/api/catalog")
async def list_catalog(category: str = ""):
    """List published packages, optionally filtered by category."""
    packages = store.list_packages(category=category)
    return JSONResponse(
        content=[pkg.model_dump() for pkg in packages],
    )


@app.get("/api/packages/{package_id}")
async def get_package_detail(package_id: str):
    """Get details for a single package."""
    pkg = store.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return JSONResponse(content=pkg.model_dump())


@app.get("/api/packages/{package_id}/download")
async def download_package(
    package_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Download a .nexus.zip package file. Requires auth + valid subscription."""
    user_id = current_user["user_id"]

    # Check access
    if not store.has_access(user_id, package_id):
        raise HTTPException(
            status_code=403,
            detail="You do not have an active subscription for this package",
        )

    # Locate package file
    zip_path = PACKAGES_DIR / f"{package_id}.nexus.zip"
    if not zip_path.is_file():
        raise HTTPException(status_code=404, detail="Package file not found on server")

    # Increment download count
    store.increment_download(package_id)

    return FileResponse(
        path=str(zip_path),
        filename=f"{package_id}.nexus.zip",
        media_type="application/zip",
    )


# ── My Subscriptions ──────────────────────────────────────────────────


@app.get("/api/my")
async def my_subscriptions(
    current_user: dict = Depends(get_current_user),
):
    """List the current user's active subscriptions."""
    user_id = current_user["user_id"]
    subs = store.get_subscriptions(user_id)
    return JSONResponse(content=[sub.model_dump() for sub in subs])


# ── Auth routes ───────────────────────────────────────────────────────


@app.post("/api/auth/register")
async def register(req: RegisterRequest):
    """Register a new user account."""
    if len(req.username) < 3:
        raise HTTPException(status_code=400, detail="Username must be at least 3 characters")
    if len(req.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    password_hash = hash_password(req.password)
    user = store.create_user(req.username, password_hash)
    if user is None:
        raise HTTPException(status_code=409, detail="Username already taken")

    audit_record(
        AuditEvent.AUTH_REGISTER, "user.registered",
        actor=user.user_id, resource=f"user:{req.username}",
        detail="new registration",
    )
    token = create_token(user.user_id, user.username)
    return TokenResponse(token=token, user=user)


@app.post("/api/auth/login")
async def login(req: LoginRequest, request: Request):
    """Login with username and password."""
    user_row = store.get_user(req.username)
    if user_row is None:
        audit_record(
            AuditEvent.AUTH_FAILED, "login.failed",
            actor=req.username, detail="user not found",
            ip_address=request.client.host if request.client else "",
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    if not verify_password(req.password, user_row["password_hash"]):
        audit_record(
            AuditEvent.AUTH_FAILED, "login.failed",
            actor=req.username, detail="wrong password",
            ip_address=request.client.host if request.client else "",
        )
        raise HTTPException(status_code=401, detail="Invalid username or password")

    user = UserInfo(user_id=user_row["id"], username=user_row["username"])

    # Check VIP status
    conn = store._conn()
    try:
        vip_row = conn.execute(
            "SELECT 1 FROM subscriptions WHERE user_id = ? AND plan_type = 'vip' "
            "AND expires_at > ?",
            (user.user_id, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        user.is_vip = vip_row is not None
    finally:
        conn.close()

    audit_record(
        AuditEvent.AUTH_LOGIN, "user.logged_in",
        actor=user.user_id, resource=f"user:{user.username}",
        ip_address=request.client.host if request.client else "",
    )
    token = create_token(user.user_id, user.username)
    return TokenResponse(token=token, user=user)


@app.get("/api/auth/me")
async def me(current_user: dict = Depends(get_current_user)):
    """Return the current user's profile."""
    user_id = current_user["user_id"]
    username = current_user.get("username", "")

    # Check VIP status
    conn = store._conn()
    try:
        vip_row = conn.execute(
            "SELECT 1 FROM subscriptions WHERE user_id = ? AND plan_type = 'vip' "
            "AND expires_at > ?",
            (user_id, datetime.now(timezone.utc).isoformat()),
        ).fetchone()
        is_vip = vip_row is not None
    finally:
        conn.close()

    user = UserInfo(user_id=user_id, username=username, is_vip=is_vip)
    return JSONResponse(content=user.model_dump())

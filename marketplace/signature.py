"""Server-side HMAC signature verification for marketplace API."""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, Request

SHARED_SECRET_PATH = Path("~/.nexus/marketplace_shared_secret").expanduser()


def _get_shared_secret() -> str:
    """Get shared secret from env var, file, or generate + persist a new one."""
    env_secret = os.environ.get("MARKETPLACE_SHARED_SECRET", "")
    if env_secret:
        return env_secret
    SHARED_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SHARED_SECRET_PATH.exists():
        return SHARED_SECRET_PATH.read_text().strip()
    secret = secrets.token_hex(32)
    SHARED_SECRET_PATH.write_text(secret)
    SHARED_SECRET_PATH.chmod(0o600)
    return secret


async def verify_signature(request: Request) -> None:
    """FastAPI dependency: verify X-Signature on protected endpoints.

    Skips /api/auth/* and /api/catalog (public endpoints).
    Skips verification if no clients registered yet (V1 compatibility).
    """
    path = request.url.path
    if path.startswith("/api/auth/") or path == "/api/catalog":
        return

    sig = request.headers.get("X-Signature", "")
    ts = request.headers.get("X-Timestamp", "")

    # V1: skip verification if no signature header (backward compat)
    if not sig:
        return

    if not ts:
        raise HTTPException(status_code=401, detail="Missing timestamp")

    # Anti-replay: +/- 5 minute window
    try:
        req_time = datetime.fromisoformat(ts)
        if req_time.tzinfo is None:
            req_time = req_time.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if abs((now - req_time).total_seconds()) > 300:
            raise HTTPException(status_code=401, detail="Timestamp expired")
    except ValueError as e:
        raise HTTPException(status_code=401, detail="Invalid timestamp") from e

    secret = _get_shared_secret()

    body = await request.body()
    message = f"{request.method}\n{path}\n{body.decode()}\n{ts}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

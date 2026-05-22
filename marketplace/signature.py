"""Server-side HMAC signature verification for marketplace API."""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request


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
        now = datetime.now(timezone.utc)
        if abs((now - req_time).total_seconds()) > 300:
            raise HTTPException(status_code=401, detail="Timestamp expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")

    # HMAC verify — use a shared secret. V1: env var or default.
    secret = os.environ.get("MARKETPLACE_SHARED_SECRET", "nexus-shared-secret-v1")

    body = await request.body()
    message = f"{request.method}\n{path}\n{body.decode()}\n{ts}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")

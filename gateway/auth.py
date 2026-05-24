from __future__ import annotations

"""API authentication — API Key + JWT dependency injection for FastAPI.

- Local CLI/Agent calls: API Key (x-api-key header)
- Web UI login: JWT (Authorization: Bearer <token>)
- First start auto-generates API Key to ~/.nexus/api_key
"""


import hmac
import logging
import os
import secrets
from pathlib import Path

from fastapi import HTTPException, Request

API_KEY_PATH = Path("~/.nexus/api_key").expanduser()
logger = logging.getLogger(__name__)


def get_or_create_api_key() -> str:
    """Get existing API key or generate a new one."""
    API_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if API_KEY_PATH.exists():
        return API_KEY_PATH.read_text().strip()
    key = "nk-" + secrets.token_hex(24)
    tmp_path = API_KEY_PATH.with_suffix(".tmp")
    tmp_path.write_text(key)
    tmp_path.chmod(0o600)
    os.replace(tmp_path, API_KEY_PATH)
    return key


def verify_api_key(key: str) -> bool:
    """Constant-time API key comparison."""
    stored = get_or_create_api_key()
    return hmac.compare_digest(key.encode(), stored.encode())


async def require_auth(request: Request):
    """FastAPI dependency: require either API Key or JWT."""
    # 1. Check API Key
    api_key = request.headers.get("x-api-key", "")
    if api_key and verify_api_key(api_key):
        return

    # 2. Check JWT token
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        if _verify_jwt(auth[7:]):
            return

    raise HTTPException(status_code=401, detail="Authentication required")


def _verify_jwt(token: str) -> bool:
    """Verify HMAC-signed token (reuses marketplace/auth.py logic)."""
    try:
        from marketplace.auth import decode_token

        payload = decode_token(token)
        return payload is not None
    except Exception as exc:
        logger.debug("JWT verification failed: %s", exc)
        return False

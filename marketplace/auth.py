"""Authentication utilities for the Solution Marketplace.

Token format: base64url(header).base64url(payload).base64url(signature)
Signed with HMAC-SHA256.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sys
import time
from pathlib import Path

JWT_SECRET_PATH = Path("~/.nexus/marketplace_jwt_secret").expanduser()


def _get_jwt_secret() -> str:
    """Get JWT secret from env var, file, or generate + persist a new one."""
    env_secret = os.environ.get("MARKETPLACE_JWT_SECRET", "")
    if env_secret:
        return env_secret
    JWT_SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if JWT_SECRET_PATH.exists():
        return JWT_SECRET_PATH.read_text().strip()
    secret = secrets.token_hex(32)
    JWT_SECRET_PATH.write_text(secret)
    JWT_SECRET_PATH.chmod(0o600)
    return secret


JWT_SECRET = _get_jwt_secret()
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 720


def _b64url_encode(data: bytes) -> str:
    """Base64 URL-safe encode without padding."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(s: str) -> bytes:
    """Base64 URL-safe decode, adding padding back."""
    rem = len(s) % 4
    if rem:
        s += "=" * (4 - rem)
    return base64.urlsafe_b64decode(s)


def hash_password(password: str) -> str:
    """Hash a password using PBKDF2-HMAC-SHA256 with 100,000 iterations.

    Returns format: salt:key (both hex-encoded).
    """
    salt = secrets.token_hex(16)
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    )
    return f"{salt}:{key.hex()}"


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored salt:key PBKDF2 hash."""
    try:
        salt, h = stored_hash.split(":", 1)
    except ValueError:
        return False
    key = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    )
    return hmac.compare_digest(key.hex(), h)


def create_token(user_id: str, username: str) -> str:
    """Create a signed JWT-like token."""
    header = {"alg": JWT_ALGORITHM, "typ": "JWT"}
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": int(time.time()) + JWT_EXPIRE_HOURS * 3600,
        "iat": int(time.time()),
    }

    header_b64 = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_b64 = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))

    signing_input = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        JWT_SECRET.encode("utf-8"),
        signing_input.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    signature_b64 = _b64url_encode(signature)

    return f"{signing_input}.{signature_b64}"


def decode_token(token: str) -> dict | None:
    """Decode and verify a token. Returns payload dict or None if invalid/expired."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None

        header_b64, payload_b64, signature_b64 = parts

        # Verify signature
        signing_input = f"{header_b64}.{payload_b64}"
        expected_sig = hmac.new(
            JWT_SECRET.encode("utf-8"),
            signing_input.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        actual_sig = _b64url_decode(signature_b64)

        if not hmac.compare_digest(expected_sig, actual_sig):
            return None

        # Decode payload
        payload_bytes = _b64url_decode(payload_b64)
        payload = json.loads(payload_bytes)

        # Check expiration
        if payload.get("exp", 0) < int(time.time()):
            return None

        return payload
    except Exception:
        return None


ADMIN_TOKEN_PATH = Path("~/.nexus/admin_token").expanduser()
ADMIN_TOKEN_HASH = os.environ.get("MARKETPLACE_ADMIN_TOKEN_HASH", "")
if not ADMIN_TOKEN_HASH:
    if ADMIN_TOKEN_PATH.exists():
        ADMIN_TOKEN_HASH = hash_password(ADMIN_TOKEN_PATH.read_text().strip())
    else:
        admin_token = secrets.token_hex(24)
        ADMIN_TOKEN_HASH = hash_password(admin_token)
        ADMIN_TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        ADMIN_TOKEN_PATH.write_text(admin_token)
        ADMIN_TOKEN_PATH.chmod(0o600)
        print(
            f"[marketplace] Admin token saved to {ADMIN_TOKEN_PATH} "
            f"(set MARKETPLACE_ADMIN_TOKEN_HASH env var to persist)",
            file=sys.stderr,
        )


def verify_admin_token(token: str) -> bool:
    """Verify admin token against stored hash."""
    return verify_password(token, ADMIN_TOKEN_HASH)

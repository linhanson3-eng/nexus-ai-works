"""HMAC request signing for local-cloud API communication.

Shared secret stored at ~/.nexus/marketplace_secret.
Generated on first run.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

SECRET_PATH = Path("~/.nexus/marketplace_secret").expanduser()


def get_or_create_secret() -> str:
    """Get existing secret or generate a new one."""
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()
    secret = secrets.token_hex(32)
    SECRET_PATH.write_text(secret)
    SECRET_PATH.chmod(0o600)
    return secret


def sign_request(method: str, path: str, body: str, timestamp: str) -> str:
    """Produce HMAC-SHA256 signature for a request."""
    secret = get_or_create_secret()
    message = f"{method}\n{path}\n{body}\n{timestamp}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()

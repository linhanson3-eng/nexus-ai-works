from __future__ import annotations

"""HMAC request signing for local-cloud API communication.

Shared secret stored at ~/.nexus/marketplace_shared_secret.
Generated on first run. Migrates from old marketplace_secret path.
"""


import hashlib
import hmac
import os
import secrets
from pathlib import Path

SECRET_PATH = Path("~/.nexus/marketplace_shared_secret").expanduser()
OLD_SECRET_PATH = Path("~/.nexus/marketplace_secret").expanduser()


def get_or_create_secret() -> str:
    """Get existing secret or generate a new one.

    Migrates from old ~/.nexus/marketplace_secret path if present.
    """
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()
    # Migrate from old path
    if OLD_SECRET_PATH.exists():
        secret = OLD_SECRET_PATH.read_text().strip()
        tmp_path = SECRET_PATH.with_suffix(".tmp")
        tmp_path.write_text(secret)
        tmp_path.chmod(0o600)
        os.replace(tmp_path, SECRET_PATH)
        return secret
    secret = secrets.token_hex(32)
    tmp_path = SECRET_PATH.with_suffix(".tmp")
    tmp_path.write_text(secret)
    tmp_path.chmod(0o600)
    os.replace(tmp_path, SECRET_PATH)
    return secret


def sign_request(method: str, path: str, body: str, timestamp: str) -> str:
    """Produce HMAC-SHA256 signature for a request."""
    secret = get_or_create_secret()
    message = f"{method}\n{path}\n{body}\n{timestamp}".encode("utf-8")
    return hmac.new(secret.encode("utf-8"), message, hashlib.sha256).hexdigest()

"""API key encryption — AES-256-GCM with a machine-local key.

Keys are encrypted at rest in settings.json and only decrypted
in memory when actively needed by provider resolution.

Key derivation: HKDF-SHA256 from a random seed stored in
~/.nexus/.keyseed (per-machine, auto-generated on first use).
"""

from __future__ import annotations

import os
import secrets
from base64 import urlsafe_b64encode, urlsafe_b64decode
from pathlib import Path

KEY_SEED_PATH = Path("~/.nexus/.keyseed").expanduser()

# Lazy-loaded module-level cache
_cipher: object | None = None


def _ensure_key() -> bytes:
    """Get or create the machine-local encryption key seed."""
    KEY_SEED_PATH.parent.mkdir(parents=True, exist_ok=True)
    if KEY_SEED_PATH.exists():
        return urlsafe_b64decode(KEY_SEED_PATH.read_bytes())

    seed = secrets.token_bytes(32)
    KEY_SEED_PATH.write_bytes(urlsafe_b64encode(seed))
    os.chmod(KEY_SEED_PATH, 0o600)
    return seed


def _get_cipher():
    """Lazy-load the AES-GCM cipher (avoid import overhead when unused)."""
    global _cipher
    if _cipher is not None:
        return _cipher
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    _cipher = AESGCM(_ensure_key())
    return _cipher


def encrypt(plaintext: str) -> str:
    """Encrypt a plaintext string. Returns base64-encoded ciphertext.

    Format: base64(nonce || ciphertext)
    """
    if not plaintext:
        return ""
    nonce = secrets.token_bytes(12)
    cipher = _get_cipher()
    ciphertext = cipher.encrypt(nonce, plaintext.encode("utf-8"), None)
    combined = nonce + ciphertext
    return urlsafe_b64encode(combined).decode("ascii")


def decrypt(encoded: str) -> str:
    """Decrypt a base64-encoded ciphertext back to plaintext.

    Returns the empty string for empty input (unset key).
    """
    if not encoded:
        return ""
    cipher = _get_cipher()
    combined = urlsafe_b64decode(encoded.encode("ascii"))
    nonce = combined[:12]
    ciphertext = combined[12:]
    return cipher.decrypt(nonce, ciphertext, None).decode("utf-8")

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

import jwt

logger = logging.getLogger(__name__)


class MCPTokenManager:
    """Issue and verify session-scoped MCP tokens using PyJWT.

    HS256 JWT with kid header for future key rotation.
    max_uses tracking to prevent token reuse.
    Automatic stale cleanup on verify().
    """

    def __init__(
        self,
        secret: str,
        ttl_seconds: int = 86400,
        max_uses: int = 1,
        kid: str = "mcp-default",
    ):
        if not secret:
            raise RuntimeError("MCPTokenManager requires a non-empty secret")
        self._secret = secret
        self._ttl = ttl_seconds
        self._max_uses = max_uses
        self._kid = kid
        self._use_counts: dict[str, int] = {}
        self._use_expiry: dict[str, int] = {}
        self._last_cleanup: float = time.monotonic()

    def issue(
        self,
        user_id: str,
        session_id: str,
        workshop_name: str,
    ) -> str:
        now = int(time.time())
        jti = uuid.uuid4().hex[:12]
        payload = {
            "sub": user_id,
            "session_id": session_id,
            "workshop_name": workshop_name,
            "iat": now,
            "exp": now + self._ttl,
            "aud": "ai-factory",
            "iss": "ai-factory",
            "jti": jti,
        }
        headers = {"kid": self._kid}
        return jwt.encode(payload, self._secret, algorithm="HS256", headers=headers)

    def verify(self, token: str) -> dict[str, Any] | None:
        self._maybe_cleanup()
        try:
            payload = jwt.decode(
                token,
                self._secret,
                algorithms=["HS256"],
                audience="ai-factory",
                issuer="ai-factory",
                options={"require": ["exp", "jti", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT verification failed: %s", exc)
            return None

        jti = payload.get("jti", "")
        if jti:
            count = self._use_counts.get(jti, 0)
            if count >= self._max_uses:
                return None
            self._use_counts[jti] = count + 1
            self._use_expiry[jti] = payload.get("exp", 0)

        return payload

    def revoke(self, jti: str) -> None:
        self._use_counts[jti] = self._max_uses

    def _maybe_cleanup(self) -> None:
        now = time.monotonic()
        count = len(self._use_counts)
        if count > 0 and (count % 100 == 0 or now - self._last_cleanup > 60):
            self._cleanup_stale()
            self._last_cleanup = now

    def _cleanup_stale(self) -> None:
        now = int(time.time())
        stale = [jti for jti, exp in self._use_expiry.items() if exp < now]
        for jti in stale:
            self._use_counts.pop(jti, None)
            self._use_expiry.pop(jti, None)
        if stale:
            logger.debug("Cleaned up %d stale token entries", len(stale))

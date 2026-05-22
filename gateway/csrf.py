"""CSRF protection via double-submit cookie pattern.

Sets a csrf_token cookie readable by JS. State-changing requests
(POST/PUT/PATCH/DELETE) must include X-CSRF-Token header that
matches the cookie value.
"""

from __future__ import annotations

import secrets

from fastapi import HTTPException, Request
from fastapi.responses import Response
from starlette.middleware.base import BaseHTTPMiddleware

SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
CSRF_COOKIE = "csrf_token"
CSRF_HEADER = "x-csrf-token"
COOKIE_MAX_AGE = 86400  # 24 hours


def _generate_token() -> str:
    return secrets.token_hex(32)


class CSRFTokenMiddleware(BaseHTTPMiddleware):
    """Middleware that sets csrf_token cookie and validates on unsafe methods.

    Skip paths (e.g. webhooks, SSE) can be configured via ``skip_paths``.
    """

    def __init__(self, app, skip_paths: tuple[str, ...] = ()):
        super().__init__(app)
        self._skip_prefixes = skip_paths

    async def dispatch(self, request: Request, call_next):
        # Skip certain paths (e.g. webhook callbacks, SSE streams)
        for prefix in self._skip_prefixes:
            if request.url.path.startswith(prefix):
                return await call_next(request)

        # Read existing token or generate new one
        cookie_token = request.cookies.get(CSRF_COOKIE)

        if request.method not in SAFE_METHODS:
            header_token = request.headers.get(CSRF_HEADER, "")
            if not cookie_token or not secrets.compare_digest(cookie_token, header_token):
                raise HTTPException(status_code=403, detail="CSRF token missing or invalid")

        response: Response = await call_next(request)

        if not cookie_token:
            cookie_token = _generate_token()

        response.set_cookie(
            CSRF_COOKIE,
            cookie_token,
            max_age=COOKIE_MAX_AGE,
            httponly=False,  # must be JS-readable for double-submit
            samesite="strict",
            secure=False,  # True in prod behind HTTPS
        )
        return response

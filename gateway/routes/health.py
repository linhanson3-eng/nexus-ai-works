"""Health check and CSRF token endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}


@router.get("/api/csrf-token")
async def csrf_token(request: Request):
    from gateway.csrf import CSRF_COOKIE, COOKIE_MAX_AGE, _generate_token

    token = request.cookies.get(CSRF_COOKIE) or _generate_token()
    resp = JSONResponse(content={"token": token})
    resp.set_cookie(
        CSRF_COOKIE,
        token,
        max_age=COOKIE_MAX_AGE,
        httponly=False,
        samesite="strict",
        secure=False,
    )
    return resp

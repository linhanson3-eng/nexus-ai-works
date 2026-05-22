"""方案市场本地代理 — 转发请求到云端 API."""
from __future__ import annotations

import os
import tempfile
import zipfile
import shutil
from pathlib import Path

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.signature import sign_request

router = APIRouter(prefix="/api/market", tags=["market"])
CLOUD_URL = os.environ.get("MARKETPLACE_API_URL", "http://127.0.0.1:8800")


def _forward_headers(request: Request) -> dict[str, str]:
    """Extract headers to forward to the cloud API, including Authorization."""
    headers: dict[str, str] = {}
    auth = request.headers.get("Authorization")
    if auth:
        headers["Authorization"] = auth
    content_type = request.headers.get("Content-Type")
    if content_type:
        headers["Content-Type"] = content_type
    return headers


def _signed_headers(method: str, path: str, body: str = "") -> dict[str, str]:
    ts = datetime.now(timezone.utc).isoformat()
    sig = sign_request(method, path, body, ts)
    return {"X-Signature": sig, "X-Timestamp": ts}


async def _proxy_get(request: Request, cloud_path: str) -> JSONResponse:
    """Forward a GET request to the cloud API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{CLOUD_URL.rstrip('/')}{cloud_path}"
        headers = {**_forward_headers(request), **_signed_headers("GET", cloud_path)}
        resp = await client.get(
            url,
            params=dict(request.query_params),
            headers=headers,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"detail": resp.text}
        return JSONResponse(content=data, status_code=resp.status_code)


async def _proxy_post(request: Request, cloud_path: str) -> JSONResponse:
    """Forward a POST request to the cloud API."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        url = f"{CLOUD_URL.rstrip('/')}{cloud_path}"
        body = await request.body()
        headers = {
            **_forward_headers(request),
            **_signed_headers("POST", cloud_path, body.decode()),
        }
        resp = await client.post(
            url,
            content=body,
            headers=headers,
        )
        try:
            data = resp.json()
        except Exception:
            data = {"detail": resp.text}
        return JSONResponse(content=data, status_code=resp.status_code)


# ── Proxy routes ──


@router.get("/catalog")
async def catalog(request: Request):
    """Proxy: GET /api/catalog with query params."""
    return await _proxy_get(request, "/api/catalog")


@router.get("/packages/{package_id}")
async def get_package(package_id: str, request: Request):
    """Proxy: GET /api/packages/{package_id}."""
    return await _proxy_get(request, f"/api/packages/{package_id}")


@router.get("/my")
async def my_packages(request: Request):
    """Proxy: GET /api/my."""
    return await _proxy_get(request, "/api/my")


@router.post("/auth/login")
async def auth_login(request: Request):
    """Proxy: POST /api/auth/login."""
    return await _proxy_post(request, "/api/auth/login")


@router.post("/auth/register")
async def auth_register(request: Request):
    """Proxy: POST /api/auth/register."""
    return await _proxy_post(request, "/api/auth/register")


@router.get("/auth/me")
async def auth_me(request: Request):
    """Proxy: GET /api/auth/me."""
    return await _proxy_get(request, "/api/auth/me")


# ── Special route: install (download + extract + import) ──


@router.post("/packages/{package_id}/install")
async def install_package(package_id: str, request: Request):
    """Download .nexus.zip from cloud, extract, and import via WorkshopManager."""
    from factory.workshop.manager import WorkshopManager

    try:
        # 1. Download zip from cloud
        async with httpx.AsyncClient(timeout=120.0) as client:
            url = f"{CLOUD_URL.rstrip('/')}/api/packages/{package_id}/download"
            cloud_path = f"/api/packages/{package_id}/download"
            headers = {**_forward_headers(request), **_signed_headers("GET", cloud_path)}
            resp = await client.get(url, headers=headers)
            if resp.status_code != 200:
                try:
                    detail = resp.json()
                except Exception:
                    detail = {"detail": resp.text}
                return JSONResponse(content=detail, status_code=resp.status_code)

            zip_data = resp.content

        # 2. Save to temp file and extract
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            zip_path = tmppath / f"{package_id}.nexus.zip"
            zip_path.write_bytes(zip_data)

            extract_dir = tmppath / "package"
            extract_dir.mkdir(exist_ok=True)

            if zipfile.is_zipfile(zip_path):
                with zipfile.ZipFile(zip_path, "r") as zf:
                    zf.extractall(extract_dir)
            else:
                # Not a zip — treat as raw directory?
                return JSONResponse(
                    content={"detail": "Downloaded file is not a valid zip archive"},
                    status_code=400,
                )

            # 3. Find the package directory (the zip may have a top-level dir)
            pkg_dir = extract_dir
            entries = list(extract_dir.iterdir())
            if len(entries) == 1 and entries[0].is_dir():
                pkg_dir = entries[0]

            # 4. Import via WorkshopManager
            mgr = WorkshopManager(request.app.state.org, request.app.state.kanban_store)
            result = mgr.import_package(str(pkg_dir))

            if result is None:
                return JSONResponse(
                    content={"detail": "Import failed (workspace may already exist)"},
                    status_code=409,
                )

            return JSONResponse(content=result, status_code=201)

    except httpx.ConnectError:
        return JSONResponse(
            content={"detail": "Cannot connect to marketplace API"},
            status_code=502,
        )
    except httpx.TimeoutException:
        return JSONResponse(
            content={"detail": "Marketplace API request timed out"},
            status_code=504,
        )
    except Exception as exc:
        return JSONResponse(
            content={"detail": f"Install failed: {exc}"},
            status_code=500,
        )

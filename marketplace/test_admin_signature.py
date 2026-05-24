from __future__ import annotations
"""Tests for marketplace admin API and signature verification."""

import hashlib
import hmac
import os
import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

import marketplace.admin as admin_mod
import marketplace.signature as sig_mod


# ── Admin API Tests ──


@pytest_asyncio.fixture(autouse=True)
def _patch_admin_store(monkeypatch, tmp_path):
    """Replace admin store with a temp-db store."""
    import marketplace.store as ms
    s = ms.MarketplaceStore(str(tmp_path / "admin_test.db"))
    monkeypatch.setattr(admin_mod, "store", s)
    monkeypatch.setattr(admin_mod, "PACKAGES_DIR", tmp_path / "packages")
    (tmp_path / "packages").mkdir(exist_ok=True)


@pytest_asyncio.fixture
async def admin_client():
    transport = ASGITransport(app=admin_mod.admin)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _admin_auth_header():
    """Generate a valid admin Bearer token."""
    from marketplace.auth import ADMIN_TOKEN_PATH
    token = ADMIN_TOKEN_PATH.read_text().strip() if ADMIN_TOKEN_PATH.exists() else ""
    if not token:
        from marketplace.auth import _get_or_create_admin_token
        token = _get_or_create_admin_token()
    return {"Authorization": f"Bearer {token}"}


class TestAdmin:
    async def test_publish_package(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/packages",
            json={"id": "test-pkg", "name": "Test Package", "description": "A test"},
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 201
        assert resp.json()["package_id"] == "test-pkg"

    async def test_publish_package_no_auth(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/packages",
            json={"id": "test-pkg2", "name": "Test"},
        )
        assert resp.status_code == 403

    async def test_publish_package_generates_id(self, admin_client):
        resp = await admin_client.post(
            "/api/admin/packages",
            json={"name": "Auto ID"},
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 201
        assert resp.json()["package_id"]

    async def test_delete_package(self, admin_client):
        # Create first
        await admin_client.post(
            "/api/admin/packages",
            json={"id": "del-me", "name": "Delete Me"},
            headers=_admin_auth_header(),
        )
        resp = await admin_client.delete(
            "/api/admin/packages/del-me",
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "del-me"

    async def test_delete_package_not_found(self, admin_client):
        resp = await admin_client.delete(
            "/api/admin/packages/nonexistent",
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 404

    async def test_delete_package_no_auth(self, admin_client):
        resp = await admin_client.delete("/api/admin/packages/something")
        assert resp.status_code == 403

    async def test_activate_subscription(self, admin_client):
        from marketplace.models import PlanType

        resp = await admin_client.post(
            "/api/admin/activate",
            json={
                "user_id": "user-1",
                "package_id": "pkg-1",
                "plan_type": PlanType.monthly.value,
                "duration_months": 3,
            },
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["user_id"] == "user-1"
        assert data["package_id"] == "pkg-1"

    async def test_activate_subscription_no_auth(self, admin_client):
        from marketplace.models import PlanType

        resp = await admin_client.post(
            "/api/admin/activate",
            json={
                "user_id": "u", "package_id": "p",
                "plan_type": PlanType.monthly.value, "duration_months": 1,
            },
        )
        assert resp.status_code == 403

    async def test_activate_vip(self, admin_client):
        from marketplace.models import PlanType

        resp = await admin_client.post(
            "/api/admin/activate",
            json={
                "user_id": "vip-user",
                "package_id": "vip-access",
                "plan_type": PlanType.vip.value,
                "duration_months": 12,
            },
            headers=_admin_auth_header(),
        )
        assert resp.status_code == 201


# ── Signature Tests ──


class TestSharedSecret:
    def test_env_secret(self, monkeypatch):
        monkeypatch.setenv("MARKETPLACE_SHARED_SECRET", "env-secret-123")
        assert sig_mod._get_shared_secret() == "env-secret-123"

    def test_file_secret(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MARKETPLACE_SHARED_SECRET", raising=False)
        f = tmp_path / "secret"
        f.write_text("file-secret-456")
        monkeypatch.setattr(sig_mod, "SHARED_SECRET_PATH", f)
        assert sig_mod._get_shared_secret() == "file-secret-456"

    def test_generate_new_secret(self, monkeypatch, tmp_path):
        monkeypatch.delenv("MARKETPLACE_SHARED_SECRET", raising=False)
        f = tmp_path / "new_secret"
        monkeypatch.setattr(sig_mod, "SHARED_SECRET_PATH", f)
        s = sig_mod._get_shared_secret()
        assert len(s) == 64  # token_hex(32)
        assert f.exists()


class TestVerifySignature:
    @pytest.fixture(autouse=True)
    def _patch_secret(self, monkeypatch):
        monkeypatch.setattr(sig_mod, "_get_shared_secret", lambda: "test-shared-secret")

    async def _make_request(self, path, method="GET", headers=None, body=b""):
        """Create a mock request-like object for signature verification."""
        from unittest.mock import AsyncMock, MagicMock

        request = MagicMock()
        request.url.path = path
        request.method = method
        request.headers = headers or {}
        request.body = AsyncMock(return_value=body)
        return request

    async def test_skip_auth_paths(self):
        # Public paths should skip verification
        for path in ["/api/auth/login", "/api/auth/register", "/api/catalog"]:
            req = await self._make_request(path)
            await sig_mod.verify_signature(req)  # should not raise

    async def test_skip_no_signature(self):
        # Backward compat: no sig header → skip
        req = await self._make_request("/api/download/pkg-1")
        await sig_mod.verify_signature(req)  # should not raise

    async def test_missing_timestamp(self):
        from fastapi import HTTPException

        req = await self._make_request(
            "/api/download/pkg-1",
            headers={"X-Signature": "abc123"},
        )
        with pytest.raises(HTTPException) as exc:
            await sig_mod.verify_signature(req)
        assert exc.value.status_code == 401
        assert "timestamp" in str(exc.value.detail).lower()

    async def test_expired_timestamp(self):
        from fastapi import HTTPException
        from datetime import datetime, timezone, timedelta

        old_ts = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        req = await self._make_request(
            "/api/download/pkg-1",
            headers={"X-Signature": "abc", "X-Timestamp": old_ts},
        )
        with pytest.raises(HTTPException) as exc:
            await sig_mod.verify_signature(req)
        assert exc.value.status_code == 401
        assert "expired" in str(exc.value.detail).lower()

    async def test_invalid_signature(self):
        from fastapi import HTTPException
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        req = await self._make_request(
            "/api/download/pkg-1",
            method="GET",
            headers={"X-Signature": "wrong", "X-Timestamp": now},
        )
        with pytest.raises(HTTPException) as exc:
            await sig_mod.verify_signature(req)
        assert exc.value.status_code == 401
        assert "signature" in str(exc.value.detail).lower()

    async def test_valid_signature(self):
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        path = "/api/download/pkg-1"
        method = "GET"
        body = b""
        message = f"{method}\n{path}\n{body.decode()}\n{now}".encode()
        sig = hmac.new(b"test-shared-secret", message, hashlib.sha256).hexdigest()

        req = await self._make_request(
            path,
            method=method,
            headers={"X-Signature": sig, "X-Timestamp": now},
            body=body,
        )
        await sig_mod.verify_signature(req)  # should not raise

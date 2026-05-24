from __future__ import annotations
"""Admin FastAPI app — package management and subscription activation.

All routes require the admin token: Authorization: Bearer <admin-token>.
"""

import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from marketplace.models import ActivateRequest, MarketplacePackage
from marketplace.store import MarketplaceStore

admin = FastAPI(title="Nexus Solution Marketplace — Admin", version="1.0.0")

store = MarketplaceStore()
security = HTTPBearer(auto_error=False)
PACKAGES_DIR = Path(__file__).parent / "packages"


def require_admin(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
) -> None:
    """Verify the admin token. Raises 403 if invalid."""
    from marketplace.auth import verify_admin_token

    if credentials is None:
        raise HTTPException(status_code=403, detail="Missing admin token")
    if not verify_admin_token(credentials.credentials):
        raise HTTPException(status_code=403, detail="Invalid admin token")


# ── Package management ────────────────────────────────────────────────


@admin.post("/api/admin/packages")
async def publish_package(pkg: MarketplacePackage, _: None = Depends(require_admin)):
    """Publish (create or update) a marketplace package."""
    now = datetime.now(timezone.utc).isoformat()
    if not pkg.id:
        pkg.id = uuid.uuid4().hex
    if not pkg.created_at:
        pkg.created_at = now
    pkg.updated_at = now

    store.save_package(pkg)
    return JSONResponse(
        content={"status": "ok", "package_id": pkg.id},
        status_code=201,
    )


@admin.delete("/api/admin/packages/{package_id}")
async def delete_package(package_id: str, _: None = Depends(require_admin)):
    """Unpublish (delete) a marketplace package."""
    deleted = store.delete_package(package_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Package not found")
    return JSONResponse(content={"status": "ok", "deleted": package_id})


@admin.post("/api/admin/activate")
async def activate_subscription(
    req: ActivateRequest, _: None = Depends(require_admin)
):
    """Manually activate a subscription for a user."""
    sub = store.activate_subscription(
        user_id=req.user_id,
        package_id=req.package_id,
        plan_type=req.plan_type,
        duration_months=req.duration_months,
    )
    return JSONResponse(content=sub.model_dump(), status_code=201)

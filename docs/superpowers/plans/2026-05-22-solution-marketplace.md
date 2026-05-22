# 方案市场 — 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 构建方案市场系统 — 云端 API 提供方案目录/订阅/下载，本地 Gateway 代理转发，前端浏览和一键安装。

**Architecture:** 两个独立子系统：(A) 云服务器 `marketplace/` — FastAPI + SQLite，提供方案目录、用户认证、订阅验证、下载；(B) 本地工厂 — Gateway 代理层 (`gateway/routes/market.py`) 转发请求到云端 + React 前端组件浏览和安装方案。

**Tech Stack:** Python 3.11+, FastAPI, SQLite, Pydantic v2, httpx (代理), JWT (pyjwt), React+TypeScript+Tailwind

---

## File Structure

### 云端服务器（独立部署）

| File | Action | Responsibility |
|------|--------|---------------|
| `marketplace/__init__.py` | Create | 模块初始化 |
| `marketplace/models.py` | Create | MarketplacePackage, Subscription Pydantic 模型 |
| `marketplace/store.py` | Create | SQLite 数据存储 |
| `marketplace/auth.py` | Create | JWT 登录/注册 |
| `marketplace/api.py` | Create | FastAPI 应用（catalog, detail, download, my） |
| `marketplace/admin.py` | Create | 管理后台（发布/下架方案，手动激活订阅） |
| `marketplace/packages/` | Create | 方案 .nexus.zip 存储目录 |
| `marketplace/test_api.py` | Create | API 端到端测试 |

### 本地工厂

| File | Action | Responsibility |
|------|--------|---------------|
| `gateway/routes/market.py` | Create | 本地代理 API（转发到云端） |
| `webui/src/components/Marketplace.tsx` | Create | 方案市场前端页面 |
| `webui/src/lib/types.ts` | Modify | 追加 MarketPackage, Subscription 类型 |
| `webui/src/lib/api.ts` | Modify | 追加 market API 调用 |
| `webui/src/App.tsx` | Modify | 追加 /market 路由 |
| `gateway/server.py` | Modify | 注册 market router |

---

### Task 1: 云端 — 数据模型

**Files:**
- Create: `marketplace/__init__.py`
- Create: `marketplace/models.py`

- [ ] **Step 1: 创建 marketplace/__init__.py**

```python
"""方案市场 — 云端 API 服务。"""
```

- [ ] **Step 2: 创建 marketplace/models.py**

```python
"""Pydantic models for the solution marketplace."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class PlanType(str, Enum):
    MONTHLY = "monthly"
    YEARLY = "yearly"
    VIP = "vip"


class MarketplacePackage(BaseModel):
    """A solution package in the marketplace catalog."""

    id: str
    name: str
    description: str = ""
    long_description: str = ""
    category: str = "其他"
    tags: list[str] = Field(default_factory=list)
    author: str = ""
    version: str = "1.0.0"
    icon_url: str = ""
    screenshots: list[str] = Field(default_factory=list)
    plan_monthly_price: int = 0  # cents, 0 = unavailable
    plan_yearly_price: int = 0
    package_url: str = ""
    package_size: int = 0
    download_count: int = 0
    created_at: str = ""
    updated_at: str = ""


class Subscription(BaseModel):
    """A user's subscription/purchase record."""

    user_id: str
    package_id: str  # "vip" for VIP all-access
    plan_type: PlanType = PlanType.MONTHLY
    expires_at: str = ""
    created_at: str = ""


class UserInfo(BaseModel):
    user_id: str
    username: str
    is_vip: bool = False


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    user: UserInfo


class ActivateRequest(BaseModel):
    user_id: str
    package_id: str
    plan_type: PlanType = PlanType.MONTHLY
    duration_months: int = 1
```

- [ ] **Step 3: Commit**

```bash
git add marketplace/__init__.py marketplace/models.py
git commit -m "feat(marketplace): add Pydantic models"
```

---

### Task 2: 云端 — 数据存储

**Files:**
- Create: `marketplace/store.py`

- [ ] **Step 1: 创建 marketplace/store.py**

```python
"""SQLite-backed marketplace data store."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path

from marketplace.models import MarketplacePackage, PlanType, Subscription, UserInfo

STORE_SQL = """
CREATE TABLE IF NOT EXISTS packages (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    long_description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '其他',
    tags TEXT NOT NULL DEFAULT '[]',
    author TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    icon_url TEXT NOT NULL DEFAULT '',
    screenshots TEXT NOT NULL DEFAULT '[]',
    plan_monthly_price INTEGER NOT NULL DEFAULT 0,
    plan_yearly_price INTEGER NOT NULL DEFAULT 0,
    package_url TEXT NOT NULL DEFAULT '',
    package_size INTEGER NOT NULL DEFAULT 0,
    download_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS subscriptions (
    user_id TEXT NOT NULL,
    package_id TEXT NOT NULL,
    plan_type TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL,
    PRIMARY KEY (user_id, package_id)
);
"""


class MarketplaceStore:
    def __init__(self, db_path: str = "marketplace/marketplace.db") -> None:
        self._db_path = Path(db_path)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        import sqlite3
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        conn.executescript(STORE_SQL)
        conn.commit()
        conn.close()

    def _conn(self):
        import sqlite3
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    # ── Packages ──

    def list_packages(self, category: str = "") -> list[MarketplacePackage]:
        import json
        conn = self._conn()
        try:
            if category:
                rows = conn.execute(
                    "SELECT * FROM packages WHERE category = ? ORDER BY created_at DESC",
                    (category,),
                ).fetchall()
            else:
                rows = conn.execute(
                    "SELECT * FROM packages ORDER BY created_at DESC"
                ).fetchall()
            return [self._row_to_package(r) for r in rows]
        finally:
            conn.close()

    def get_package(self, package_id: str) -> MarketplacePackage | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM packages WHERE id = ?", (package_id,)
            ).fetchone()
            if row is None:
                return None
            return self._row_to_package(row)
        finally:
            conn.close()

    def save_package(self, pkg: MarketplacePackage) -> None:
        import json
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT 1 FROM packages WHERE id = ?", (pkg.id,)
            ).fetchone()
            if existing:
                conn.execute(
                    "UPDATE packages SET name=?, description=?, long_description=?, "
                    "category=?, tags=?, version=?, plan_monthly_price=?, "
                    "plan_yearly_price=?, package_url=?, package_size=?, "
                    "updated_at=? WHERE id=?",
                    (pkg.name, pkg.description, pkg.long_description,
                     pkg.category, json.dumps(pkg.tags, ensure_ascii=False),
                     pkg.version, pkg.plan_monthly_price, pkg.plan_yearly_price,
                     pkg.package_url, pkg.package_size, now, pkg.id),
                )
            else:
                conn.execute(
                    "INSERT INTO packages (id, name, description, long_description, "
                    "category, tags, author, version, plan_monthly_price, "
                    "plan_yearly_price, package_url, package_size, "
                    "created_at, updated_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (pkg.id, pkg.name, pkg.description, pkg.long_description,
                     pkg.category, json.dumps(pkg.tags, ensure_ascii=False),
                     pkg.author, pkg.version, pkg.plan_monthly_price,
                     pkg.plan_yearly_price, pkg.package_url, pkg.package_size,
                     pkg.created_at or now, now),
                )
            conn.commit()
        finally:
            conn.close()

    def delete_package(self, package_id: str) -> bool:
        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT 1 FROM packages WHERE id = ?", (package_id,)
            ).fetchone()
            if not existing:
                return False
            conn.execute("DELETE FROM packages WHERE id = ?", (package_id,))
            conn.commit()
            return True
        finally:
            conn.close()

    def increment_download(self, package_id: str) -> None:
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE packages SET download_count = download_count + 1 WHERE id = ?",
                (package_id,),
            )
            conn.commit()
        finally:
            conn.close()

    def _row_to_package(self, row) -> MarketplacePackage:
        import json
        return MarketplacePackage(
            id=row["id"], name=row["name"],
            description=row["description"],
            long_description=row["long_description"],
            category=row["category"],
            tags=json.loads(row["tags"]),
            author=row["author"], version=row["version"],
            icon_url=row["icon_url"],
            screenshots=json.loads(row["screenshots"]),
            plan_monthly_price=row["plan_monthly_price"],
            plan_yearly_price=row["plan_yearly_price"],
            package_url=row["package_url"],
            package_size=row["package_size"],
            download_count=row["download_count"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )

    # ── Users ──

    def create_user(self, username: str, password_hash: str) -> UserInfo | None:
        import hashlib
        now = datetime.now(timezone.utc).isoformat()
        uid = str(uuid.uuid4())[:8]
        conn = self._conn()
        try:
            conn.execute(
                "INSERT INTO users (id, username, password_hash, created_at) "
                "VALUES (?, ?, ?, ?)",
                (uid, username, password_hash, now),
            )
            conn.commit()
            return UserInfo(user_id=uid, username=username)
        except Exception:
            return None
        finally:
            conn.close()

    def get_user(self, username: str) -> dict | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM users WHERE username = ?", (username,)
            ).fetchone()
            if row is None:
                return None
            return dict(row)
        finally:
            conn.close()

    # ── Subscriptions ──

    def get_subscriptions(self, user_id: str) -> list[Subscription]:
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT * FROM subscriptions WHERE user_id = ? ORDER BY created_at DESC",
                (user_id,),
            ).fetchall()
            return [
                Subscription(
                    user_id=r["user_id"], package_id=r["package_id"],
                    plan_type=PlanType(r["plan_type"]),
                    expires_at=r["expires_at"], created_at=r["created_at"],
                )
                for r in rows
            ]
        finally:
            conn.close()

    def has_access(self, user_id: str, package_id: str) -> bool:
        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            # Check VIP
            vip = conn.execute(
                "SELECT 1 FROM subscriptions WHERE user_id = ? AND package_id = 'vip' "
                "AND expires_at > ?",
                (user_id, now.isoformat()),
            ).fetchone()
            if vip:
                return True
            # Check specific package
            sub = conn.execute(
                "SELECT 1 FROM subscriptions WHERE user_id = ? AND package_id = ? "
                "AND expires_at > ?",
                (user_id, package_id, now.isoformat()),
            ).fetchone()
            return sub is not None
        finally:
            conn.close()

    def activate_subscription(
        self, user_id: str, package_id: str, plan_type: PlanType, duration_months: int = 1
    ) -> Subscription:
        from datetime import timedelta
        now = datetime.now(timezone.utc)
        expires = now + timedelta(days=30 * duration_months)
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR REPLACE INTO subscriptions "
                "(user_id, package_id, plan_type, expires_at, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (user_id, package_id, plan_type.value,
                 expires.isoformat(), now.isoformat()),
            )
            conn.commit()
            return Subscription(
                user_id=user_id, package_id=package_id,
                plan_type=plan_type, expires_at=expires.isoformat(),
                created_at=now.isoformat(),
            )
        finally:
            conn.close()
```

- [ ] **Step 2: Commit**

```bash
git add marketplace/store.py
git commit -m "feat(marketplace): add SQLite data store"
```

---

### Task 3: 云端 — JWT 认证

**Files:**
- Create: `marketplace/auth.py`

- [ ] **Step 1: 创建 marketplace/auth.py**

```python
"""JWT authentication for the marketplace."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timezone, timedelta

import jwt

JWT_SECRET = os.environ.get("JWT_SECRET", secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_HOURS = 720  # 30 days


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    h = hashlib.sha256(f"{salt}:{password}".encode()).hexdigest()
    return f"{salt}:{h}"


def verify_password(password: str, stored_hash: str) -> bool:
    salt, h = stored_hash.split(":", 1)
    return hashlib.sha256(f"{salt}:{password}".encode()).hexdigest() == h


def create_token(user_id: str, username: str) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "user_id": user_id,
        "username": username,
        "exp": now + timedelta(hours=JWT_EXPIRE_HOURS),
        "iat": now,
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> dict | None:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.PyJWTError:
        return None
```

- [ ] **Step 2: Commit**

```bash
git add marketplace/auth.py
git commit -m "feat(marketplace): add JWT authentication"
```

---

### Task 4: 云端 — API 服务 + 管理后台

**Files:**
- Create: `marketplace/api.py`
- Create: `marketplace/admin.py`

- [ ] **Step 1: 创建 marketplace/api.py**

```python
"""方案市场 FastAPI 应用 — 面向终端用户的 API。"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse

from marketplace.models import (
    LoginRequest, RegisterRequest, TokenResponse, UserInfo,
)
from marketplace.store import MarketplaceStore
from marketplace.auth import (
    create_token, decode_token, hash_password, verify_password,
)

app = FastAPI(title="方案市场 API", version="1.0.0")
store = MarketplaceStore()


def _current_user(authorization: str = Header("")) -> dict:
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing token")
    payload = decode_token(authorization[7:])
    if payload is None:
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload


# ── Auth ──

@app.post("/api/auth/register")
async def register(body: RegisterRequest):
    if store.get_user(body.username):
        raise HTTPException(status_code=409, detail="Username taken")
    user = store.create_user(body.username, hash_password(body.password))
    if user is None:
        raise HTTPException(status_code=500, detail="Registration failed")
    token = create_token(user.user_id, user.username)
    return TokenResponse(token=token, user=user)


@app.post("/api/auth/login")
async def login(body: LoginRequest):
    row = store.get_user(body.username)
    if row is None or not verify_password(body.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    uid = row["id"]
    is_vip = store.has_access(uid, "vip")
    user = UserInfo(user_id=uid, username=body.username, is_vip=is_vip)
    token = create_token(uid, body.username)
    return TokenResponse(token=token, user=user)


@app.get("/api/auth/me")
async def me(user: dict = Header(None)):  # type: ignore[arg-type]
    payload = _current_user()
    is_vip = store.has_access(payload["user_id"], "vip")
    return UserInfo(
        user_id=payload["user_id"],
        username=payload["username"],
        is_vip=is_vip,
    )


# ── Catalog ──

@app.get("/api/catalog")
async def catalog(category: str = ""):
    packages = store.list_packages(category=category)
    return JSONResponse(content=[p.model_dump() for p in packages])


@app.get("/api/packages/{package_id}")
async def package_detail(package_id: str):
    pkg = store.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    return JSONResponse(content=pkg.model_dump())


# ── Download ──

@app.get("/api/packages/{package_id}/download")
async def download_package(package_id: str, user: dict = Header(None)):  # type: ignore[arg-type]
    payload = _current_user()
    if not store.has_access(payload["user_id"], package_id):
        raise HTTPException(status_code=403, detail="No subscription")
    pkg = store.get_package(package_id)
    if pkg is None:
        raise HTTPException(status_code=404, detail="Package not found")
    filepath = pkg.package_url
    store.increment_download(package_id)
    return FileResponse(filepath, media_type="application/zip",
                        filename=f"{pkg.name}.nexus.zip")


# ── My purchases ──

@app.get("/api/my")
async def my_purchases(user: dict = Header(None)):  # type: ignore[arg-type]
    payload = _current_user()
    subs = store.get_subscriptions(payload["user_id"])
    result = []
    for sub in subs:
        pkg = store.get_package(sub.package_id) if sub.package_id != "vip" else None
        result.append({
            "package_id": sub.package_id,
            "plan_type": sub.plan_type.value,
            "expires_at": sub.expires_at,
            "created_at": sub.created_at,
            "name": pkg.name if pkg else "VIP 包年",
            "category": pkg.category if pkg else "",
            "version": pkg.version if pkg else "",
        })
    return JSONResponse(content=result)
```

- [ ] **Step 2: 创建 marketplace/admin.py**

```python
"""方案市场管理后台 API — 发布/管理方案，手动激活订阅。"""

from __future__ import annotations

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse

from marketplace.models import (
    ActivateRequest, MarketplacePackage, PlanType,
)
from marketplace.store import MarketplaceStore

admin = FastAPI(title="方案市场管理后台", version="1.0.0")
store = MarketplaceStore()

ADMIN_TOKEN = "nexus-admin-secret"  # V1: hardcoded, V2: env var


def _admin_only(authorization: str = Header("")) -> None:
    if not authorization.startswith("Bearer ") or authorization[7:] != ADMIN_TOKEN:
        raise HTTPException(status_code=403, detail="Forbidden")


# ── Package management ──

@admin.post("/api/admin/packages")
async def publish_package(pkg: MarketplacePackage, authorization: str = Header("")):
    _admin_only(authorization)
    store.save_package(pkg)
    return JSONResponse(content=pkg.model_dump(), status_code=201)


@admin.delete("/api/admin/packages/{package_id}")
async def unpublish_package(package_id: str, authorization: str = Header("")):
    _admin_only(authorization)
    ok = store.delete_package(package_id)
    if not ok:
        raise HTTPException(status_code=404, detail="Not found")
    return JSONResponse(content={"deleted": package_id})


# ── Manual subscription activation ──

@admin.post("/api/admin/activate")
async def activate_subscription(body: ActivateRequest, authorization: str = Header("")):
    _admin_only(authorization)
    sub = store.activate_subscription(
        body.user_id, body.package_id, body.plan_type, body.duration_months,
    )
    return JSONResponse(content=sub.model_dump())
```

- [ ] **Step 3: 创建 packages 目录**

```bash
mkdir -p marketplace/packages
```

- [ ] **Step 4: 创建 marketplace 启动入口**

Create `marketplace/main.py`:
```python
"""Run marketplace API + admin in one process."""

from marketplace.api import app
from marketplace.admin import admin

# Mount admin routes under /admin prefix
app.mount("/admin", admin)

# Run: uvicorn marketplace.main:app --port 8800
```

- [ ] **Step 5: Commit**

```bash
git add marketplace/api.py marketplace/admin.py marketplace/main.py marketplace/packages/
git commit -m "feat(marketplace): add API and admin backend"
```

---

### Task 5: 云端 — API 测试

**Files:**
- Create: `marketplace/test_api.py`

- [ ] **Step 1: 创建 marketplace/test_api.py**

```python
"""Integration tests for marketplace API."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from marketplace.api import app
from marketplace.store import MarketplaceStore


@pytest.fixture(autouse=True)
def fresh_store(tmp_path, monkeypatch):
    """Each test gets a fresh in-memory database."""
    import marketplace.store as ms
    monkeypatch.setattr(ms, "MarketplaceStore", lambda: MarketplaceStore(
        str(tmp_path / "test_marketplace.db")
    ))


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _register(client) -> tuple[str, str]:
    resp = await client.post("/api/auth/register", json={
        "username": "u_" + str(id(client)), "password": "test",
    })
    data = resp.json()
    return (data["user"]["username"], data["token"])


class TestCatalog:
    async def test_catalog_empty(self, client):
        resp = await client.get("/api/catalog")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_catalog_with_packages(self, client, fresh_store):
        from marketplace.store import MarketplaceStore
        from marketplace.models import MarketplacePackage
        s = MarketplaceStore()
        s.save_package(MarketplacePackage(
            id="p1", name="市场调研方案", description="深度市场分析",
            category="市场分析", author="Nexus AI", version="1.0.0",
            plan_monthly_price=9900, plan_yearly_price=99000,
        ))
        s.save_package(MarketplacePackage(
            id="p2", name="代码审查方案", description="自动代码审查",
            category="代码工具", plan_monthly_price=19900,
        ))
        resp = await client.get("/api/catalog")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 2

    async def test_catalog_category_filter(self, client, fresh_store):
        from marketplace.store import MarketplaceStore
        from marketplace.models import MarketplacePackage
        s = MarketplaceStore()
        s.save_package(MarketplacePackage(
            id="p1", name="p1", category="市场分析",
        ))
        s.save_package(MarketplacePackage(
            id="p2", name="p2", category="代码工具",
        ))
        resp = await client.get("/api/catalog?category=代码工具")
        data = resp.json()
        assert len(data) == 1
        assert data[0]["name"] == "p2"


class TestAuth:
    async def test_register_and_login(self, client):
        resp = await client.post("/api/auth/register", json={
            "username": "testuser", "password": "testpass",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["username"] == "testuser"

    async def test_login_invalid(self, client):
        resp = await client.post("/api/auth/login", json={
            "username": "noone", "password": "bad",
        })
        assert resp.status_code == 401


class TestDownload:
    async def test_download_without_subscription(self, client, fresh_store):
        from marketplace.store import MarketplaceStore
        from marketplace.models import MarketplacePackage
        s = MarketplaceStore()
        s.save_package(MarketplacePackage(
            id="p1", name="test", package_url="/dev/null",
        ))
        # Register and login
        resp = await client.post("/api/auth/register", json={
            "username": "u", "password": "p",
        })
        token = resp.json()["token"]
        # Try download without subscription
        resp = await client.get(
            "/api/packages/p1/download",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert resp.status_code == 403
```

- [ ] **Step 2: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest marketplace/test_api.py -v --tb=short`
Expected: 6+ tests pass

- [ ] **Step 3: Commit**

```bash
git add marketplace/test_api.py
git commit -m "test(marketplace): add API integration tests"
```

---

### Task 6: 本地 — 代理 API 路由

**Files:**
- Create: `gateway/routes/market.py`
- Modify: `gateway/server.py`

- [ ] **Step 1: 创建 gateway/routes/market.py**

```python
"""方案市场本地代理 — 转发请求到云端 API。

配置由 MARKETPLACE_API_URL 环境变量指定云端地址。
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(prefix="/api/market", tags=["market"])

CLOUD_URL = os.environ.get("MARKETPLACE_API_URL", "http://127.0.0.1:8800")


async def _proxy(request: Request, path: str, method: str = "GET"):
    """Forward request to cloud API, return JSON."""
    url = f"{CLOUD_URL}{path}"
    headers = {}
    auth = request.headers.get("Authorization", "")
    if auth:
        headers["Authorization"] = auth
    async with httpx.AsyncClient(timeout=30.0) as client:
        if method == "POST":
            body = await request.json()
            resp = await client.post(url, json=body, headers=headers)
        elif method == "DELETE":
            resp = await client.delete(url, headers=headers)
        else:
            params = dict(request.query_params)
            resp = await client.get(url, params=params, headers=headers)
        return JSONResponse(content=resp.json(), status_code=resp.status_code)


@router.get("/catalog")
async def catalog(request: Request):
    return await _proxy(request, "/api/catalog")


@router.get("/packages/{package_id}")
async def package_detail(package_id: str, request: Request):
    return await _proxy(request, f"/api/packages/{package_id}")


@router.get("/my")
async def my_purchases(request: Request):
    return await _proxy(request, "/api/my")


@router.post("/auth/login")
async def login(request: Request):
    return await _proxy(request, "/api/auth/login", method="POST")


@router.post("/auth/register")
async def register(request: Request):
    return await _proxy(request, "/api/auth/register", method="POST")


@router.get("/auth/me")
async def me(request: Request):
    return await _proxy(request, "/api/auth/me")


@router.post("/packages/{package_id}/install")
async def install_package(package_id: str, request: Request):
    """Download .nexus.zip from cloud and install locally."""
    from factory.workshop.manager import WorkshopManager
    from factory.kanban import KanbanStore

    org = request.app.state.org
    kanban_store = request.app.state.kanban_store

    # 1. Download from cloud
    auth = request.headers.get("Authorization", "")
    url = f"{CLOUD_URL}/api/packages/{package_id}/download"
    async with httpx.AsyncClient(timeout=120.0) as client:
        headers = {}
        if auth:
            headers["Authorization"] = auth
        resp = await client.get(url, headers=headers)
        if resp.status_code != 200:
            detail = "Download failed"
            try:
                detail = resp.json().get("detail", detail)
            except Exception:
                pass
            return JSONResponse(content={"detail": detail}, status_code=resp.status_code)

        # 2. Save to temp file
        with tempfile.NamedTemporaryFile(suffix=".nexus.zip", delete=False) as tmp:
            tmp.write(resp.content)
            tmp_path = Path(tmp.name)

    # 3. Extract and import
    import zipfile
    pkg_dir = tmp_path.parent / f"market_install_{package_id}"
    pkg_dir.mkdir(exist_ok=True)
    try:
        with zipfile.ZipFile(tmp_path, "r") as zf:
            zf.extractall(pkg_dir)

        mgr = WorkshopManager(org, kanban_store)
        result = mgr.import_package(str(pkg_dir))
        if result is None:
            return JSONResponse(
                content={"detail": "Import failed (workspace may already exist)"},
                status_code=409,
            )
        return JSONResponse(content=result, status_code=201)
    finally:
        tmp_path.unlink(missing_ok=True)
        import shutil
        shutil.rmtree(pkg_dir, ignore_errors=True)
```

- [ ] **Step 2: 注册 router 到 gateway/server.py**

在 `gateway/server.py` imports 区追加：
```python
from gateway.routes.market import router as market_router
```

在 `app.include_router(ws_router)` 后追加：
```python
    app.include_router(market_router)
```

在 CSRF skip_paths 中追加 `/api/market/`：
```python
skip_paths=(
    ...
    "/api/market/",
),
```

- [ ] **Step 3: Commit**

```bash
git add gateway/routes/market.py gateway/server.py
git commit -m "feat(marketplace): add local proxy routes"
```

---

### Task 7: 前端 — 方案市场组件

**Files:**
- Modify: `webui/src/lib/types.ts`
- Modify: `webui/src/lib/api.ts`
- Create: `webui/src/components/Marketplace.tsx`
- Modify: `webui/src/App.tsx`

- [ ] **Step 1: 追加类型到 webui/src/lib/types.ts**

```typescript
export interface MarketPackage {
  id: string;
  name: string;
  description: string;
  long_description: string;
  category: string;
  tags: string[];
  author: string;
  version: string;
  icon_url: string;
  screenshots: string[];
  plan_monthly_price: number;
  plan_yearly_price: number;
  package_size: number;
  download_count: number;
  created_at: string;
  updated_at: string;
}

export interface MarketSubscription {
  package_id: string;
  plan_type: string;
  expires_at: string;
  created_at: string;
  name: string;
  category: string;
  version: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
  is_vip: boolean;
}
```

- [ ] **Step 2: 追加 API 方法到 webui/src/lib/api.ts**

```typescript
  // ── Marketplace ──
  marketCatalog: (category?: string) =>
    get<MarketPackage[]>(`/market/catalog?category=${encodeURIComponent(category || "")}`),
  marketPackage: (id: string) =>
    get<MarketPackage>(`/market/packages/${id}`),
  marketInstall: (id: string, token: string) =>
    post<Record<string, unknown>>(`/market/packages/${id}/install`, {}, token),
  marketMy: (token: string) =>
    get<MarketSubscription[]>("/market/my", token),
  marketLogin: (username: string, password: string) =>
    post<{ token: string; user: UserInfo }>("/market/auth/login", { username, password }),
  marketRegister: (username: string, password: string) =>
    post<{ token: string; user: UserInfo }>("/market/auth/register", { username, password }),
```

需要给 `get` 和 `post` 函数加一个可选的 auth token 参数（追加到 headers）。

更新 `get`:
```typescript
async function get<T>(url: string, authToken?: string): Promise<T> {
  const headers: Record<string, string> = {};
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(`${BASE}${url}`, { credentials: "include", headers });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
```

更新 `post`:
```typescript
async function post<T>(url: string, body: unknown, authToken?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...csrfHeaders() };
  if (authToken) headers["Authorization"] = `Bearer ${authToken}`;
  const res = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}
```

- [ ] **Step 3: 创建 webui/src/components/Marketplace.tsx**

```tsx
import { useState, useEffect } from "react";
import { api } from "../lib/api";
import type { MarketPackage, MarketSubscription, UserInfo } from "../lib/types";

const CATEGORIES = [
  "全部", "市场分析", "内容创作", "代码工具", "数据处理",
  "法务合规", "营销推广", "客服支持", "项目管理",
  "金融分析", "教育培训", "医疗健康", "其他",
];

export function Marketplace() {
  const [packages, setPackages] = useState<MarketPackage[]>([]);
  const [selected, setSelected] = useState<MarketPackage | null>(null);
  const [category, setCategory] = useState("全部");
  const [loading, setLoading] = useState(false);
  const [user, setUser] = useState<UserInfo | null>(null);
  const [token, setToken] = useState(localStorage.getItem("market_token") || "");
  const [mySubs, setMySubs] = useState<MarketSubscription[]>([]);
  const [tab, setTab] = useState<"browse" | "my">("browse");
  const [loginOpen, setLoginOpen] = useState(false);
  const [loginUser, setLoginUser] = useState("");
  const [loginPass, setLoginPass] = useState("");

  // Restore auth on mount
  useEffect(() => {
    if (token) {
      api.marketLogin("", "").catch(() => {}); // warm up
    }
  }, []);

  const loadCatalog = async () => {
    setLoading(true);
    try {
      const cat = category === "全部" ? "" : category;
      const data = await api.marketCatalog(cat);
      setPackages(data);
    } catch { setPackages([]); }
    finally { setLoading(false); }
  };

  useEffect(() => { loadCatalog(); }, [category]);

  const loadMy = async () => {
    if (!token) return;
    try {
      const data = await api.marketMy(token);
      setMySubs(data);
    } catch { setMySubs([]); }
  };

  useEffect(() => { if (tab === "my") loadMy(); }, [tab, token]);

  const handleLogin = async () => {
    try {
      const resp = await api.marketLogin(loginUser, loginPass);
      setToken(resp.token);
      setUser(resp.user);
      localStorage.setItem("market_token", resp.token);
      setLoginOpen(false);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert("登录失败: " + msg);
    }
  };

  const handleInstall = async (pkg: MarketPackage) => {
    if (!token) { setLoginOpen(true); return; }
    try {
      await api.marketInstall(pkg.id, token);
      alert(`方案「${pkg.name}」安装成功！`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert("安装失败: " + msg);
    }
  };

  const hasAccess = (pkgId: string) =>
    mySubs.some(s => s.package_id === pkgId || s.package_id === "vip");

  const fmtPrice = (cents: number) =>
    cents === 0 ? "—" : `¥${(cents / 100).toFixed(0)}`;

  return (
    <div className="p-6 max-w-6xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">方案市场</h1>
        <div className="flex items-center gap-4">
          <div className="flex gap-1 bg-zinc-900 rounded-lg p-1">
            <button
              onClick={() => setTab("browse")}
              className={`px-3 py-1.5 rounded text-sm ${tab === "browse" ? "bg-amber-500 text-black" : "text-zinc-400"}`}
            >浏览</button>
            <button
              onClick={() => setTab("my")}
              className={`px-3 py-1.5 rounded text-sm ${tab === "my" ? "bg-amber-500 text-black" : "text-zinc-400"}`}
            >我的</button>
          </div>
          {token ? (
            <span className="text-sm text-zinc-400">
              {user?.username || "已登录"}
              {user?.is_vip && <span className="ml-2 px-2 py-0.5 bg-amber-500/20 text-amber-400 rounded text-xs">VIP</span>}
            </span>
          ) : (
            <button
              onClick={() => setLoginOpen(true)}
              className="text-sm px-3 py-1.5 bg-zinc-800 text-white rounded-lg hover:bg-zinc-700"
            >登录</button>
          )}
        </div>
      </div>

      {/* Login modal */}
      {loginOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-zinc-900 p-6 rounded-xl border border-zinc-700 w-80">
            <h2 className="text-lg font-bold mb-4">登录方案市场</h2>
            <input
              type="text" placeholder="用户名" value={loginUser}
              onChange={e => setLoginUser(e.target.value)}
              className="w-full px-3 py-2 mb-2 bg-zinc-800 border border-zinc-700 rounded text-white text-sm"
            />
            <input
              type="password" placeholder="密码" value={loginPass}
              onChange={e => setLoginPass(e.target.value)}
              className="w-full px-3 py-2 mb-4 bg-zinc-800 border border-zinc-700 rounded text-white text-sm"
            />
            <div className="flex gap-2">
              <button onClick={handleLogin}
                className="flex-1 py-2 bg-amber-500 text-black rounded font-medium text-sm">登录</button>
              <button onClick={() => setLoginOpen(false)}
                className="flex-1 py-2 bg-zinc-800 text-zinc-400 rounded text-sm">取消</button>
            </div>
          </div>
        </div>
      )}

      {tab === "browse" && (
        <>
          {/* Category tabs */}
          <div className="flex gap-1 flex-wrap mb-4">
            {CATEGORIES.map(c => (
              <button key={c}
                onClick={() => setCategory(c)}
                className={`px-3 py-1 rounded-full text-xs ${category === c ? "bg-amber-500/20 text-amber-400" : "bg-zinc-800 text-zinc-400 hover:text-white"}`}
              >{c}</button>
            ))}
          </div>

          {/* Package grid */}
          {loading ? (
            <p className="text-zinc-500">加载中...</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
              {packages.map(pkg => (
                <div key={pkg.id}
                  className="p-4 rounded-lg border border-zinc-800 bg-zinc-900 hover:border-zinc-700 cursor-pointer transition-colors"
                  onClick={() => setSelected(pkg)}>
                  <h3 className="font-medium text-white mb-1">{pkg.name}</h3>
                  <p className="text-sm text-zinc-400 mb-2 line-clamp-2">{pkg.description}</p>
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-zinc-500">{pkg.author} · v{pkg.version}</span>
                    <div className="text-xs">
                      {pkg.plan_monthly_price > 0 && (
                        <span className="text-amber-400">{fmtPrice(pkg.plan_monthly_price)}/月</span>
                      )}
                      {pkg.plan_yearly_price > 0 && (
                        <span className="text-amber-400 ml-2">{fmtPrice(pkg.plan_yearly_price)}/年</span>
                      )}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Package detail */}
          {selected && (
            <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
              <div className="bg-zinc-900 rounded-xl border border-zinc-700 max-w-lg w-full mx-4 max-h-[80vh] overflow-y-auto">
                <div className="p-6">
                  <h2 className="text-xl font-bold text-white mb-1">{selected.name}</h2>
                  <p className="text-sm text-zinc-500 mb-4">{selected.author} · v{selected.version} · {selected.download_count} 次下载</p>
                  <p className="text-sm text-zinc-300 mb-4 whitespace-pre-wrap">{selected.long_description || selected.description}</p>
                  {selected.tags.length > 0 && (
                    <div className="flex gap-1 flex-wrap mb-4">
                      {selected.tags.map(t => (
                        <span key={t} className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{t}</span>
                      ))}
                    </div>
                  )}
                  <div className="mb-4 space-y-1 text-sm text-zinc-400">
                    {selected.plan_monthly_price > 0 && (
                      <p>月付: <span className="text-amber-400 font-medium">{fmtPrice(selected.plan_monthly_price)}/月</span></p>
                    )}
                    {selected.plan_yearly_price > 0 && (
                      <p>年付: <span className="text-amber-400 font-medium">{fmtPrice(selected.plan_yearly_price)}/年</span></p>
                    )}
                    <p className="text-xs text-zinc-500">包大小: {(selected.package_size / 1024).toFixed(1)} KB</p>
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={() => handleInstall(selected)}
                      className="flex-1 py-2 bg-amber-500 text-black rounded-lg font-medium text-sm hover:bg-amber-400"
                    >
                      {hasAccess(selected.id) ? "安装" : "购买并安装"}
                    </button>
                    <button
                      onClick={() => setSelected(null)}
                      className="py-2 px-4 bg-zinc-800 text-zinc-400 rounded-lg text-sm"
                    >关闭</button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {tab === "my" && (
        <div className="space-y-3">
          {mySubs.length === 0 ? (
            <p className="text-zinc-500">暂无已购方案。登录后查看订阅。</p>
          ) : (
            mySubs.map(sub => (
              <div key={sub.package_id + sub.plan_type}
                className="p-4 rounded-lg border border-zinc-800 bg-zinc-900">
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{sub.name}</span>
                  <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">{sub.plan_type}</span>
                </div>
                <p className="text-xs text-zinc-500 mt-1">
                  到期: {new Date(sub.expires_at).toLocaleDateString("zh-CN")}
                </p>
              </div>
            ))
          )}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: 追加路由到 App.tsx**

在 `webui/src/App.tsx` imports:
```tsx
import { Marketplace } from "./components/Marketplace";
```

在 Routes 中追加:
```tsx
<Route path="/market" element={<ErrorBoundary><Marketplace /></ErrorBoundary>} />
```

- [ ] **Step 5: TypeScript 编译检查**

Run: `cd /Users/linhan/ai-factory/webui && ./node_modules/.bin/tsc --noEmit 2>&1 | grep -E 'Marketplace|market\.ts|types\.ts|api\.ts|App\.tsx' || echo "No new errors"`
Expected: No errors

- [ ] **Step 6: Commit**

```bash
git add webui/src/lib/types.ts webui/src/lib/api.ts webui/src/components/Marketplace.tsx webui/src/App.tsx
git commit -m "feat(marketplace): add Marketplace frontend component"
```

---

### Task 8: 最终验证

- [ ] **Step 1: 运行全量测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ marketplace/ --tb=short 2>&1 | tail -5`
Expected: all tests pass

- [ ] **Step 2: 启动云端服务（手动）**

```bash
cd /Users/linhan/ai-factory
pip install pyjwt httpx
uvicorn marketplace.main:app --port 8800 &
```

- [ ] **Step 3: 验证云端 API**

```bash
curl http://127.0.0.1:8800/api/catalog
# Expected: {"detail":"Not Found"} or []

# 通过 admin 发布一个测试方案
curl -X POST http://127.0.0.1:8800/admin/api/admin/packages \
  -H "Authorization: Bearer nexus-admin-secret" \
  -H "Content-Type: application/json" \
  -d '{"id":"test-1","name":"测试方案","description":"用于验证安装流程","category":"代码工具","tags":["test"],"author":"admin","plan_monthly_price":9900,"package_url":"/dev/null"}'

# 查看目录
curl http://127.0.0.1:8800/api/catalog
# Expected: [{"id":"test-1","name":"测试方案",...}]
```

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "feat(marketplace): complete solution marketplace implementation"
```

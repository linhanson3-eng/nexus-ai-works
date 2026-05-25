# Agor 对齐升级方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将 ai-factory 的核心基础设施从 Agent 对平台上下文无感知的私有调用模式，升级为 MCP 协议 (Agent-to-Platform 双向通信) + git worktree 工作单元 + fork/spawn 会话树

**Architecture:** 三层渐进升级 — MCP Server 给本地 Agent 提供平台感知能力 (看板/工作流/session)，Worktree Manager 替代 Path 目录的 Workshop 底座，Session Tree 替代线性 RunSnapshot。每层独立上线，互不阻塞。全程 localhost，所有 Agent 保持为本地 Claude 实例。

**Tech Stack:** Python 3.11+ FastAPI + MCP SDK (Python) + git worktree + React Flow (前端会话树)

---

## 改造总览

```
现在                                  升级后

Agent 接入: bridge.py direct call  →  gateway/mcp/ server (JSON-RPC 2.0 + JWT)
工作单元:   Path 目录 isolation     →  git worktree (分支 + 目录 + 端口哈希)
会话历史:   RunSnapshot (线性)      →  SessionNode (树形 fork/spawn/btw)
```

### 实施顺序

最优路径 (按杠杆从高到低):

```
Phase 0 (MCP Server) → Phase 2 (Session Tree) → Phase 1 (Worktree)
```

理由:
- MCP Server 让 Agent 获得自编排能力 (最大杠杆)
- Session Tree 让编排结果有结构 (非线性会话历史)
- Worktree 是底座优化 (git 隔离)，前两个没做完时意义不大

### Phase 0: MCP Server (最大杠杆, 3-5 天)

### Phase 1: Worktree Manager (git 原生底座, 2-3 天) *(调整到 Phase 2 之后)*

### Phase 2: Session Tree (非线性会话 + btw, 3-4 天)

---

## Phase 0: MCP Server

### 现状与目标

**现状**: `factory/engine/bridge.py` 是整个系统唯一被允许 import `factory.vendor.claw_code_agent` 的模块。`NexusAgentRunner` 通过 `AgentLoopEngine` 直接调用 LocalCodingAgent。所有 Agent 都是本地 Claude 实例 (claw-code-agent)，不走外部网络。但 Agent 与平台的通信是私有协议——Agent 不知道自己运行在哪个 Workshop、看板上有什么、能不能 spawn 子任务。

**目标**: 在 Gateway 层新增 MCP Server (JSON-RPC 2.0, localhost:8600/mcp)，ai-factory 自身暴露为 MCP tools。Agent 通过本地 MCP endpoint 感知平台上下文 (看板状态、工作流进度、其他 session)、spawn 子任务、写回结果。所有 Agent 仍是本地 Claude 实例，不依赖任何外部 AI 服务。

```
现在:                                          MCP 后:

Agent (本地 Claude)                           Agent (本地 Claude)
  │                                              │
  ├── bridge.py → claw-code-agent.run()           ├── 通过 MCP tool 读看板状态
  │                                              ├── 通过 MCP tool spawn 子任务
  └── Agent 不知道自己跑在哪个 Workshop          ├── 通过 MCP tool 查其他 session
     Agent 不知道看板上有什么                     │
     Agent 不能 spawn 子任务                       └── bridge.py → claw-code-agent.run()
                                                    (本地 Agent 执行不变，MCP 是平台感知层)
```

**关键约束**: 全程 `localhost`，不走任何外部网络。Agent 都是本地 Claude 实例。MCP Server 是 Agent 与 ai-factory 平台之间的本地协议层，不是外部 API 网关。

### 架构决策

**MCP Server 放在 gateway/ 而不是独立的 daemon**。原因:
1. ai-factory 已有 FastAPI gateway + session + auth 体系
2. 不需要像 Agor 那样再跑一个 FeathersJS daemon
3. MCP transport 用 streamable HTTP (POST /mcp + Authorization: Bearer <JWT>)，复用 gateway 的安全中间件

### 文件结构

```
gateway/mcp/                    ← 新增 MCP Server 模块
├── __init__.py
├── server.py                   ← FastAPI 子路由，MCP endpoint
├── tools.py                    ← MCP tool 定义 (run_agent, read_board, spawn_session, etc.)
├── auth.py                     ← session-scoped MCP token 签发/验证
└── test_server.py              ← MCP Server 测试

gateway/routes/agent.py         ← 修改：内部调用路径从 bridge → MCP tool
factory/engine/bridge.py        ← 保留兼容 (现有 claw-code-agent 后端仍可用)
factory/runner.py               ← 不变 (MCP tool 调用同一 runner)
```

### Task 0.1: MCP Token (PyJWT + kid 支持 + 自动清理)

**设计修正 (v2 review):**

| 问题 | v1 错误 | v2 修正 |
|------|---------|---------|
| 手写 JWT | 20 行手写 HMAC + `rstrip(b"=")` 去 padding | `pip install pyjwt`，一行 `jwt.encode()` |
| secret 硬编码 | `"nexus-mcp-secret-change-in-production"` | 启动时强制检查环境变量，缺省拒绝启动 |
| kid 缺失 | 无法做 key rotation | kid 嵌入 JWT header |
| 内存泄漏 | `_use_counts` dict 永不过期 | `verify()` 时顺带清理过期条目 |

**Files:**
- Create: `gateway/mcp/__init__.py`
- Create: `gateway/mcp/auth.py`
- Test: `gateway/mcp/test_server.py`

- [ ] **Step 1: 安装依赖**

```bash
pip install pyjwt
```

- [ ] **Step 2: 写失败测试**

```python
# gateway/mcp/test_server.py
from __future__ import annotations

import time
import pytest
from gateway.mcp.auth import MCPTokenManager


def test_issue_and_verify_jwt_token():
    mgr = MCPTokenManager(secret="test-secret-key-for-mcp", kid="k1")

    token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
    parts = token.split(".")
    assert len(parts) == 3  # standard JWT

    payload = mgr.verify(token)
    assert payload is not None
    assert payload["session_id"] == "sess-abc"
    assert payload["workshop_name"] == "demo"
    assert payload["iss"] == "ai-factory"


def test_expired_token_returns_none():
    mgr = MCPTokenManager(secret="test-secret", ttl_seconds=-1)
    token = mgr.issue(user_id="user-1", session_id="sess-expired", workshop_name="demo")
    assert mgr.verify(token) is None


def test_tampered_token_returns_none():
    mgr = MCPTokenManager(secret="test-secret")
    token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
    tampered = token[:-5] + "xxxxx"
    assert mgr.verify(tampered) is None


def test_max_uses_default_1():
    mgr = MCPTokenManager(secret="test-secret", max_uses=1)
    token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
    assert mgr.verify(token) is not None  # first use ok
    assert mgr.verify(token) is None      # second use denied


def test_max_uses_custom():
    mgr = MCPTokenManager(secret="test-secret", max_uses=3)
    token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
    for _ in range(3):
        assert mgr.verify(token) is not None
    assert mgr.verify(token) is None  # 4th use exceeded


def test_revoke_token():
    mgr = MCPTokenManager(secret="test-secret")
    token = mgr.issue(user_id="user-1", session_id="sess-abc", workshop_name="demo")
    assert mgr.verify(token) is not None
    jti = mgr.verify(token)["jti"]  # re-verify to get jti (first use consumed it)
    # Issue new, get jti from payload
    token2 = mgr.issue(user_id="user-1", session_id="sess-xyz", workshop_name="demo")
    payload2 = mgr.verify(token2)
    mgr.revoke(payload2["jti"])
    assert mgr.verify(token2) is None  # revoked


def test_use_counts_cleanup():
    """Verify that stale _use_counts entries can be cleaned up."""
    mgr = MCPTokenManager(secret="test-secret", ttl_seconds=0, max_uses=5)
    for i in range(10):
        token = mgr.issue(user_id="u1", session_id=f"sess-{i}", workshop_name="demo")
        mgr.verify(token)  # Each fails (ttl=0) but still records use_count
    # Manual cleanup of expired entries
    mgr._cleanup_stale()
    assert len(mgr._use_counts) == 0
```

- [ ] **Step 3: 运行测试验证失败**

```bash
python3 -m pytest gateway/mcp/test_server.py -v
# Expected: FAIL — ModuleNotFoundError
```

- [ ] **Step 4: 实现 PyJWT + kid + 自动清理**

```python
# gateway/mcp/__init__.py
from __future__ import annotations

"""MCP Server module — exposes ai-factory as MCP tools for local Agent instances."""
```

```python
# gateway/mcp/auth.py
from __future__ import annotations

import logging
import os
import time
import uuid
from typing import Any

import jwt

logger = logging.getLogger(__name__)


class MCPTokenManager:
    """Issue and verify session-scoped MCP tokens using standard PyJWT.

    Key features:
    - HS256 JWT with kid in header (enables future key rotation)
    - max_uses tracking to prevent token reuse
    - Automatic cleanup of stale use_counts on verify()
    - Secret enforced from env var at startup
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
        self._use_expiry: dict[str, int] = {}  # jti → exp timestamp
        self._last_cleanup: float = time.monotonic()  # for 60s fallback cleanup

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
        # Periodic cleanup of stale entries (every 100th call OR every 60s)
        self._maybe_cleanup()

        try:
            payload = jwt.decode(
                token, self._secret, algorithms=["HS256"],
                audience="ai-factory", issuer="ai-factory",
                options={"require": ["exp", "jti", "sub"]},
            )
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError as exc:
            logger.debug("JWT verification failed: %s", exc)
            return None

        # Check max_uses
        jti = payload.get("jti", "")
        if jti:
            count = self._use_counts.get(jti, 0)
            if count >= self._max_uses:
                return None
            self._use_counts[jti] = count + 1
            self._use_expiry[jti] = payload.get("exp", 0)

        return payload

    def revoke(self, jti: str) -> None:
        """Immediately revoke a token by jti."""
        self._use_counts[jti] = self._max_uses  # Force max_uses exceeded

    def _maybe_cleanup(self) -> None:
        """Trigger cleanup every 100 calls OR every 60 seconds (for low-traffic systems)."""
        now = time.monotonic()
        count = len(self._use_counts)
        if count > 0 and (count % 100 == 0 or now - self._last_cleanup > 60):
            self._cleanup_stale()
            self._last_cleanup = now

    def _cleanup_stale(self) -> None:
        """Remove expired entries from _use_counts."""
        now = int(time.time())
        stale = [jti for jti, exp in self._use_expiry.items() if exp < now]
        for jti in stale:
            self._use_counts.pop(jti, None)
            self._use_expiry.pop(jti, None)
        if stale:
            logger.debug("Cleaned up %d stale token entries", len(stale))
```

- [ ] **Step 5: 运行测试**

```bash
python3 -m pytest gateway/mcp/test_server.py -v
# Expected: 7 PASSED
```

- [ ] **Step 6: 提交**

```bash
git add gateway/mcp/__init__.py gateway/mcp/auth.py gateway/mcp/test_server.py
git commit -m "feat: MCP JWT token — PyJWT + kid + auto-cleanup + revocation"
```

### Task 0.2: MCP Server (rate-limit + body-limit + audit + health + revocation + isError)

**生产必备清单 (v2 review 新增):**

| 能力 | 为什么必需 |
|------|-----------|
| Body size limit (1MB) | 防止 `await request.json()` 内存爆炸 |
| Per-token rate limit (10 req/s) | 防止 Agent loop 打穿连接 |
| 结构化审计日志 | 无日志 = 生产出 Bug 查不了 |
| Token 吊销端点 | Token 泄露必须能立即废掉 |
| 健康检查 `GET /mcp/health` | daemon 挂了 Agent 需要知道 |
| `isError: true` 标准化错误 | Agent 需 programmatic 区分错误类型 |

**Files:**
- Create: `gateway/mcp/tools.py`
- Create: `gateway/mcp/server.py`
- Modify: `gateway/server.py`

- [ ] **Step 1: 实现 server.py — 全功能 MCP endpoint**

```python
# gateway/mcp/server.py
from __future__ import annotations

"""MCP Server — production-grade JSON-RPC 2.0 endpoint.

Transport: POST /mcp with Authorization: Bearer <JWT>
Rate limit: 10 req/s per token (token bucket)
Body limit: 1 MB
"""

import asyncio
import json
import logging
import os
import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from gateway.mcp.auth import MCPTokenManager
from gateway.mcp.tools import TOOL_DEFINITIONS, execute_tool

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/mcp", tags=["mcp"])

MCP_SECRET = os.environ.get("MCP_TOKEN_SECRET", "")
if not MCP_SECRET:
    raise RuntimeError(
        "MCP_TOKEN_SECRET environment variable is required. "
        "Generate: python3 -c 'import secrets; print(secrets.token_hex(32))'"
    )
_token_manager = MCPTokenManager(secret=MCP_SECRET)

MCP_MAX_BODY_BYTES = int(os.environ.get("MCP_MAX_BODY_BYTES", 1_048_576))  # 1 MB
MCP_RATE_LIMIT_RPS = float(os.environ.get("MCP_RATE_LIMIT_RPS", 10.0))      # 10 req/s


# ── Rate limiter (token bucket, per-session, concurrent-safe) ──────

class TokenBucket:
    """Concurrent-safe token bucket with asyncio.Lock per bucket."""

    def __init__(self, rate: float, burst: int = 5):
        self._rate = rate
        self._burst = burst
        self._tokens = float(burst)
        self._last = time.monotonic()
        self._lock = asyncio.Lock()
        self._last_access = time.monotonic()

    async def consume(self) -> bool:
        async with self._lock:
            now = time.monotonic()
            elapsed = now - self._last
            self._tokens = min(self._burst, self._tokens + elapsed * self._rate)
            self._last = now
            self._last_access = now
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    @property
    def idle_seconds(self) -> float:
        return time.monotonic() - self._last_access


_rate_buckets: dict[str, TokenBucket] = {}
_rate_bucket_lock = asyncio.Lock()


async def _get_rate_bucket(session_id: str) -> TokenBucket:
    """Get or create rate bucket keyed by session_id (not token prefix).

    Uses session_id instead of token[:40] to avoid:
    - Different sessions sharing the same bucket due to JWT header collision
    - Leaked tokens affecting the rate limit of legitimate sessions
    """
    async with _rate_bucket_lock:
        # Periodic cleanup: remove buckets idle > 5 minutes
        if len(_rate_buckets) % 100 == 0 and len(_rate_buckets) > 0:
            stale = [
                k for k, b in _rate_buckets.items()
                if b.idle_seconds > 300
            ]
            for k in stale:
                del _rate_buckets[k]

        if session_id not in _rate_buckets:
            _rate_buckets[session_id] = TokenBucket(rate=MCP_RATE_LIMIT_RPS)
        return _rate_buckets[session_id]


# ── Auth helpers ────────────────────────────────────────────────────

def _extract_token(request: Request) -> str:
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return ""


async def _verify_request(request: Request) -> dict | None:
    token = _extract_token(request)
    if not token:
        return None

    # Verify JWT first to get session_id
    payload = _token_manager.verify(token)
    if payload is None:
        return None

    # Rate limit per session_id (not token prefix — avoids collision)
    session_id = payload.get("session_id", "")
    if session_id:
        bucket = await _get_rate_bucket(session_id)
        if not await bucket.consume():
            return None  # Rate limited

    return payload


# ── Endpoints ───────────────────────────────────────────────────────

@router.get("/health")
async def health():
    """Health check — Agent daemon monitors."""
    return {
        "status": "ok",
        "tools_count": len(TOOL_DEFINITIONS),
        "version": "1.0.0",
    }


@router.post("")
async def mcp_handler(request: Request):
    """Main MCP JSON-RPC endpoint.

    Required: Authorization: Bearer <JWT>
    Body: {"jsonrpc":"2.0","method":"...","params":{...},"id":1}
    """
    # Body size check (before reading)
    content_length = request.headers.get("content-length")
    if content_length and int(content_length) > MCP_MAX_BODY_BYTES:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": f"Request body too large (max {MCP_MAX_BODY_BYTES} bytes)"},
                "id": None,
            },
            status_code=413,
        )

    # Auth + rate limit
    payload = await _verify_request(request)
    if payload is None:
        return JSONResponse(
            content={
                "jsonrpc": "2.0",
                "error": {"code": -32001, "message": "Unauthorized or rate limited — use Authorization: Bearer <token>"},
                "id": None,
            },
            status_code=401,
        )

    # Parse body
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(
            content={"jsonrpc": "2.0", "error": {"code": -32700, "message": "Parse error"}, "id": None},
            status_code=400,
        )

    req_id = body.get("id")
    method = body.get("method", "")
    session_id = payload.get("session_id", "")

    # Audit log
    logger.info(
        "mcp_request",
        extra={
            "session_id": session_id[:12],
            "method": method,
            "request_id": req_id,
            "workshop": payload.get("workshop_name", ""),
        },
    )

    # ── tools/list ──

    if method == "tools/list":
        return JSONResponse(content={
            "jsonrpc": "2.0",
            "result": {"tools": TOOL_DEFINITIONS},
            "id": req_id,
        })

    # ── tools/call ──

    if method == "tools/call":
        params = body.get("params", {})
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})

        start_time = time.monotonic()
        try:
            org = request.app.state.org
            kanban_store = request.app.state.kanban_store
            session_manager = request.app.state.session_manager

            result = await execute_tool(
                tool_name, arguments,
                org=org, kanban_store=kanban_store,
                session_manager=session_manager,
                mcp_token_payload=payload,
            )

            duration_ms = (time.monotonic() - start_time) * 1000
            is_error = result.get("isError", False)
            logger.info(
                "mcp_tool_call",
                extra={
                    "session_id": session_id[:12],
                    "tool": tool_name,
                    "args_keys": list(arguments.keys()),
                    "duration_ms": round(duration_ms, 1),
                    "is_error": is_error,
                },
            )

            return JSONResponse(content={
                "jsonrpc": "2.0",
                "result": result,
                "id": req_id,
            })

        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                "mcp_tool_error",
                extra={
                    "session_id": session_id[:12],
                    "tool": tool_name,
                    "args_keys": list(arguments.keys()),
                    "duration_ms": round(duration_ms, 1),
                    "error": str(exc)[:200],
                },
            )
            return JSONResponse(content={
                "jsonrpc": "2.0",
                "error": {"code": -32000, "message": str(exc)[:200]},
                "id": req_id,
            })

    return JSONResponse(content={
        "jsonrpc": "2.0",
        "error": {"code": -32601, "message": f"Method not found: {method}"},
        "id": req_id,
    })


@router.post("/token")
async def issue_token(request: Request):
    """Issue MCP session token (JWT).

    POST /mcp/token
    {"workshop_name": "demo", "user_id": "optional"}
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JSONResponse(content={"error": "Invalid JSON"}, status_code=400)

    workshop_name = body.get("workshop_name", "") or body.get("workshop", "")
    if not workshop_name:
        return JSONResponse(content={"error": "workshop_name is required"}, status_code=400)

    user_id = body.get("user_id", f"workshop:{workshop_name}")

    import uuid
    session_id = f"mcp-{uuid.uuid4().hex[:12]}"
    token = _token_manager.issue(
        user_id=user_id,
        session_id=session_id,
        workshop_name=workshop_name,
    )

    logger.info("mcp_token_issued", extra={
        "session_id": session_id[:12],
        "workshop": workshop_name,
    })

    return JSONResponse(content={
        "token": token,
        "session_id": session_id,
        "workshop_name": workshop_name,
        "endpoint": "/mcp",
        "header_format": "Authorization: Bearer <token>",
    })


@router.delete("/token/{jti}")
async def revoke_token(jti: str, request: Request):
    """Revoke an MCP token by its JWT ID (jti).

    DELETE /mcp/token/{jti}
    Authorization: Bearer <admin-token>

    If token is leaked, this immediately invalidates it
    (even if TTL hasn't expired).
    """
    payload = await _verify_request(request)
    if payload is None:
        return JSONResponse(
            content={"error": "Unauthorized or rate limited"},
            status_code=401,
        )

    _token_manager.revoke(jti)
    logger.info("mcp_token_revoked", extra={"jti": jti})
    return JSONResponse(content={"status": "revoked", "jti": jti})
```

- [ ] **Step 2: 更新 tools.py — isError 标准化 + btw callback 明确标记**

关键改动:

```python
# tools.py — execute_tool() 中每个错误返回加 isError 标记:

# Before (v1):   return {"content": [{"type": "text", "text": f"工作区 {name} 不存在"}]}
# After (v2):    return {"content": [{"type": "text", "text": f"工作区 {name} 不存在"}], "isError": True}

# btw callback 处理 — 标记为 Phase 2 实现:
# Phase 0 中 btw 模式设置 session_type=BTW 并记录 parent_session_id，
# 实际 callback 机制 (async callback queue) 在 Phase 2 Session Tree 完整实现。
```

**btw callback 对齐:**
```
Phase 0: execute_task(mode="btw") → 创建 SessionNode(session_type=BTW)，记录 parent_session_id
Phase 2: 完整 callback → parent session 的 callback_queue 收到结果 → 自动归档 → 通知调用方
```

- [ ] **Step 3: 挂载 MCP 路由 + 注册中间件**

```python
# gateway/server.py — 在 create_app() 中添加:

from gateway.mcp.server import router as mcp_router
app.include_router(mcp_router)
```

- [ ] **Step 4: 写集成测试**

```python
# gateway/mcp/test_server.py (追加)

def test_health_check():
    ...

def test_body_size_limit_rejected():
    ...

def test_rate_limit_after_burst():
    ...

def test_revoke_endpoint():
    ...

def test_tool_error_returns_is_error():
    ...
```

- [ ] **Step 5: 运行测试**

```bash
python3 -m pytest gateway/mcp/test_server.py -v
# Expected: all PASS
```

- [ ] **Step 6: 提交**

```bash
git add gateway/mcp/tools.py gateway/mcp/server.py gateway/server.py gateway/mcp/test_server.py
git commit -m "feat: MCP Server production-ready — rate-limit + audit + health + revocation + isError"
```

**Transport 决策: 只用 Authorization header，不用 query param**

原因:
- URL 中的 token 会被 nginx/cloudflare/gateway 日志记录
- 浏览器 history 会泄露
- MCP SDK 的 StreamableHTTP transport 期望 `Authorization: Bearer <token>` header
- Agor 0.14 版本后也从 query param 改成了 header

**Tools 决策: 合并为 `execute_task` + mode 枚举，而不是分裂式 `run_agent` / `spawn_session`**

原因:
- 分裂式的问题是 Agent 需要自己决定「该调 run_agent 还是 spawn_session」— 这在 LLM function calling 中是已知的脆弱点
- 合并为一个 tool + mode 枚举让 LLM 的决策空间从 N 选 1 变成 1 个参数选值
- Agor 的做法: `agor_sessions_prompt(sessionId, prompt, mode: "continue"|"fork"|"subsession"|"btw")`

### Task 0.3: Agent 通过 MCP 感知平台上下文

- Create: 无需新增代码，Agent 端通过 MCP 配置接入

Agent 通过 MCP 接入 ai-factory 不需要改 ai-factory 代码。所有 Agent 都是本地 Claude 实例，只需在 `CLAUDE.md` 或配置文件里声明 MCP server:

```json
{
  "mcpServers": {
    "nexus-ai-works": {
      "type": "streamable-http",
      "url": "http://localhost:8600/mcp",
      "headers": {
        "Authorization": "Bearer <token from POST /mcp/token>"
      }
    }
  }
}
```

Agent 拿到 token 后就能调:
- `nexus_read_board` — 读取当前 Workshop 的看板状态
- `nexus_list_workshops` — 列出所有 Workshop
- `nexus_run_workflow` — 执行工作流 DAG
- `nexus_execute_task(mode="spawn")` — 创建子会话处理子任务
- `nexus_execute_task(mode="fork")` — 同级 fork 探索替代方案
- `nexus_execute_task(mode="btw")` — 旁路询问不阻塞 (Phase 2 完整 callback)
- `nexus_get_status` — 获取平台整体状态

**无须新增代码** — token endpoint 已在 Task 0.2 实现。Agent 端只需一份本地 MCP 配置。全程 localhost。

### Task 0.4: 前端 MCP Token 面板

**Files:**
- Modify: `webui/src/components/Settings.tsx`
- Modify: `webui/src/lib/api.ts`

**交互流程:**
1. 用户打开 Settings → 看到 "MCP 连接" tab
2. 下拉选择 Workshop（从 `/api/workshops` 加载列表）
3. 点击「生成 Token」按钮 → `POST /mcp/token {"workshop_name": "..."}`
4. 面板展示: Token (带一键复制按钮) + curl 示例 + Claude Code MCP 配置 JSON
5. 底下有「吊销」按钮 → `DELETE /mcp/token/{jti}`

- [ ] **Step 1: 添加 API 层**

```typescript
// webui/src/lib/api.ts — 追加:

export async function fetchMCPToken(workshopName: string): Promise<{
  token: string; session_id: string; workshop_name: string; endpoint: string;
}> {
  const resp = await fetch(`${BASE}/mcp/token`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ workshop_name: workshopName }),
  });
  if (!resp.ok) throw new Error("Failed to generate MCP token");
  return resp.json();
}
```

- [ ] **Step 2: 添加 MCP Token UI**

```tsx
// webui/src/components/Settings.tsx — 新增 MCP 连接面板:
//
// 状态: { token, sessionId, workshopName, copied } | null
// UI 结构:
//   <select> {workshops.map(w => <option>{w.name}</option>)} </select>
//   <Button onClick={generateToken}>生成 Token</Button>
//   {token && (
//     <Card>
//       <code>{token.slice(0, 30)}...</code>
//       <Button onClick={copy}>复制完整 Token</Button>
//       <pre>{`curl -X POST ${BASE}/mcp \\
//   -H "Authorization: Bearer ${token}" \\
//   -H "Content-Type: application/json" \\
//   -d '{"jsonrpc":"2.0","method":"tools/list","id":1}'`}</pre>
//       <Button variant="destructive" onClick={revoke}>吊销 Token</Button>
//     </Card>
//   )}
```

- [ ] **Step 3: 写测试**

```tsx
// webui/src/components/__tests__/Settings.test.tsx (追加):
test("MCP token panel: generates and displays token", async () => { ... });
test("MCP token panel: copy button copies token to clipboard", async () => { ... });
```

---

## Phase 1: Worktree Manager

### 现状与目标

**现状**: `factory/org.py` Workshop 创建时 `self.workspace.mkdir(parents=True, exist_ok=True)` — 普通目录。Workshop 之间通过 `Warehouse` (symlink-based) 共享产物。

**目标**: Workshop 底层改用 `git worktree`。每个 Workshop = 一个 git worktree = 一个独立分支 + 目录 + 唯一端口。

```
现在:                             升级后:

workspaces/                       ~/.factory/worktrees/
├── demo/    (普通目录)              ├── wt-abc123/  (分支: workshop/demo)
│   ├── src/                        │   ├── .env (PORT=3001)
│   └── memory/                     │   ├── src/
└── dev/                            │   └── memory/
                                    └── wt-def456/  (分支: workshop/dev)
                                        ├── .env (PORT=3002)
                                        └── ...
```

### 文件结构

```
factory/worktree/               ← 新增模块
├── __init__.py
├── manager.py                  ← git worktree CRUD + hash-based port assignment
├── env_manager.py              ← 每个 worktree 独立 .env
└── test_manager.py             ← 测试
```

### Task 1.1: 端口分配 (hash-based, 无需独立类)

**为什么不用独立 PortAllocator 类:**
- Agor 的做法: `branch.unique_id % 1000 + 3000` — 一行哈希
- 独立的状态管理器 (PortAllocator 类 + allocate/release + 防冲突循环) 是过度设计
- 分支名本身就是唯一的，哈希后碰撞概率极低

**Files:**
- Create: `factory/worktree/__init__.py`
- Create: `factory/worktree/manager.py` (incorporates port assignment inline)

- [ ] **Step 1: 端口分配内联到 WorktreeManager**

```python
# factory/worktree/__init__.py
from __future__ import annotations
"""Worktree Manager — git worktree-based workspace isolation."""
```

端口分配逻辑直接放在 `WorktreeManager.create()` 里，不需要独立的 PortAllocator 类:

```python
# factory/worktree/manager.py (端口分配部分)
import hashlib

def _assign_port(branch: str, base: int = 3000, pool_size: int = 1000) -> int:
    """Deterministic port from branch name hash. Agor-style: hash % pool + base."""
    h = hashlib.sha256(branch.encode()).digest()
    num = int.from_bytes(h[:4], "big")
    return (num % pool_size) + base
```

- [ ] **Step 2: 写测试**

```python
# factory/worktree/test_manager.py
from factory.worktree.manager import _assign_port

def test_assign_port_deterministic():
    assert _assign_port("workshop/demo") == _assign_port("workshop/demo")

def test_assign_port_different_branches():
    p1 = _assign_port("workshop/a")
    p2 = _assign_port("workshop/b")
    assert p1 != p2  # should be different for different names
```

### Task 1.2: Worktree Manager (git worktree CRUD)

**Files:**
- Create: `factory/worktree/manager.py`
- Create: `factory/worktree/env_manager.py`

核心操作:
- `create(workshop_name)` → `git worktree add ~/.factory/worktrees/wt-{name} -b workshop/{name}`
- `list_all()` → `git worktree list`
- `remove(workshop_name)` → `git worktree remove` + `git branch -D`
- `merge(workshop_name, target_branch)` → `git merge`

- [ ] **Step 1: 写测试**

```python
# factory/worktree/test_manager.py (追加)

import tempfile
from pathlib import Path

from factory.worktree.manager import WorktreeManager


@pytest.fixture
def git_repo():
    """Create a temporary git repo for testing worktree operations."""
    import subprocess
    with tempfile.TemporaryDirectory() as td:
        repo = Path(td) / "bare.git"
        repo.mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "--bare"], check=True, capture_output=True)
        yield repo


def test_create_and_list_worktree(git_repo):
    mgr = WorktreeManager(
        repo_url=str(git_repo),
        worktree_root=git_repo.parent / "wts",
    )
    wt_path = mgr.create("test-workshop")
    assert wt_path.exists()
    assert (wt_path / ".git").exists() or (wt_path / ".git").is_file()

    trees = mgr.list_all()
    assert any("test-workshop" in t["name"] for t in trees)

    mgr.remove("test-workshop")
    assert not wt_path.exists()
```

- [ ] **Step 2: 实现 WorktreeManager**

```python
# factory/worktree/manager.py
from __future__ import annotations

import hashlib
import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)


def _assign_port(branch: str, base: int = 3000, pool_size: int = 1000) -> int:
    """Deterministic port from branch name hash. Agor-style: hash % pool + base."""
    h = hashlib.sha256(branch.encode()).digest()
    num = int.from_bytes(h[:4], "big")
    return (num % pool_size) + base


class WorktreeManager:
    """Manage git worktrees as isolated workshop execution units."""

    def __init__(
        self,
        repo_path: str = "",
        worktree_root: str | Path = "~/.factory/worktrees",
    ):
        # repo_path is required in production — never rely on CWD
        # (FastAPI/systemd/Docker CWD may not be the project root)
        self._repo = repo_path or os.environ.get(
            "NX_REPO_PATH",
            os.environ.get("NX_WORKSPACE_ROOT", ""),
        )
        if not self._repo:
            raise RuntimeError(
                "WorktreeManager requires repo_path or NX_REPO_PATH/NX_WORKSPACE_ROOT env var"
            )
        self._root = Path(worktree_root).expanduser().resolve()

    def _git(self, *args: str, timeout: int = 30) -> subprocess.CompletedProcess:
        """Run a git command with timeout to prevent indefinite blocking."""
        cmd = ["git", "-C", self._repo] + list(args)
        try:
            return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            raise RuntimeError(f"Git command timed out after {timeout}s: {' '.join(cmd)}")

    def create(self, workshop_name: str) -> Path:
        branch = f"workshop/{workshop_name}"
        wt_id = f"wt-{workshop_name}"
        target = self._root / wt_id

        self._root.mkdir(parents=True, exist_ok=True)

        result = self._git("worktree", "add", str(target), "-b", branch)
        if result.returncode != 0:
            result2 = self._git("worktree", "add", str(target), branch)
            if result2.returncode != 0:
                raise RuntimeError(f"git worktree add failed: {result2.stderr}")

        # Hash-based port assignment
        port = _assign_port(branch)
        (target / ".env").write_text(f"PORT={port}\nWORKSHOP_NAME={workshop_name}\n")

        return target

    def list_all(self) -> list[dict]:
        result = self._git("worktree", "list", "--porcelain")
        trees: list[dict] = []
        current: dict = {}
        for line in result.stdout.splitlines():
            if line.startswith("worktree "):
                if current:
                    trees.append(current)
                current = {"path": line[9:]}
            elif line.startswith("HEAD ") and current:
                current["head"] = line[5:]
            elif line.startswith("branch ") and current:
                current["branch"] = line[20:]
        if current:
            trees.append(current)
        return [
            {
                "name": Path(t.get("path", "")).name,
                "path": t.get("path", ""),
                "branch": t.get("branch", t.get("head", "")),
            }
            for t in trees
        ]

    def remove(self, workshop_name: str) -> None:
        wt_id = f"wt-{workshop_name}"
        target = self._root / wt_id
        if not target.exists():
            return
        self._git("worktree", "remove", str(target), "--force")
        try:
            self._git("branch", "-D", f"workshop/{workshop_name}")
        except RuntimeError:
            pass  # branch may not exist if worktree was partially cleaned
```

- [ ] **Step 3: 运行测试**

```bash
python3 -m pytest factory/worktree/test_manager.py -v
# Expected: all PASS
```

- [ ] **Step 4: 提交**

```bash
git add factory/worktree/manager.py factory/worktree/env_manager.py
git commit -m "feat: WorktreeManager — git worktree CRUD for workshop isolation"
```

### Task 1.3: Workshop 集成 Worktree（可选开关）

这一步让 Workshop 底层可以选择使用 worktree 还是传统 Path 目录。通过环境变量 `NX_USE_WORKTREE=true` 控制。

由于这是基础底座变更，需要保留兼容性——不加 flag 时行为不变。

**Files:**
- Modify: `factory/org.py` (Workshop.__init__)
- Modify: `config/schema.py` (DepartmentSpec 可选 worktree 字段)

此项改动在 Path 目录模式下添加一个 `_maybe_init_git()` 调用——当 `NX_USE_WORKTREE=true` 时自动创建 git worktree，否则行为不变。

---

## Phase 2: Session Tree

### 现状与目标

**现状**: `factory/workflow/snapshot.py` RunSnapshot 是线性的——一个 run_id 对应一个状态点，只能顺序恢复。

**目标**: 树形会话模型。每个 session node 可以有 0 或 1 个 parent，0 或 N 个 children。支持 fork (创建同级兄弟会话) 和 spawn (创建子会话)。

```
         root session (需求分析)
              │
        ┌─────┴─────┐
        │  spawn    │  spawn
        ▼           ▼
    前端开发      后端开发        ← 子任务，独立 worktree
        │           │
    ┌───┴───┐       │
    │ fork  │       │
    ▼       ▼       ▼
  Claude  Codex   完成
  方案A   方案B
    │       │
    └───┬───┘
        ▼
      合并比较                  ← 父 session 汇总
```

### 文件结构

```
factory/workflow/session_tree.py   ← 新增：树形会话模型 (替代 snapshot.py)
factory/workflow/test_session_tree.py ← 测试
factory/workflow/snapshot.py       ← 保留兼容，标记 deprecated
```

### Task 2.1: SessionNode 数据模型 + Tree 操作

**Files:**
- Create: `factory/workflow/session_tree.py`
- Test: `factory/workflow/test_session_tree.py`

- [ ] **Step 1: 写数据模型和测试**

```python
# factory/workflow/test_session_tree.py
from __future__ import annotations

import pytest
from factory.workflow.session_tree import SessionNode, SessionTree, SessionStatus


def make_node(session_id: str, parent_id: str = "", **kwargs) -> SessionNode:
    return SessionNode(
        session_id=session_id,
        parent_id=parent_id,
        workshop_name="demo",
        task="test task",
        **kwargs,
    )


class TestSessionTree:

    @pytest.fixture
    def tree(self, tmp_path):
        import os
        os.environ["SESSION_TREE_DIR"] = str(tmp_path)
        return SessionTree(workshop_name="test-workshop")

    def test_add_root(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        assert tree.root.session_id == "sess-root"

    def test_spawn_child(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        child = make_node("sess-child", parent_id="sess-root")
        tree.add(child)
        assert len(tree.children_of("sess-root")) == 1
        assert tree.children_of("sess-root")[0].session_id == "sess-child"

    def test_fork_sibling(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        fork_a = make_node("sess-root", session_type="fork")
        tree.add(fork_a)  # should become sibling of root's children
        # Actually fork creates a sibling from parent perspective
        a = make_node("sess-a", parent_id="sess-root")
        tree.add(a)
        b = tree.fork("sess-a", "sess-b", task="alternative approach")
        # b should be child of sess-root, same level as sess-a
        siblings = tree.children_of("sess-root")
        assert len(siblings) == 2
        assert {s.session_id for s in siblings} == {"sess-a", "sess-b"}

    def test_get_ancestors(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        child = make_node("sess-1", parent_id="sess-root")
        tree.add(child)
        grandchild = make_node("sess-2", parent_id="sess-1")
        tree.add(grandchild)
        ancestors = tree.ancestors_of("sess-2")
        assert [a.session_id for a in ancestors] == ["sess-root", "sess-1"]

    def test_get_siblings(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        tree.add(make_node("sess-a", parent_id="sess-root"))
        tree.add(make_node("sess-b", parent_id="sess-root"))
        tree.add(make_node("sess-c", parent_id="sess-root"))
        siblings = tree.siblings_of("sess-b")
        assert {s.session_id for s in siblings} == {"sess-a", "sess-c"}

    def test_to_dict_roundtrip(self, tree):
        tree.add(make_node("sess-root"))
        tree.add(make_node("sess-a", parent_id="sess-root"))
        data = tree.to_dict()
        restored = SessionTree.from_dict(data)
        assert restored.root.session_id == "sess-root"
        assert len(restored.children_of("sess-root")) == 1
```

- [ ] **Step 2: 运行测试验证失败**

```bash
python3 -m pytest factory/workflow/test_session_tree.py -v
# Expected: FAIL
```

- [ ] **Step 3: 实现 SessionTree**

```python
# factory/workflow/session_tree.py
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MERGED = "merged"


class SessionType(str, Enum):
    ROOT = "root"
    SPAWN = "spawn"    # child session for sub-task
    FORK = "fork"      # sibling session exploring alternative
    BTW = "btw"        # bypass inquiry — doesn't block target, auto-callback result


@dataclass
class SessionNode:
    session_id: str
    parent_id: str = ""
    session_type: SessionType = SessionType.ROOT
    workshop_name: str = ""
    worktree_id: str = ""
    task: str = ""
    status: SessionStatus = SessionStatus.PENDING
    agent_name: str = ""
    model: str = ""
    output: str = ""
    error: str = ""
    git_sha: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "session_type": self.session_type.value,
            "workshop_name": self.workshop_name,
            "worktree_id": self.worktree_id,
            "task": self.task,
            "status": self.status.value,
            "agent_name": self.agent_name,
            "model": self.model,
            "output": self.output,
            "error": self.error,
            "git_sha": self.git_sha,
            "turns": self.turns,
            "cost_usd": self.cost_usd,
            "tools_used": self.tools_used,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionNode:
        return cls(
            session_id=data["session_id"],
            parent_id=data.get("parent_id", ""),
            session_type=SessionType(data.get("session_type", "root")),
            workshop_name=data.get("workshop_name", ""),
            worktree_id=data.get("worktree_id", ""),
            task=data.get("task", ""),
            status=SessionStatus(data.get("status", "pending")),
            agent_name=data.get("agent_name", ""),
            model=data.get("model", ""),
            output=data.get("output", ""),
            error=data.get("error", ""),
            git_sha=data.get("git_sha", ""),
            turns=data.get("turns", 0),
            cost_usd=data.get("cost_usd", 0.0),
            tools_used=data.get("tools_used", []),
            messages=data.get("messages", []),
        )


class SessionTree:
    """Tree-structured session history with fork and spawn operations.

    Persistence: auto-saves to ~/.factory/sessions/{workshop}.json on every
    structural mutation (add/fork/spawn/btw). Auto-loads on init.
    """

    def __init__(self, workshop_name: str = "default"):
        self._workshop = workshop_name
        self._nodes: dict[str, SessionNode] = {}
        self._storage = Path(
            os.environ.get("SESSION_TREE_DIR", str(Path("~/.factory/sessions").expanduser()))
        ) / f"{workshop_name}.json"
        self._load()

    def _save(self) -> None:
        """Persist tree to disk after every structural mutation."""
        self._storage.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._storage.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
        os.replace(tmp, self._storage)

    def _load(self) -> None:
        """Load persisted tree on init. Missing file = fresh tree."""
        if self._storage.exists():
            try:
                data = json.loads(self._storage.read_text())
                for node_data in data.get("nodes", []):
                    self._nodes[node_data["session_id"]] = SessionNode.from_dict(node_data)
            except (json.JSONDecodeError, OSError):
                pass  # Corrupt file → start fresh

    @property
    def root(self) -> SessionNode | None:
        for node in self._nodes.values():
            if node.session_type == SessionType.ROOT:
                return node
        return None

    def add(self, node: SessionNode) -> None:
        if node.session_id in self._nodes:
            raise ValueError(f"Session {node.session_id} already exists")
        if node.parent_id and node.parent_id not in self._nodes:
            raise ValueError(f"Parent session {node.parent_id} not found")
        self._nodes[node.session_id] = node
        self._save()

    def get(self, session_id: str) -> SessionNode | None:
        return self._nodes.get(session_id)

    def fork(self, source_session_id: str, new_session_id: str, task: str) -> SessionNode:
        """Create a sibling session from the same parent for alternative exploration."""
        source = self._nodes[source_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=source.parent_id,
            session_type=SessionType.FORK,
            workshop_name=source.workshop_name,
            task=task,
            agent_name=source.agent_name,
            model=source.model,
        )
        self.add(node)
        return node

    def spawn(self, parent_session_id: str, new_session_id: str, task: str) -> SessionNode:
        """Create a child session for a sub-task."""
        parent = self._nodes[parent_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=parent_session_id,
            session_type=SessionType.SPAWN,
            workshop_name=parent.workshop_name,
            task=task,
            agent_name=parent.agent_name,
        )
        self.add(node)
        return node

    def btw(
        self,
        target_session_id: str,
        new_session_id: str,
        task: str,
    ) -> SessionNode:
        """Create a bypass inquiry session.

        Key differences from spawn:
        - Does NOT block the target session (even if target is busy, btw runs)
        - Auto-callbacks result to the calling session when complete
        - Auto-archived after callback

        Scope: Phase 2 provides the data model + tree structure.
        The async callback queue (btw results → parent session notification)
        is deferred to Phase 3 (Async Callback Infrastructure).
        """
        target = self._nodes[target_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=target_session_id,
            session_type=SessionType.BTW,
            workshop_name=target.workshop_name,
            task=task,
            agent_name=target.agent_name,
        )
        self.add(node)
        return node

    def children_of(self, session_id: str) -> list[SessionNode]:
        return [n for n in self._nodes.values() if n.parent_id == session_id]

    def siblings_of(self, session_id: str) -> list[SessionNode]:
        node = self._nodes.get(session_id)
        if not node:
            return []
        return [n for n in self._nodes.values() if n.parent_id == node.parent_id and n.session_id != session_id]

    def ancestors_of(self, session_id: str) -> list[SessionNode]:
        result: list[SessionNode] = []
        current = self._nodes.get(session_id)
        while current and current.parent_id:
            parent = self._nodes.get(current.parent_id)
            if parent:
                result.append(parent)
                current = parent
            else:
                break
        result.reverse()
        return result

    def all_nodes(self) -> list[SessionNode]:
        return list(self._nodes.values())

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [n.to_dict() for n in self._nodes.values()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionTree:
        tree = cls()
        for node_data in data.get("nodes", []):
            tree.add(SessionNode.from_dict(node_data))
        return tree
```

- [ ] **Step 4: 运行测试验证通过**

```bash
python3 -m pytest factory/workflow/test_session_tree.py -v
# Expected: all PASS
```

- [ ] **Step 5: 提交**

```bash
git add factory/workflow/session_tree.py factory/workflow/test_session_tree.py
git commit -m "feat: SessionTree — 树形会话模型 (fork/spawn) 替代线性 snapshot"
```

---

## 测试策略

### Phase 0 测试

| 层级 | 内容 | 预期覆盖 |
|------|------|----------|
| 单元测试 | MCPTokenManager issue/verify/expire/revoke/cleanup | 7 tests |
| 单元测试 | TokenBucket concurrent consume (2 coroutines, 100 iterations each) | 1 concurrency test |
| 单元测试 | MCP tools 每个 tool 的正确响应 + isError 标记 | 10 tools |
| 集成测试 | POST /mcp 完整 JSON-RPC 流程 (token→list→call→error) | 4 flow tests |
| 集成测试 | Rate limit: 11 requests in burst → 11th gets 401 | 1 test |
| 集成测试 | Body size limit: 2MB body → 413 | 1 test |
| 故障注入 | MCP_SECRET 未设置 → RuntimeError 启动拒绝 | 1 test |
| E2E | 本地 Agent 通过 MCP 调 `nexus_list_tools` → 验证返回结果 | Phase 0 收尾 |

### Phase 1 测试

| 层级 | 内容 |
|------|------|
| 单元测试 | hash-based 端口分配 deterministic + collision resistance |
| 单元测试 | WorktreeManager create/list/remove (用临时 bare repo) |
| 故障注入 | git 不可用时 WorktreeManager.create 抛 RuntimeError |
| 故障注入 | CWD 不是 repo 时 WorktreeManager 抛 RuntimeError |
| 集成测试 | Workshop 通过 NX_USE_WORKTREE=true 创建 worktree |

### Phase 2 测试

| 层级 | 内容 |
|------|------|
| 单元测试 | SessionNode to_dict/from_dict |
| 单元测试 | SessionTree add/fork/spawn/btw/children/ancestors/siblings |
| 单元测试 | SessionTree 持久化: 创建 → 新实例加载 → 树结构一致 |
| 并发测试 | 2 协程同时 spawn 子任务 → 树结构完整，无丢节点 |
| 集成测试 | 替换 RunSnapshot → SessionTree in WorkflowRunner |

---

## 实施顺序

```
Phase 0: MCP Server (3-5 天)
  Task 0.1 → Task 0.2 → Task 0.3 → Task 0.4
  没有依赖外部模块，可以立即开始

Phase 1: Worktree Manager (2-3 天)
  Task 1.1 → Task 1.2 → Task 1.3
  依赖：不需要 MCP (独立模块)

Phase 2: Session Tree (3-4 天)
  Task 2.1
  依赖：不需要 Phase 1 (但 benefit 最大时与 Worktree 搭配)
```

**Phase 之间互不阻塞**。可以先做任何一个 Phase。

---

## v2 Review 修正清单

| # | 严重度 | 问题 | 修正 |
|---|--------|------|------|
| 1 | .critical | 手写 JWT，无 kid，与标准库不兼容 | → PyJWT `jwt.encode()` + kid header |
| 2 | .critical | `_use_counts` dict 永不过期，内存泄漏 | → `_cleanup_stale()` 定期清理 |
| 3 | .critical | 无速率限制 + body 限制 | → Token bucket 10 req/s + 1MB body limit |
| 4 | .high | 无审计追踪 | → 结构化日志 `logger.info("mcp_tool_call", extra={...})` |
| 5 | .high | 无 token 吊销端点 | → `DELETE /mcp/token/{jti}` |
| 6 | .high | btw callback 未实现 | → Phase 0 设 type=BTW，Phase 2 实现 callback queue |
| 7 | .medium | 错误码不规范，Agent 无法 programmatic 区分 | → `isError: true` 标记 |
| 8 | .medium | 无健康检查 | → `GET /mcp/health` |

## 风险与回滚

| Phase | 风险 | 回滚方式 |
|-------|------|----------|
| MCP Server | 新增路由，不影响现有 Agent 调用 | 删除 `app.include_router(mcp_router)` 一行 |
| MCP Server | MCP endpoint 成为 Agent 性能瓶颈 (HTTP + auth + rate limit) | 启动后监控 p50/p99 延迟 + 错误率，加 metrics endpoint |
| MCP Server | PyJWT 第三方依赖安全漏洞 | lock 版本号 (`pyjwt>=2.8,<3`)，Dependabot 监控 |
| Worktree Manager | git 依赖，非 git 环境不兼容 | `NX_USE_WORKTREE=false` 回退 Path 模式 |
| Worktree Manager | git worktree 与用户本地 git 操作冲突 | 文档明确 `NX_USE_WORKTREE` 开启时不要在同一个 repo 手动 git 操作 |
| Worktree Manager | NFS/git index 损坏导致子进程永久阻塞 | 所有 git 操作 `timeout=30s`，超时抛异常 |
| Session Tree | 重启后 session 树结构丢失 (v4 已修复: 自动持久化) | `~/.factory/sessions/` JSON 文件可手动恢复 |
| Session Tree | 替换 snapshot 影响断点续跑 | snapshot.py 保留 90 天 deprecated 兼容 |

# 可靠性与安全 — 实现计划

> **Goal:** 可靠性（Agent错误透明化、DAG超时、断点续跑）+ 安全（API认证、Admin token加固、请求签名）

**Architecture:** 3个可靠性模块（Runner错误分类、Workflow超时/快照、断点恢复）+ 3个安全模块（Gateway认证依赖注入、Admin token哈希、HMAC签名中间件），全部独立可测。

**Tech Stack:** Python 3.11+, asyncio, hashlib, hmac, Pydantic v2, FastAPI Depends

---

## 文件清单

| File | Action | Responsibility |
|------|--------|---------------|
| `factory/runner.py` | Modify | 结构化错误类型 + 错误链追踪 |
| `factory/workflow/models.py` | Modify | WorkflowNode 加 timeout_seconds, WorkflowTemplate 加 max_total_seconds |
| `factory/workflow/engine.py` | Modify | 超时控制 + 执行快照 |
| `factory/workflow/snapshot.py` | Create | RunSnapshot — 运行状态持久化与恢复 |
| `factory/workflow/test_snapshot.py` | Create | 快照单元测试 |
| `gateway/auth.py` | Create | API Key 生成/验证 + JWT 依赖注入 |
| `gateway/server.py` | Modify | 注册认证中间件 |
| `marketplace/auth.py` | Modify | ADMIN_TOKEN 改为环境变量 + hash |
| `gateway/routes/market.py` | Modify | 加 HMAC 签名 |
| `marketplace/signature.py` | Create | 服务端验签 |

复用已有代码：
- `factory/workflow/engine.py` — WorkflowRunner._execute_node 已有 try/except，加超时和快照写入即可
- `gateway/csrf.py` — CSRFTokenMiddleware 模式参考，认证层用 FastAPI Depends 而不是中间件
- `gateway/routes/market.py` — _proxy_get/_proxy_post 加签名参数

---

### Task 1: Agent 错误透明化

**Files:**
- Modify: `factory/runner.py`

- [ ] **Step 1: 在 TaskResult 中加结构化错误字段**

```python
from enum import Enum

class ErrorKind(str, Enum):
    NONE = ""
    TOOL_FAILURE = "tool_failure"
    API_ERROR = "api_error"
    BUDGET_EXCEEDED = "budget_exceeded"
    TIMEOUT = "timeout"
    PERMISSION_DENIED = "permission_denied"
    UNKNOWN = "unknown"

@dataclass
class TaskResult:
    content: str
    tools_used: list[str] = field(default_factory=list)
    error: str | None = None
    error_kind: ErrorKind = ErrorKind.NONE       # NEW
    error_context: dict[str, str] = field(default_factory=dict)  # NEW: 错误发生时的上下文
    chunks_written: int = 0
    summaries_generated: int = 0
    session_id: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    events: tuple = ()
```

- [ ] **Step 2: 在 _run_agent_loop 中分类错误**

在 `_run_agent_loop` 的 except 处理中替换现有的简单 try/except，或在返回 TaskResult 处扩展错误判断逻辑：

```python
# 在当前行 273-281 的 TaskResult 构造处，扩展 error 处理：
error_kind = ErrorKind.NONE
error_context_info: dict[str, str] = {}
if result.stop_reason and result.stop_reason != "end_turn":
    error_kind = _classify_error(result.stop_reason, result.final_output or "")
    error_context_info = {
        "stop_reason": result.stop_reason,
        "tools_called": ", ".join(tool_names),
        "turns_used": str(result.turns),
    }
```

添加错误分类函数：

```python
def _classify_error(stop_reason: str, output: str) -> ErrorKind:
    reason_lower = stop_reason.lower() + " " + output[:500].lower()
    if any(k in reason_lower for k in ("tool_error", "tool_call", "tool_use_failed")):
        return ErrorKind.TOOL_FAILURE
    if any(k in reason_lower for k in ("429", "rate", "limit", "quota", "billing")):
        return ErrorKind.BUDGET_EXCEEDED
    if any(k in reason_lower for k in ("timeout", "timed out", "deadline")):
        return ErrorKind.TIMEOUT
    if any(k in reason_lower for k in ("401", "403", "unauthorized", "forbidden", "permission")):
        return ErrorKind.PERMISSION_DENIED
    if any(k in reason_lower for k in ("api_error", "server_error", "500", "502", "503")):
        return ErrorKind.API_ERROR
    return ErrorKind.UNKNOWN
```

- [ ] **Step 3: 运行现有测试确保无回归**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ --tb=short 2>&1 | tail -5`
Expected: all tests pass (TaskResult 加了字段但默认值兼容)

- [ ] **Step 4: Commit**

```bash
git add factory/runner.py
git commit -m "feat: Agent错误透明化 — 结构化错误分类+上下文追踪"
```

---

### Task 2: DAG 超时控制

**Files:**
- Modify: `factory/workflow/models.py:22-42`
- Modify: `factory/workflow/engine.py:66-141`

- [ ] **Step 1: WorkflowNode 和 WorkflowTemplate 加超时字段**

在 `factory/workflow/models.py` 中:

```python
@dataclass
class WorkflowNode:
    id: str
    label: str = ""
    agent_name: str = ""
    prompt: str = ""
    depends_on: list[str] = field(default_factory=list)
    expected_output: str = ""
    gate: dict[str, str] | None = None
    timeout_seconds: int = 300  # NEW: 节点级超时，默认5分钟
    
    def to_dict(self) -> dict[str, Any]:
        d = { ... }
        d["timeout_seconds"] = self.timeout_seconds  # NEW
        return d
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            ...
            timeout_seconds=data.get("timeout_seconds", 300),  # NEW
        )

@dataclass
class WorkflowTemplate:
    name: str
    description: str = ""
    workspace: str = ""
    nodes: list[WorkflowNode] = field(default_factory=list)
    max_total_seconds: int = 0  # NEW: 0=不限，工作流级总超时
```

- [ ] **Step 2: WorkflowRunner.run() 加两重超时**

在 `factory/workflow/engine.py` 的 `_execute_node` 方法中包 asyncio.wait_for：

```python
async def _execute_node(self, node_id: str, task: str) -> NodeResult:
    node = self._node_map[node_id]
    timeout = node.timeout_seconds if hasattr(node, 'timeout_seconds') else 300
    await self._notify(node_id, "running", "")
    
    if node_id in self._mock_outputs:
        ...  # 不变
    
    try:
        return await asyncio.wait_for(
            self._execute_node_impl(node_id, task),
            timeout=timeout,
        )
    except asyncio.TimeoutError:
        await self._notify(node_id, "failed", f"Timeout after {timeout}s")
        return NodeResult(
            node_id=node_id, agent_name=node.agent_name,
            status=NodeStatus.FAILED, error=f"Timeout after {timeout}s",
        )
```

把原有逻辑移到 `_execute_node_impl`（同函数体，改名）。

在 `run()` 方法加工作流级超时：

```python
async def run(self, template: WorkflowTemplate, task: str) -> WorkflowResult:
    ...
    total_timeout = getattr(template, 'max_total_seconds', 0) or 0
    try:
        if total_timeout > 0:
            return await asyncio.wait_for(
                self._run_impl(template, task, result, order),
                timeout=total_timeout,
            )
        return await self._run_impl(template, task, result, order)
    except asyncio.TimeoutError:
        result.status = NodeStatus.FAILED
        result.final_output = f"Workflow timeout after {total_timeout}s"
        return result
```

把 run() 中原有的 while 循环逻辑移到 `_run_impl`。

- [ ] **Step 3: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/workflow/test_engine.py -v --tb=short`
Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add factory/workflow/models.py factory/workflow/engine.py
git commit -m "feat: DAG超时控制 — 节点级+工作流级双重超时"
```

---

### Task 3: 断点续跑

**Files:**
- Create: `factory/workflow/snapshot.py`
- Create: `factory/workflow/test_snapshot.py`
- Modify: `factory/workflow/engine.py`

- [ ] **Step 1: 创建 factory/workflow/snapshot.py**

```python
"""工作流执行快照 — 持久化运行状态，支持断点续跑。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from .models import NodeStatus, WorkflowTemplate


class RunSnapshot:
    """单个工作流运行的完整状态快照。"""

    def __init__(self, base_dir: str = "~/.nexus/runs") -> None:
        self._dir = Path(base_dir).expanduser().resolve()

    def _path(self, run_id: str) -> Path:
        return self._dir / f"{run_id}.json"

    def save(
        self,
        run_id: str,
        template: WorkflowTemplate,
        task: str,
        node_states: dict[str, NodeStatus],
        node_outputs: dict[str, str],
        node_errors: dict[str, str],
        retries: dict[str, int],
    ) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        data = {
            "run_id": run_id,
            "template_name": template.name,
            "task": task,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "node_states": {k: v.value for k, v in node_states.items()},
            "node_outputs": node_outputs,
            "node_errors": node_errors,
            "retries": retries,
        }
        self._path(run_id).write_text(json.dumps(data, ensure_ascii=False, indent=2))

    def load(self, run_id: str) -> dict | None:
        path = self._path(run_id)
        if not path.exists():
            return None
        return json.loads(path.read_text())

    def list_incomplete(self) -> list[dict]:
        """返回所有未完成的运行（含 FAILED 和 PENDING 节点）。"""
        if not self._dir.exists():
            return []
        result = []
        for f in self._dir.glob("*.json"):
            data = json.loads(f.read_text())
            states = data.get("node_states", {})
            has_incomplete = any(
                s in (NodeStatus.PENDING.value, NodeStatus.RUNNING.value, NodeStatus.FAILED.value)
                for s in states.values()
            )
            if has_incomplete:
                result.append(data)
        return result

    def delete(self, run_id: str) -> None:
        path = self._path(run_id)
        if path.exists():
            path.unlink()

    @staticmethod
    def new_run_id() -> str:
        return f"run-{uuid.uuid4().hex[:8]}"
```

- [ ] **Step 2: WorkflowRunner 集成快照**

在 `run()` 方法中，每完成一个节点就写入快照：

```python
async def run(self, template: WorkflowTemplate, task: str, *, run_id: str = "") -> WorkflowResult:
    from .snapshot import RunSnapshot
    snapshot = RunSnapshot()
    run_id = run_id or RunSnapshot.new_run_id()
    ...  # 现有逻辑
    
    # 每完成一个 batch 后：
    snapshot.save(
        run_id=run_id,
        template=template,
        task=task,
        node_states={nid: nr.status for nid, nr in result.node_results.items()},
        node_outputs={nid: nr.output for nid, nr in result.node_results.items()},
        node_errors={nid: nr.error for nid, nr in result.node_results.items()},
        retries={nid: nr.retries for nid, nr in result.node_results.items()},
    )
    
    # 全部完成后删除快照（运行成功）
    snapshot.delete(run_id)
    return result
```

加一个类方法从快照恢复：

```python
@classmethod
async def resume(cls, run_id: str, org) -> WorkflowResult | None:
    from .snapshot import RunSnapshot
    snap = RunSnapshot()
    data = snap.load(run_id)
    if data is None:
        return None
    
    tmpl = org.workflow_store.load(data["template_name"])
    if tmpl is None:
        return None
    
    # 从快照恢复 runner 状态
    runner = cls(None)
    result = WorkflowResult(template_name=tmpl.name, task=data["task"])
    # ... 跳过已完成的节点，从第一个 pending/failed 开始
    
    # 执行剩余节点（复用 run 逻辑，跳过 passed 节点）
    # ... 
    return result
```

- [ ] **Step 3: 单元测试**

创建 `factory/workflow/test_snapshot.py`：

```python
class TestRunSnapshot:
    def test_save_and_load(self, tmp_path):
        ...
    def test_list_incomplete(self, tmp_path):
        ...
    def test_delete(self, tmp_path):
        ...
    def test_load_nonexistent(self, tmp_path):
        ...
```

- [ ] **Step 4: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/workflow/ -v --tb=short`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add factory/workflow/snapshot.py factory/workflow/test_snapshot.py factory/workflow/engine.py
git commit -m "feat: 断点续跑 — RunSnapshot持久化+恢复"
```

---

### Task 4: API 认证层

**Files:**
- Create: `gateway/auth.py`
- Modify: `gateway/server.py`

- [ ] **Step 1: 创建 gateway/auth.py**

```python
"""API authentication — API Key + JWT dependency injection for FastAPI.

- 本地 CLI/Agent 调用: API Key (x-api-key header)
- Web UI 登录: JWT (Authorization: Bearer <token>)
- 首次启动自动生成 API Key 写入 ~/.nexus/api_key
"""

from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from pathlib import Path

from fastapi import HTTPException, Request
from fastapi.security import HTTPBearer

API_KEY_PATH = Path("~/.nexus/api_key").expanduser()
JWT_SECRET = os.environ.get("JWT_SECRET", "")

security = HTTPBearer(auto_error=False)


def get_or_create_api_key() -> str:
    """Get existing API key or generate a new one."""
    API_KEY_PATH.parent.mkdir(parents=True, exist_ok=True)
    if API_KEY_PATH.exists():
        return API_KEY_PATH.read_text().strip()
    key = "nk-" + secrets.token_hex(24)  # nk- prefix = nexus key
    API_KEY_PATH.write_text(key)
    API_KEY_PATH.chmod(0o600)
    return key


def verify_api_key(key: str) -> bool:
    """Constant-time API key comparison."""
    stored = get_or_create_api_key()
    return hmac.compare_digest(key.encode(), stored.encode())


async def require_auth(request: Request):
    """FastAPI dependency: require either API Key or JWT."""
    # 1. Check API Key
    api_key = request.headers.get("x-api-key", "")
    if api_key and verify_api_key(api_key):
        return

    # 2. Check JWT
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        if _verify_jwt(auth[7:]):
            return

    raise HTTPException(status_code=401, detail="Authentication required")


def _verify_jwt(token: str) -> bool:
    """Verify HMAC-signed JWT. Uses same logic as marketplace/auth.py."""
    from marketplace.auth import decode_token
    payload = decode_token(token)
    return payload is not None


# Optional: stricter auth for sensitive ops
async def require_admin(request: Request):
    """Require API Key only (admin-level operations)."""
    api_key = request.headers.get("x-api-key", "")
    if not api_key or not verify_api_key(api_key):
        raise HTTPException(status_code=403, detail="Admin API key required")
```

- [ ] **Step 2: 在 gateway/server.py 注册可选认证**

不对所有路由强制认证，而是提供 dependency 供路由自行选择：

在 `gateway/server.py` 中无需额外注册——`require_auth` 和 `require_admin` 作为路由级别的 dependency 使用即可。现有路由默认不启动强制认证（兼容已有测试），敏感路由（如 /api/agent/run, /api/workshops/import）可以逐步加上 `dependencies=[Depends(require_auth)]`。

加一个认证状态的端点：

```python
# 在 gateway/routes/health.py 中追加
@router.get("/api/auth/status")
async def auth_status():
    from gateway.auth import API_KEY_PATH
    return {"key_configured": API_KEY_PATH.exists()}
```

- [ ] **Step 3: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ --tb=short 2>&1 | tail -5`
Expected: all pass（认证层是可选依赖，不破坏现有测试）

- [ ] **Step 4: Commit**

```bash
git add gateway/auth.py gateway/server.py gateway/routes/health.py
git commit -m "feat: API认证层 — API Key + JWT 双通道认证依赖"
```

---

### Task 5: Admin Token 加固

**Files:**
- Modify: `marketplace/auth.py`
- Modify: `marketplace/admin.py`

- [ ] **Step 1: marketplace/auth.py 追加 admin token 管理**

```python
# 追加到 marketplace/auth.py 末尾

ADMIN_TOKEN_HASH = os.environ.get("MARKETPLACE_ADMIN_TOKEN_HASH", "")
if not ADMIN_TOKEN_HASH:
    # Default: hash of "nexus-admin-secret" (V1 compatibility)
    ADMIN_TOKEN_HASH = hash_password("nexus-admin-secret")


def verify_admin_token(token: str) -> bool:
    """Verify admin token against stored hash."""
    return verify_password(token, ADMIN_TOKEN_HASH)
```

- [ ] **Step 2: marketplace/admin.py 改用 verify_admin_token**

替换所有 `_admin_only` 中的硬编码检查：

```python
# 旧:
if authorization[7:] != ADMIN_TOKEN:
    raise HTTPException(status_code=403, detail="Forbidden")

# 新:
from marketplace.auth import verify_admin_token
if not verify_admin_token(authorization[7:]):
    raise HTTPException(status_code=403, detail="Forbidden")
```

- [ ] **Step 3: Commit**

```bash
git add marketplace/auth.py marketplace/admin.py
git commit -m "fix: Admin token加固 — 环境变量+hash存储"
```

---

### Task 6: 本地↔云端请求签名

**Files:**
- Create: `gateway/signature.py`
- Modify: `gateway/routes/market.py`

- [ ] **Step 1: 创建 gateway/signature.py**

```python
"""HMAC request signing for local↔cloud API communication.

Shared secret stored at ~/.nexus/marketplace_secret.
Generated on first run, must be registered with cloud.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from pathlib import Path

SECRET_PATH = Path("~/.nexus/marketplace_secret").expanduser()


def get_or_create_secret() -> str:
    SECRET_PATH.parent.mkdir(parents=True, exist_ok=True)
    if SECRET_PATH.exists():
        return SECRET_PATH.read_text().strip()
    secret = secrets.token_hex(32)
    SECRET_PATH.write_text(secret)
    SECRET_PATH.chmod(0o600)
    return secret


def sign_request(method: str, path: str, body: str, timestamp: str) -> str:
    """Produce HMAC-SHA256 signature for a request."""
    secret = get_or_create_secret()
    message = f"{method}\n{path}\n{body}\n{timestamp}".encode()
    return hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
```

- [ ] **Step 2: gateway/routes/market.py 代理请求加签名**

在 `_proxy_get` 和 `_proxy_post` 中追加 header：

```python
from gateway.signature import sign_request
from datetime import datetime, timezone

def _signed_headers(method: str, path: str, body: str) -> dict:
    ts = datetime.now(timezone.utc).isoformat()
    sig = sign_request(method, path, body, ts)
    return {"X-Signature": sig, "X-Timestamp": ts}

# 在 httpx 请求的 headers 中合并这些 header
```

- [ ] **Step 3: 创建 marketplace/signature.py（服务端验签）**

```python
"""Server-side HMAC signature verification middleware for marketplace API."""

from __future__ import annotations

import hashlib
import hmac
from datetime import datetime, timezone, timedelta

from fastapi import HTTPException, Request


async def verify_signature(request: Request) -> None:
    """FastAPI dependency: verify X-Signature on all /api/* requests.
    
    Skips /api/auth/* and /api/catalog (public endpoints).
    """
    path = request.url.path
    if path.startswith("/api/auth/") or path == "/api/catalog":
        return  # Public endpoints — no signature required
    
    # Check signature from registered clients only
    # V1: skip verification if no clients registered
    secret = _get_client_secret(request)
    if secret is None:
        return  # No auth configured yet
    
    sig = request.headers.get("X-Signature", "")
    ts = request.headers.get("X-Timestamp", "")
    if not sig or not ts:
        raise HTTPException(status_code=401, detail="Missing signature")
    
    # Anti-replay: ±5 minute window
    try:
        req_time = datetime.fromisoformat(ts)
        now = datetime.now(timezone.utc)
        if abs((now - req_time).total_seconds()) > 300:
            raise HTTPException(status_code=401, detail="Timestamp expired")
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid timestamp")
    
    # HMAC verify
    body = await request.body()
    message = f"{request.method}\n{path}\n{body.decode()}\n{ts}".encode()
    expected = hmac.new(secret.encode(), message, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(sig, expected):
        raise HTTPException(status_code=401, detail="Invalid signature")
```

- [ ] **Step 4: 运行测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest marketplace/ gateway/ --tb=short 2>&1 | tail -5`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add gateway/signature.py gateway/routes/market.py marketplace/signature.py
git commit -m "feat: HMAC请求签名 — 本地↔云端防篡改+防重放"
```

---

### Task 7: 最终验证

- [ ] **Step 1: 全量测试**

Run: `cd /Users/linhan/ai-factory && python3 -m pytest factory/ gateway/ marketplace/ --tb=short 2>&1 | tail -5`
Expected: all pass

- [ ] **Step 2: 验证新增功能**

```bash
python3 -c "from factory.workflow.snapshot import RunSnapshot; print('OK')"
python3 -c "from gateway.auth import require_auth; print('OK')"
python3 -c "from gateway.signature import sign_request; print('OK')"
```

- [ ] **Step 3: Commit**

```bash
git add -A
git commit -m "chore: 可靠性与安全最终验证通过"
```

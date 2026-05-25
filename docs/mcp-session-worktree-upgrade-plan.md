# MCP + Session Tree + Worktree 升级方案

> 2026-05-25 | 基于 Agor 分析，为 ai-factory 开发部板块做技术方案

## 目标

让 ai-factory 支持多个 Agent (Claude Code, Codex, Gemini CLI, Qwen Agent 等) 在一个项目里**自己开会、自己分工、自己审查**，用户只输入需求、接收结果。

## 三层架构

```
┌─────────────────────────────────────────────┐
│                 用户                          │
│         输入需求 → 接收产物                    │
└──────────────────┬──────────────────────────┘
                   │
┌──────────────────┴──────────────────────────┐
│           MCP Server (gateway/mcp/)           │
│                                              │
│  Agent 通过 MCP tools 互相对话：              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐   │
│  │ Claude   │  │  Codex   │  │ Gemini   │   │
│  │ (审查)   │  │ (开发)   │  │ (测试)   │   │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘   │
│       │             │             │          │
│       └─────────────┼─────────────┘          │
│                     │                        │
│              MCP Endpoint                     │
│           (JSON-RPC 2.0)                     │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────┴───────────────────────┐
│           Session Tree                        │
│                                              │
│  树形会话记录，所有 Agent 共享                │
│  支持 fork(分叉) + spawn(子任务)              │
└──────────────────────┬───────────────────────┘
                       │
┌──────────────────────┴───────────────────────┐
│           Worktree Manager                    │
│                                              │
│  每个任务 = git worktree = 独立分支+目录+端口  │
└──────────────────────────────────────────────┘
```

---

## Phase 1: MCP Server

### 概要

在 gateway 层加 MCP endpoint，把 ai-factory 的已有能力暴露为 MCP tools。Agent 后端通过 MCP 协议与平台交互。

### 实现

**新文件**: `gateway/mcp/__init__.py`, `gateway/mcp/server.py`, `gateway/mcp/tools.py`

**MCP Endpoint**: `POST /mcp` (JSON-RPC 2.0)

```python
# gateway/mcp/server.py — 核心
class MCPServer:
    """MCP Server wrapping ai-factory capabilities."""

    def __init__(self, org, workflow_store, kanban_store):
        self.tools = {
            # ── Agent 执行 ──
            "agent.run":           self.run_agent,        # 调用 Agent 执行任务
            "agent.status":        self.agent_status,     # 查 Agent 状态

            # ── 会话通信 ──
            "session.send":        self.session_send,     # 向另一个 session 发消息
            "session.read":        self.session_read,     # 读本 session 消息
            "session.status":      self.session_status,   # 更新 session 状态

            # ── 工作流 ──
            "workflow.start":      self.workflow_start,   # 启动工作流
            "workflow.status":     self.workflow_status,  # 查工作流状态

            # ── Worktree / 工作区 ──
            "worktree.read":       self.worktree_read,    # 读另一个 worktree 的代码
            "worktree.commit":     self.worktree_commit,  # 提交当前 worktree

            # ── 看板 ──
            "board.status":        self.board_status,     # 查看板状态
            "board.move_card":     self.board_move_card,  # 移动卡片
        }

    async def handle(self, request: MCPRequest) -> MCPResponse:
        token = request.params.get("sessionToken")
        session = self.resolve_session(token)
        tool = self.tools[request.method]
        return await tool(session, request.params)
```

**Session Token 机制**: 每个 Agent 会话开始时签发一个 JWT token，关联 session_id + worktree_id + 权限范围。

```python
# Session token payload
{
    "session_id": "sess-abc123",
    "worktree_id": "wt-def456",
    "agent_type": "claude",
    "permissions": ["agent.run", "session.send", "worktree.read"],
    "exp": 1712345678
}
```

### MCP Tools 设计

| Tool | 谁调用 | 做什么 |
|------|--------|--------|
| `session.send` | 任何 Agent | 向指定 session 发消息（可指定角色和目标） |
| `session.read` | 任何 Agent | 读当前 session 的所有消息（筛选角色/时间） |
| `session.status` | 任何 Agent | 更新自己的执行状态（running/done/failed） |
| `agent.run` | 任何 Agent | 启动一个新的 Agent 执行子任务 |
| `workflow.start` | PM Agent | 启动预定义工作流模板 |
| `worktree.read` | 审查 Agent | 读开发 Agent 的 worktree 代码 |
| `worktree.commit` | 开发 Agent | 提交代码变更 |
| `board.status` | 任何 Agent | 看看板上各列任务分布 |
| `board.move_card` | 任何 Agent | 把卡片移到对应列 |

### 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `gateway/mcp/__init__.py` | 新 | 5 |
| `gateway/mcp/server.py` | 新 | ~120 |
| `gateway/mcp/tools.py` | 新 | ~80 |
| `gateway/server.py` | 加 `/mcp` 路由 | ~15 |
| `factory/engine/bridge.py` | 不改，保留兼容 | 0 |
| 总计 | | ~220 行 |

### 验证

```bash
# 启动 ai-factory
python3 entrypoint.py serve

# 模拟 Claude Agent 通过 MCP 发消息
curl -X POST http://localhost:8600/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "session.send",
    "params": {
      "sessionToken": "xxx",
      "target_session": "sess-codex-001",
      "role": "reviewer",
      "content": "第三行有 SQL 注入漏洞，请修复"
    },
    "id": 1
  }'

# 模拟 Codex Agent 读消息
curl -X POST http://localhost:8600/mcp \
  -H "Content-Type: application/json" \
  -d '{
    "jsonrpc": "2.0",
    "method": "session.read",
    "params": {"sessionToken": "yyy"},
    "id": 2
  }'
```

---

## Phase 2: Session Tree

### 概要

将线性 RunSnapshot → 树形 SessionTree。支持 fork（同任务多 Agent 分叉探索）和 spawn（父任务拆分）。

### 数据模型

```python
# factory/workflow/session_tree.py

@dataclass
class SessionNode:
    id: str                          # "sess-abc123"
    parent_id: str | None            # null = root
    session_type: str                # "root" | "fork" | "spawn"
    agent_type: str                  # "claude" | "codex" | "gemini"
    worktree_id: str                 # 关联的 worktree
    task: str                        # 任务描述
    role: str = ""                   # "architect" | "developer" | "reviewer"
    status: str = "pending"          # pending/running/done/failed
    messages: list[dict] = field(default_factory=list)
    # 每条消息: {role, content, target, timestamp, git_sha}
    created_at: str = ""
    completed_at: str = ""

@dataclass
class SessionTree:
    nodes: dict[str, SessionNode]    # session_id → node
    root_id: str                     # 树的根节点

    def fork(self, session_id: str, agent_type: str) -> str:
        """从指定 session 分叉，创建同级兄弟 session"""
        ...

    def spawn(self, session_id: str, task: str, agent_type: str) -> str:
        """从指定 session 衍生子任务 session"""
        ...

    def get_messages(self, session_id: str) -> list[dict]:
        """读某个 session 的所有消息（含祖先 session 的上下文）"""
        ...

    def get_siblings(self, session_id: str) -> list[str]:
        """获取同级 session（用于比较不同 Agent 的产出）"""
        ...
```

### 存储

沿用现有 RunSnapshot 的 `~/.nexus/runs/` 目录，JSON 文件格式：

```json
{
  "run_id": "run-abc123",
  "parent_id": null,
  "session_type": "root",
  "tree": {
    "run-abc123": {
      "agent": "claude",
      "status": "done",
      "task": "实现用户登录",
      "messages": [
        {"role": "architect", "content": "方案: JWT + bcrypt...", "target": "codex", "ts": "...", "sha": "abc123"},
        {"role": "developer", "content": "已完成，见 worktree wt-xxx", "target": "claude", "ts": "...", "sha": "def456"}
      ]
    },
    "run-def456": {
      "parent_id": "run-abc123",
      "session_type": "spawn",
      "agent": "codex",
      "status": "running"
    }
  }
}
```

### 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `factory/workflow/session_tree.py` | 新，替代 snapshot.py | ~150 |
| `factory/workflow/snapshot.py` | 兼容保留，内部委托给 SessionTree | ~20 |
| `factory/workflow/engine.py` | 执行时读写 SessionTree | ~30 |
| MCP tools | 新增 `session.send` / `session.read` | 已含在 Phase1 |
| 总计 | | ~200 行 |

---

## Phase 3: Worktree Manager

### 概要

将 Workshop 从普通目录升级为 git worktree。每个 Agent 任务自动创建独立分支 + 独立目录 + 独立端口。

### 实现

```python
# factory/worktree/manager.py

class WorktreeManager:
    """Git worktree 管理 — 一个任务 = 一个 worktree = 一个分支"""

    def __init__(self, repo_path: str, base_dir: str = "~/.factory/worktrees"):
        self.repo_path = repo_path
        self.base_dir = Path(base_dir).expanduser()
        self.port_allocator = PortAllocator(start=4000, end=4999)

    def create(self, task_name: str) -> Worktree:
        """为任务创建独立 worktree"""
        branch = f"task/{slugify(task_name)}-{short_id()}"
        worktree_id = f"wt-{short_id()}"
        path = self.base_dir / worktree_id
        # git worktree add path -b branch
        subprocess.run(["git", "-C", self.repo_path, "worktree", "add", str(path), "-b", branch])
        port = self.port_allocator.allocate()
        return Worktree(id=worktree_id, branch=branch, path=path, port=port)

    def merge(self, worktree_id: str) -> bool:
        """合并 worktree 分支到主分支"""
        ...

    def remove(self, worktree_id: str) -> None:
        """删除 worktree，释放端口"""
        ...

    def list(self) -> list[Worktree]:
        """列所有活跃 worktree"""
        ...

    def read(self, worktree_id: str, file_path: str) -> str:
        """Agent 读另一个 worktree 的文件"""
        ...
```

### 端口分配器

```python
class PortAllocator:
    """防止多 Agent 并行时端口冲突"""

    def __init__(self, start: int, end: int):
        self.start = start
        self.end = end
        self._used: set[int] = set()

    def allocate(self) -> int:
        port = next(p for p in range(self.start, self.end + 1) if p not in self._used)
        self._used.add(port)
        return port

    def release(self, port: int) -> None:
        self._used.discard(port)
```

### 改动清单

| 文件 | 改动 | 行数 |
|------|------|------|
| `factory/worktree/__init__.py` | 新 | 5 |
| `factory/worktree/manager.py` | 新 | ~120 |
| `factory/worktree/port_allocator.py` | 新 | ~40 |
| `factory/org.py` Workshop | upgrade 内部用 WorktreeManager | ~30 |
| `gateway/server.py` | 初始化时启动 WorktreeManager | ~10 |
| 总计 | | ~205 行 |

---

## 总改动量

| Phase | 新代码 | 改现有代码 | 总计 |
|-------|--------|-----------|------|
| MCP Server | ~200 行 | ~15 行 | ~215 行 |
| Session Tree | ~150 行 | ~50 行 | ~200 行 |
| Worktree Manager | ~165 行 | ~40 行 | ~205 行 |
| **合计** | **~515 行** | **~105 行** | **~620 行** |

三个 Phase 可以独立实施、独立测试、独立上线。

---

## 验收标准

### Phase 1 验收
- Claude Code 能通过 MCP 调用 `session.send` 向 Codex 发消息
- Codex 能通过 MCP 调用 `session.read` 读到 Claude 的消息
- 新 Agent (Gemini CLI) 接入 → 不改 ai-factory 代码，只配 MCP client

### Phase 2 验收
- 同一任务 fork 两个 Agent 分叉执行（Codex vs Claude）
- spawn 创建子任务 session，父子关联
- 树形结构可查询、可回溯

### Phase 3 验收
- 创建任务 → 自动创建 git worktree + 分支
- 多个 Agent 并行 → 各自独立 worktree + 不冲突端口
- 任务完成 → worktree 可合并到主分支

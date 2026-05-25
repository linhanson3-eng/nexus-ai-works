# Agor 技术分析 & 专业开发模块升级方案

> 2026-05-25 | ai-factory 项目开发模块规划

## 一、Agor 核心技术剖析

Agor (preset-io/agor) — "Figma for AI coding assistants"。一个本地 daemon，通过空间画布编排多个 AI 编码助手（Claude Code、Codex、Gemini）并行工作。

**技术栈**: TypeScript 92.3% | FeathersJS | LibSQL | Drizzle ORM | MCP  
**许可证**: BSL 1.1（源码可见，非 OSI 开源）  
**当前版本**: v0.15.0（80+ releases，2026年3月）

### 架构是四层协同

```
┌──────────────────────────────────────────────┐
│            Agor Daemon (FeathersJS)           │
│                                              │
│  ① MCP Server     ──→  /mcp?sessionToken=   │
│     所有 Agent 通过 JSON-RPC 2.0 接入        │
│     "人能干的事，Agent 也能干"                │
│                                              │
│  ② Session Engine  ──→  树形会话，可 fork/spawn│
│     每个消息记录 git SHA，可审计              │
│                                              │
│  ③ Worktree Mgr    ──→  git worktree CRUD    │
│     每个任务 = 一个 worktree = 一个分支       │
│     自动分配端口、隔离环境                     │
│                                              │
│  ④ Services Layer  ──→  Sessions/Boards/Repos│
│     Drizzle ORM → LibSQL (~/.agor/agor.db)   │
└──────────────────────────────────────────────┘
```

### 1.1 MCP Server — 统一 Agent 协议

Agor 不需要给每个 Agent 后端写 adapter。在 daemon 里起一个 MCP HTTP endpoint，Claude 说 MCP，Codex 说 MCP，Gemini 说 MCP——一个协议管所有。

**具体实现**:
- 每个 session 自动签发 MCP token（session-scoped）
- Agent 通过 `POST /mcp?sessionToken=xxx` 调用工具（JSON-RPC 2.0）
- MCP tools 暴露 Agor 自身的能力：读 board 状态、查其他 session、spawn 子任务、写结果
- **双向的**——Agent 通过 MCP 操作用户界面，用户通过界面看到 Agent 做了什么
- **Agent-to-Agent**——Agent 之间通过 MCP 互相调度和审查

### 1.2 Session Tree — 非线性会话历史

Agor 的会话不是线性的，是树。

```
         CEO 需求（root session）
              │
        ┌─────┴─────┐
        │  spawn    │  spawn
        ▼           ▼
    前端开发      后端开发      ← 子任务，各自独立 worktree
        │           │
    ┌───┴───┐       │
    │ fork  │       │
    ▼       ▼       ▼
  Codex  Claude   完成        ← 同一子任务，两个 Agent 分叉探索
  方案   方案
    │       │
    └───┬───┘
        ▼
      合并比较                  ← 父 session 汇总
```

**Fork**: 从当前 session 的某个状态点分叉，创建同级兄弟 session。两条路径各自独立，最后比较结果。  
**Spawn**: 创建子 session，专注一个子任务。父 session 可以监控、干预、汇总。

每个 message 记录 git SHA（如 `31239a11`），形成从对话到代码状态的完整审计链。

### 1.3 Worktree Manager — git 原生工作单元

Agor 把 git worktree 当作原子工作单元。

```
~/.agor/worktrees/
├── wt-abc123/          ← "实现用户登录" (分支: feat/login)
│   ├── src/...
│   ├── .env (自动生成端口 3001)
│   └── CLAUDE.md
├── wt-def456/          ← "审查登录模块" (分支: review/login)
│   └── ...
└── wt-ghi789/          ← "修复登录bug" (分支: fix/login-timeout)
```

每个 worktree:
- 有自己的 git 分支（独立 commit、push、PR）
- 自动分配不冲突的端口（3001, 3002, 3003...）
- 任务完成 → worktree 可 merge → 可删除
- 任务失败 → worktree 保留现场 → 可 resume

### 1.4 Services Layer — 胶水层

FeathersJS 的双通道（REST + WebSocket）统一了前后端通信。所有操作通过 Feathers Service：
- 写 LibSQL 数据库
- 广播 WebSocket 事件（给 UI）
- 暴露 MCP tools（给 Agent）

**一个操作，三个通道同时更新。**

### 1.5 其他关键能力

| 能力 | 实现 |
|------|------|
| Zone Trigger | 画布上画一块区域，拖 worktree 进去 → 自动触发模板 prompt |
| Cron Scheduler | daemon 内置定时器，支持心跳检查、自动审计 |
| Session Token | 每个 Agent 会话自动签发 MCP token，会话结束回收 |
| Multiplayer | Feathers WebSocket 实时同步光标、评论、facepile |
| Agent SDKs | Claude/Codex/Gemini 各自通过 JSON-RPC 2.0 接入 MCP |

---

## 二、ai-factory vs Agor 对照

| 维度 | ai-factory 现在 | Agor | 差距 |
|------|----------------|------|------|
| **Agent 接入** | bridge.py 每个后端写 adapter | MCP endpoint 统一协议 | 大 — 每加一个后端要写一套 adapter |
| **工作单元** | Workshop (Path 目录隔离) | Git worktree (分支+目录+端口) | 中 — 缺 git 原生能力和端口管理 |
| **会话历史** | RunSnapshot (线性 checkpoint) | Session Tree (树形 fork/spawn) | 大 — 不能分叉探索替代方案 |
| **任务分派** | 手动选工作流模板 + 输入 task | Zone trigger + spawn + 事件驱动 | 中 — 缺自动化触发 |
| **多 Agent 协同** | 工作流 DAG 静态定义节点 | MCP spawn 动态创建子任务 | 大 — DAG 只能在事前定义 |
| **端口管理** | 无 | 自动分配唯一端口，防冲突 | 小 — 目前多 Agent 场景少 |
| **实时同步** | WebSocket (board 频道) | Feathers REST+WS 双通道 | 小 — 基本够用 |
| **定时调度** | APScheduler (进程内) | Daemon 内置 cron | 小 — 功能等价 |
| **多人协作** | 无 | 实时光标、评论、facepile | 低优先级 — 单人场景为主 |

---

## 三、升级方案

### Phase 1: MCP Server（最大杠杆，最小改动）

**目标**: 用 MCP endpoint 替代 bridge.py 的多 adapter 模式。新增 Agent 后端零代码。

```
现在:                              改后:

Claude → bridge.py (自定义)        Claude ─┐
Codex  → codex_bridge.py (要新写)  Codex  ─┤→ gateway/mcp/
Gemini → gemini_bridge.py (要新写) Gemini ─┘  (JSON-RPC 2.0)

                                    后端只管 CLI 调用，
                                    和 ai-factory 的通信统一走 MCP
```

**具体改动**:
1. `gateway/mcp/` — 新增 MCP Server（FastAPI 子路由，FastMCP 或手写）
2. 暴露 tools: `run_agent`, `run_workflow`, `read_board`, `spawn_session`, `get_status`
3. 每个 session 签发 token，关联 workspace 和权限
4. `bridge.py` 保留兼容，新 Agent 后端直接用 MCP

**收益**:
- 新增 Claude/Codex/Gemini 后端 → 零代码
- Agent 可以互相调用（通过 MCPtool `spawn_session`）
- 用户通过界面看到 Agent 做了什么（双向同步）

### Phase 2: Worktree Manager

**目标**: Workshop 从 Path 目录升级为 git worktree。每个 Agent 任务自动创建独立分支。

**具体改动**:
1. `factory/worktree/` — 新模块
   - `worktree_manager.py` — git worktree CRUD（创建/列表/合并/清理）
   - `port_allocator.py` — 防止多 Agent 端口冲突
   - `env_manager.py` — 每个 worktree 独立 .env 和端口
2. `factory/org.py` Workshop — 内部改用 git worktree
3. 前端 — worktree 状态可视化（分支名、commit、端口）

**收益**:
- Agent 产出天然带 git history
- 不同 Agent 的产出可以 diff、merge
- 任务失败 worktree 保留现场，可 resume
- 多人/多 Agent 并行时互不干扰

### Phase 3: Session Tree

**目标**: 线性 RunSnapshot → 树形 SessionTree。支持 fork 和 spawn。

**具体改动**:
1. `factory/workflow/session_tree.py` — 替代 snapshot.py
   - 数据模型: `SessionNode { id, parentId, agentId, worktreeId, status, messages[] }`
   - `fork(sessionId)` → 创建兄弟 session，从同一状态点分叉
   - `spawn(sessionId, subtask)` → 创建子 session，专注子任务
   - 树查询: `getAncestors()`, `getSiblings()`, `getTree()`
2. 工作流 DAG 新增边类型: `fork`, `spawn`（区分于静态 `depends_on`）
3. 前端 — 画布展示树形结构（父→子→兄弟）

**收益**:
- "Claude vs Codex 谁写得好" → fork 两个 session，自动比较
- 复杂任务自动拆解 → spawn 子任务
- 完整的决策历史树 → 可审计、可回溯

### Phase 4: Zone/Trigger 系统

**目标**: 工作流模板从手动选择升级为事件驱动触发。

**具体改动**:
1. `factory/trigger/` — 新模块
   - 触发条件: manual、on_event、on_schedule、on_webhook
   - 绑定到工作流模板
2. 前端 — 看板/画布上配置触发规则

---

## 四、实施优先级

| 优先级 | Phase | 工作量 | 收益 |
|--------|-------|--------|------|
| **P0** | MCP Server | 3-5天 | 一个协议接所有 AI 后端，Agent-to-Agent 通信 |
| **P1** | Worktree Manager | 2-3天 | git 原生工作单元，分支/diff/merge |
| **P1** | Session Tree | 3-4天 | 非线性的 fork/spawn 会话历史 |
| **P2** | Zone/Trigger | 2-3天 | 事件驱动的工作流自动化 |

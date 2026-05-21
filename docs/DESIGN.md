# AI 工厂模板化开发平台 — 方案设计

版本：v0.1.0
日期：2026-05-21
状态：方案设计阶段

---

## 版本规范

遵循语义化版本 (Semantic Versioning 2.0.0)：`MAJOR.MINOR.PATCH`

| 维度 | 规则 |
|------|------|
| **MAJOR** | 架构不兼容变更、工厂 API 破坏性修改 |
| **MINOR** | 向后兼容的新功能（新增车间类型、工作流模板、Agent 模板） |
| **PATCH** | 向后兼容的 bug 修复、性能优化、文档更新 |

### 开发阶段版本

| 阶段 | 版本范围 | 含义 |
|------|---------|------|
| 方案设计 | 0.1.x | 架构设计、技术选型、原型验证 |
| Phase 1 | 0.2.x | 单车间核心骨架（已完成，commit `5e1fb51`） |
| Phase 2 | 0.3.x | 记忆系统 + Agent 执行引擎 |
| Phase 3 | 0.4.x | 看板监控 + MCP 市场对接 |
| Phase 4 | 0.5.x | 多车间 + 工作流 DAG 调度 |
| Phase 5 | 0.6.x | 通讯插件（Channel）+ 记忆进化 |
| Phase 6 | 0.7.x | WebUI 管理后台 |
| Phase 7 | 0.8.x | 自我进化引擎（GEPA） |
| Phase 8 | 0.9.x | 安全加固、性能优化、文档完善 |
| 正式发布 | 1.0.0 | 首个稳定版本，开源 |

### 版本号记录约定

- 每次 commit 须在 commit message 中标注影响范围，不强制标注版本号
- 每个 Phase 完成时打 tag：`v0.2.0`、`v0.3.0` 等
- 版本号在 `pyproject.toml` 中维护单一来源

---

## 1. 项目定位

一个开源、自进化、多 Agent 协作的 AI 工厂模板化开发平台。

**一句话：** 壳固定、组织可变、任意创建车间。每个车间是一个有记忆、会进化的 AI 团队。

**对标定位：**

| | 工厂平台 | OpenClaw | Hermes | OpenHuman |
|------|---------|---------|--------|-----------|
| 多 Agent 协作 | ✅ 原生车间 | ✅ 绑定路由 | ⏳ Phase 2-4 | ✅ 共享 Memory Tree |
| 跨会话记忆 | ✅ Memory Tree | 文件级 | ✅ 4 层记忆 | ✅ 3 层树 |
| 自我进化 | ✅ GEPA | ❌ | ✅ GEPA | ⏳ Subconscious Loop |
| 插件生态 | ✅ MCP 标准 | ❌ 自建 SDK | ✅ Skill.md | ⏳ QuickJS 沙箱 |
| 管理后台 | ✅ WebUI | ⏳ CLI | ⏳ CLI | ✅ 桌面 App |
| 通讯集成 | ✅ Channel 插件 | ✅ 20+ | ✅ 20+ | 桌面为主 |

---

## 2. 架构全景图

```
┌──────────────────────────────────────────────────────────────┐
│                        WebUI 管理后台                        │
│         React + shadcn/ui + 看板（4gaBoards/Vikunja）        │
├──────────────────────────────────────────────────────────────┤
│                       Gateway 网关层                         │
│              FastAPI WebSocket + REST API                    │
│              单进程，与 nanobot gateway 一致                  │
├──────────────┬──────────────────────────────┬────────────────┤
│  通讯插件层   │        工厂核心层            │   MCP 市场层    │
│              │                              │                │
│  WeChat      │  ┌────────────────────────┐  │  MCP Client    │
│  Feishu      │  │    车间（Workshop）      │  │  Skill.md      │
│  Discord     │  │  ┌──────┐ ┌──────┐     │  │  Tool Registry │
│  Slack       │  │  │Agent1│ │Agent2│ ... │  │                │
│  ...         │  │  └──────┘ └──────┘     │  │                │
│              │  │  共享 Topic Memory      │  │                │
│              │  └────────────────────────┘  │                │
│              │                              │                │
│              │  ┌────────────────────────┐  │                │
│              │  │     工作流引擎          │  │                │
│              │  │   DAG 调度 + 角色分工   │  │                │
│              │  └────────────────────────┘  │                │
├──────────────┴──────────────────────────────┴────────────────┤
│                       记忆系统（Memory Tree）                  │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────┐   │
│  │  Source Tree │→ │  Topic Tree │→ │   Global Tree       │   │
│  │  Agent 级    │  │  车间级      │  │   工厂级             │   │
│  │  会话+工具    │  │  主题聚合    │  │   daily→weekly→...  │   │
│  └─────────────┘  └─────────────┘  └─────────────────────┘   │
│                                                               │
│  SQLite + FTS5 + sqlite-vec (机器层)                          │
│  Obsidian 兼容 Markdown (人类层)                               │
├──────────────────────────────────────────────────────────────┤
│                      自我进化引擎（GEPA）                      │
│  反思变异 → 帕累托前沿选择 → 自然语言反馈                       │
└──────────────────────────────────────────────────────────────┘
```

---

## 3. 模块设计

### 3.1 记忆系统 — Memory Tree

**来源：** OpenHuman Memory Tree + Hermes 4 层记忆

```
Global Tree（工厂级）
  ├── daily → weekly → monthly → yearly 级联摘要
  ├── Bucket-Seal 压缩：50k token 或 10 条触发封桶
  └── 原始数据永不删除，可下钻到原始会话

Topic Tree（车间级）
  ├── 自动按实体（人/项目/任务）跨 Agent 聚合
  ├── 车间内所有 Agent 共享
  └── [[wikilinks]] 链接到 Source Tree 原文

Source Tree（Agent 级）
  ├── 每个 Agent 一棵树：会话 JSONL + 工具输出
  ├── L0 缓冲 → L1 摘要 → L2 全局摘要
  └── 可独立检索，不依赖全局树
```

**存储引擎：** SQLite WAL 模式 + FTS5 全文搜索 + sqlite-vec 向量扩展
**人读层：** Obsidian 兼容 Markdown，`[[wikilinks]]` 链接，`#tag` 分类

### 3.2 车间系统 — Workshop

**来源：** Hermes 实例模型 + ClawTeam git worktree 隔离

```
车间 = 独立 Hermes 实例
  ├── 独立工作区（git worktree 隔离）
  ├── 独立记忆分区（Topic Tree）
  ├── 独立 Agent 集合（模板实例化）
  ├── 独立 Skill 库（自学习积累）
  └── 车间间通过 Global Tree 共享组织知识
```

**Agent 类型：**

| 模板 | 类型 | 权限 |
|------|------|------|
| super | 超级 Agent | 全工具 + sub-agent spawn + shell |
| reviewer | 审查 Agent | 只读审查，不可写/执行 |
| analyst | 分析 Agent | 搜索+数据，不可改代码 |
| writer | 写作 Agent | 内容创作，不可改代码/执行 |

### 3.3 工作流引擎 — Windmill

**选择：** [Windmill](https://github.com/windmill-labs/windmill) — AGPL，8k+ stars，Python 原生

```
Windmill Flow
  ├── 可视化拖拽编辑 + 代码模式切换
  ├── 每个节点 = Python 脚本（Agent 调用）
  ├── 条件分支 / 并行 / 循环 / 错误处理
  ├── Webhook 触发 + 定时任务
  ├── 自带 WebUI 管理后台
  └── 工厂的车间 = Windmill 的 Workspace
```

**为什么不用其他方案：**

| 方案 | 否决理由 |
|------|---------|
| n8n | Commons Clause（fair-code），不可开源商用 |
| Prefect | 管道代码定义，可视化编辑差 |
| 自研 DAG | 重复造轮子，Windmill 已解决 |
| Temporal | 需要额外部署服务，太重 |

**集成方式：**
- Windmill 作为工作流编排层嵌入工厂
- Agent 是 Windmill 的 Python 脚本节点
- 车间创建一个工作流 = Windmill Flow
- Windmill WebUI 直接复用为管理后台

### 3.4 MCP 市场对接

**来源：** Anthropic MCP 协议标准

```
MCP Client 层
  ├── 工具发现：自动列出 MCP Server 提供的 tools
  ├── 工具调用：标准 JSON-RPC 2.0 协议
  ├── Skill 管理：Skill.md 格式，渐进披露（目录优先，详情按需）
  └── 本地缓存：常用工具/Skill 本地缓存，离线可用
```

**不自建协议。** 工厂是 MCP 生态的消费者，不是竞争者。

### 3.5 通讯插件 — Channel

**来源：** OpenClaw 20+ Channel 架构（只参考模式，不参考安全实现）

```
Channel 插件接口：
  ├── register_channel(name, adapter)
  ├── inbound: 消息接收 → 路由到对应车间/Agent
  ├── outbound: Agent 回复 → 格式化 → 发送
  └── lifecycle: start / stop / health check
```

初期支持：WeChat、Feishu（从旧项目迁移），后续扩展 Discord/Slack

### 3.6 看板监控

**Fork 候选：**

| 候选 | 许可 | UI | API | 资源 |
|------|------|-----|-----|------|
| **4gaBoards**（推荐） | MIT | 最美 | REST + WebSocket | 150MB |
| Vikunja | AGPL | 干净 | REST + Webhooks | 80MB |

**集成方式：** 工厂 API 自动创建/更新看板卡片，状态实时同步

### 3.7 自我进化引擎 — GEPA

**来源：** Hermes GEPA 论文（ICLR 2026 Oral）

```
进化闭环：
  执行任务 → 记录轨迹 → 反思变异 → 帕累托前沿选择 → 生成/更新 Skill
```

- 触发条件：5+ 工具调用且克服了错误 → 创建候选 Skill
- 评审机制：分叉 reviewer Agent 静默评估，不委托 LLM 做触发决策
- 安全边界：所有进化产出需人工 PR review，不自动合入

---

## 4. 数据流

```
用户消息（Channel/WebUI/CLI）
  │
  ▼
Gateway 路由 → 目标车间 → 目标 Agent
  │
  ▼
Agent 执行循环：
  1. Context 组装（Source Tree + Topic Tree + Global Tree 相关节点）
  2. LLM 推理（模型路由：深度任务 → 前沿模型，简单 → 廉价模型）
  3. 工具调用（MCP 工具 + 内置工具 + TokenJuice 输出压缩）
  4. 回复生成 + 去重
  │
  ▼
记忆写入（异步）：
  ├── 会话 JSONL → Source Tree L0 缓冲
  ├── 工具输出 → TokenJuice 压缩 → Source Tree
  └── Bucket-Seal 触发 → LLM 摘要 → 上卷到 L1/L2
  │
  ▼
看板更新：任务状态变更 → API → 看板 WebSocket 实时推送
```

---

## 5. 技术选型

| 层 | 技术 | 理由 |
|----|------|------|
| **Agent 运行时** | nanobot（不改一行） | 核心 3500 行，MIT，作为 shell |
| **工厂层语言** | Python 3.11+ | 与 nanobot 同语言，生态成熟 |
| **记忆存储** | SQLite + FTS5 + sqlite-vec | 零运维，WAL 并发，单机够用 |
| **人读知识库** | Obsidian 兼容 Markdown | 可读可编辑可带走，[[wikilinks]] |
| **Web 框架** | FastAPI | 异步，WebSocket 原生支持 |
| **看板前端** | 4gaBoards fork（React） | MIT，最美 UI，WebSocket 实时 |
| **管理后台** | Windmill WebUI + React/shadcn | Windmill 自带 WebUI 复用 |
| **工作流引擎** | Windmill（AGPL） | Python 原生，可视化拖拽编辑 |
| **MCP 集成** | mcp Python SDK | Anthropic 官方 |
| **Token 压缩** | TokenJuice 移植 | OpenHuman 验证过，80% 节省 |
| **自我进化** | GEPA 自研 | 学术验证，零模型训练 |

---

## 6. Phase 划分

### Phase 1（已完成）：核心骨架 — v0.2.0

- [x] Pydantic 配置验证（AgentSpec / DepartmentSpec / WorkflowSpec / OrgSpec）
- [x] org.yaml → OrgEngine → Workshop 链路
- [x] Agent 模板系统（4 个模板）
- [x] 工作流模板库（5 个模板）
- [x] 制品仓库接口（Warehouse + INDEX.md）
- [x] `python3 entrypoint.py` 跑通

### Phase 2：记忆系统 + Agent 执行 — v0.3.0

- [x] Memory Tree 实现（Source → Topic → Global）
- [x] Bucket-Seal 级联压缩引擎
- [x] SQLite + FTS5 存储层
- [x] Obsidian Markdown 双写导出
- [x] TokenJuice 压缩管线移植
- [x] nanobot AgentRunner 接入实际执行

### Phase 3：看板 + MCP — v0.4.0

- [x] 轻量 SQLite 看板（兼容 4gaBoards 模型）— Board/List/Card CRUD
- [x] 工厂 API → 看板卡片自动同步（KanbanSync + TaskEvent）
- [x] MCP Client 实现（stdio + streamable HTTP transport）
- [x] MCP 工具市场对接（内置 6 个官方 server + 搜索）
- [x] Skill.md 管理层（渐进披露加载 + 车间级安装管理）
- [x] FastAPI Gateway（REST + WebSocket 实时同步）

### Phase 4：多车间 + 工作流 — v0.5.0

- [x] Windmill 集成层（factory/windmill/ 占位 + 文档）
- [x] DAG 工作流执行引擎（拓扑排序 + 阶段执行 + 门控循环）
- [x] Windmill Flow 模板（5 个内置工作流：code-review/market-analysis/content-creation/legal-review/simple）
- [x] 动态创建车间（运行时 CLI + API，持久化到 org.yaml）
- [x] 车间间通信（WorkshopBridge — Warehouse 产品共享 + Global Tree 记忆桥接）
- [x] Gateway 扩展（/api/workshops CRUD, /api/workflows, /api/workshops/{name}/run）
- [x] CLI 扩展（workshop create/list/show/delete/run, workflow list/show）

### Phase 5：通讯 + 进化 — v0.6.0

- [x] Channel 插件接口（Adapter 模式 + 全局注册表 + DummyChannel）
- [x] GEPA 自我进化引擎（Reflect → Mutate → Select → Review 闭环）
- [x] 三级记忆分层跨树迁移（TopicTree.aggregate_from + GlobalTree.rollup_from）
- [ ] WeChat / Feishu 迁移（Phase 7 随 WebUI 一起）

### Phase 6：WebUI — v0.7.0

- [ ] React + shadcn/ui 管理后台
- [ ] 车间可视化管理
- [ ] Agent 实时状态监控
- [ ] 知识库浏览/编辑界面

### Phase 7：进化引擎完善 — v0.8.0

- [ ] GEPA 反思变异实现
- [ ] 帕累托前沿选择
- [ ] Skill 自动创建/更新/淘汰
- [ ] 进化日志和回滚

### Phase 8：打磨开源 — v0.9.0

- [ ] 安全加固（沙箱隔离、命令白名单）
- [ ] 性能优化
- [ ] 完整文档（README、CONTRIBUTING、ARCHITECTURE）
- [ ] 开源准备（LICENSE、CODE_OF_CONDUCT、Issue/PR 模板）

### 正式发布 — v1.0.0

- [ ] 生产可用性验证
- [ ] 多平台部署测试
- [ ] 社区建设启动

---

## 7. 安全模型

| 层 | 策略 | 来源 |
|----|------|------|
| **Agent 执行** | 死规则白名单 > LLM 判断 | Hermes |
| **工具调用** | 分级权限（只读/写入/执行） | 工厂 Agent 模板 |
| **技能沙箱** | QuickJS 隔离 + 内存/时间硬限制 | OpenHuman |
| **自主行动** | 只观察，不自动执行写入 | OpenHuman Subconscious Loop |
| **进化产出** | 所有变更需人工 PR review | Hermes |
| **密钥管理** | 环境变量 + OS Keychain，永不落地 | OpenHuman |

---

## 8. 目录结构

```
ai-factory/
├── config/                 # 配置层
│   ├── schema.py           # Pydantic 模型
│   └── org.yaml            # 组织配置
├── factory/                # 工厂核心
│   ├── org.py              # OrgEngine + Workshop
│   ├── template.py         # Agent 模板库
│   ├── workflow.py         # 工作流模板库
│   ├── warehouse.py        # 制品仓库
│   ├── memory/             # Memory Tree 引擎（Phase 2）
│   ├── windmill/            # Windmill 集成层（Phase 4）
│   ├── channel/            # Channel 插件接口（Phase 5）
│   ├── evolution/          # GEPA 进化引擎（Phase 5）
│   └── mcp/                # MCP Client（Phase 3）
├── gateway/                # Gateway 网关
│   ├── server.py           # FastAPI + WebSocket
│   └── routes/             # API 路由
├── webui/                  # WebUI 管理后台（Phase 6）
├── kanban/                 # 看板 fork（Phase 3）
├── templates/              # Agent 模板 YAML
│   ├── super.yaml
│   ├── reviewer.yaml
│   ├── analyst.yaml
│   └── writer.yaml
├── workflows/              # 工作流模板 YAML
├── entrypoint.py           # 工厂启动入口
├── pyproject.toml
└── docs/
    └── DESIGN.md           # 本文档
```

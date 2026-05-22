# Nexus AI Works — 架构文档

## 设计理念

**壳固定、组织可变。** 平台提供固定的核心框架（记忆、工作流、安全），
用户任意创建车间——每个车间是独立工作区，包含自己的 Agent 团队、
工作流模板、看板和记忆分区。

## 技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| Agent 运行时 | claw-code-agent (~36,000 行, 65 tools) | Claude Code 完整 Python 移植 |
| 引擎桥接层 | factory/engine/bridge.py | 唯一 vendor 导入点，引擎可替换 |
| 工厂层 | Python 3.11+ | 与 claw-code-agent 同语言 |
| 记忆存储 | SQLite WAL + FTS5 + 文件型语义记忆 V2 | 机器读 + 人可读双模式 |
| 人读知识库 | Obsidian Markdown | [[wikilinks]] 可带走 |
| Web 框架 | FastAPI | 异步，WebSocket + SSE 原生 |
| 数据模型 | Pydantic v2 (配置) + frozen dataclass (领域) | 类型安全 |
| 测试 | pytest + pytest-asyncio | 314 tests |

## 模块设计

### 0. 引擎桥接层 (factory/engine/)

**唯一 vendor 导入边界。** bridge.py 封装 claw-code-agent 的 LocalCodingAgent、
ModelConfig、AgentRuntimeConfig、BudgetConfig、AgentRunResult，对外暴露 Nexus 自有类型。
tools.py 提供工具名映射（Nexus 符号名 → claw-code 工具名）+ 权限过滤。
pool.py 管理 Agent 池（ThreadPoolExecutor(8) + asyncio.Semaphore(8) + 超时控制）。

### 1. 组织架构 (factory/org.py)

OrgEngine 加载 org.yaml → 创建 Workshop 实例 → 实例化 Agent 团队。
每个 Workshop 有独立工作区、Agent 集合、工作流引擎。

### 2. 记忆系统 (factory/memory/)

三级 Memory Tree：
- **Source Tree** (Agent 级) — 会话 JSONL + 工具输出，L0 缓冲 → L1/L2 摘要
- **Topic Tree** (车间级) — 跨 Agent 按实体/主题聚合
- **Global Tree** (工厂级) — daily → weekly → monthly 级联摘要

Bucket-Seal 压缩：50k token 或 10 条触发封桶，LLM 摘要上卷。
SQLite WAL + FTS5 机器读，Obsidian Markdown 人读。

### 3. 工作流引擎 (factory/workflow/)

DAG 拓扑排序 → 逐阶段执行 → 审核门控循环。
内置 simple 默认工作流（单阶段直通）。用户通过 YAML 文件自定义工作流模板。

门控逻辑：review 阶段输出匹配 pass/fail 关键词 →
通过则继续，不通过则跳回上游阶段重试（最多 3 次）。

### 4. 看板监控 (factory/kanban/)

SQLite 轻量看板：Board → List → Card。
Agent 任务自动同步 → 卡片状态变更 → WebSocket 实时推送。

### 5. MCP 集成 (factory/mcp/)

封装 mcp Python SDK：stdio + streamable HTTP transport。
内置 6 个官方 MCP 服务器：filesystem, github, postgres, brave-search, memory, slack。
工具发现 + 调用 + 本地缓存。

### 6. Skill 管理 (factory/skills/)

渐进披露：SkillIndex (目录级) → Skill (完整 body)。
YAML front matter 解析，车间级安装/卸载/启用。

### 7. Channel 插件 (factory/channel/)

Adapter 模式：统一接口，多通道接入。
全局注册表 + inbound/outbound 路由。

### 8. GEPA 进化引擎 (factory/evolution/)

Reflect → Mutate → Select → Review 闭环。
触发条件：5+ 工具调用 + 克服错误 → 创建候选 Skill。
安全边界：所有进化产出需人工确认。

## 数据流

```
用户消息 (CLI / Gateway / Channel)
  └→ Gateway 路由 → 目标车间 → 目标 Agent
       └→ 上下文组装 (Source + Topic + Global Tree)
       └→ LLM 推理 → 工具调用 (MCP + 内置 + TokenJuice)
       └→ 回复生成
       └→ 记忆写入 (异步)
            ├→ Source Tree L0 缓冲
            ├→ TokenJuice 压缩
            └→ Bucket-Seal → 上卷到 L1/L2
       └→ 看板更新 (WebSocket 实时推送)
       └→ GEPA 分析轨迹 → 候选 Skill (如果触发)
```

## 安全模型

| 层 | 策略 |
|----|------|
| Agent 执行 | 死规则白名单 > LLM 判断，已接入工具拦截器 |
| Shell 命令 | claw-code-agent bash_security + 禁止模式 + 命令白名单 |
| 路径访问 | 工作区沙箱 + 禁止路径清单 + 路径穿越检测 |
| 工具权限 | 按 AgentSpec.permissions 过滤注册工具（shell/file_write/subagent） |
| 密钥管理 | 代码中检测硬编码密钥（9 种模式） |
| 预算控制 | BudgetConfig（token/成本/工具调用/模型调用/会话轮次上限） |
| 进化产出 | 人工 PR review 确认 |

## 测试

```bash
python3 -m pytest factory/ gateway/ -v  # 261 tests
```

测试覆盖：memory 13, tokenjuice 6, kanban 44, mcp 19, skills 25,
gateway 35, workflow 20, workshop 36, channel 26, evolution 38, security 24。

# 本地模板库 — 设计方案

## 概述

用户在车间里生产出可复用的资产（工作流、Agent 配置、角色），入库保存到「我的模板」库中。以后建新车间的时直接从库里挑选安装，避免重复配置。

模板库是本地私有的；官方模板商店（订阅制收费）是后续商业层，共享同一种数据格式。

## 命名规范

| 概念 | 中文名 | CLI 前缀 | 说明 |
|------|--------|----------|------|
| 整体 | 模板库 / 我的模板 | `library` | 用户自己积累的可复用资产 |
| 工作流模板 | 生产方案 | `library workflow` | DAG 节点编排 |
| Agent 配置 | 智能体配置 | `library agent` | 角色、权限、模型、预算 |
| 角色模板 | 岗位规格 | `library role` | 系统提示词、默认权限 |

## 操作

| 操作 | CLI | 说明 |
|------|-----|------|
| 保存到库 | `library save <type> <name>` | 把车间里做好的方案/配置入库 |
| 浏览列表 | `library list <type>` | 按类型列出已保存的模板 |
| 查看详情 | `library show <type> <name>` | 展开某个模板的完整信息 |
| 安装到车间 | `library install <type> <name> --workshop <w>` | 挑一个模板装到目标车间 |
| 从库删除 | `library delete <type> <name>` | 移除模板 |

## 数据模型

### 模板条目 `LibraryEntry`

所有类型的模板共用此索引记录：

| 字段 | 类型 | 说明 |
|------|------|------|
| id | str | 唯一 ID |
| entry_type | enum | workflow / agent / role |
| name | str | 模板名称 |
| description | str | 简短说明 |
| category | str | 分类（复用 PackageManifest 的 12 分类） |
| tags | list[str] | 标签 |
| source_workshop | str | 来源车间名 |
| version | str | 版本号，默认 "1.0.0" |
| created_at | str | 入库时间 |
| body | str | 模板内容（YAML） |

### 分类（复用已有）

来自 `factory/workflow/package.py` 的 `PACKAGE_CATEGORIES`：市场分析、内容创作、代码工具、数据处理、法务合规、营销推广、客服支持、项目管理、金融分析、教育培训、医疗健康、其他。

## 存储

```
~/.nexus/library/
  library.db          # SQLite 索引（entry 表 + FTS5 全文搜索）
  workflows/
    {name}.yaml       # 工作流模板正文
  agents/
    {name}.yaml       # Agent 配置正文
  roles/
    {name}.yaml       # 角色模板正文
```

SQLite 存元数据索引；YAML 文件存内容正文。支持直接编辑 YAML 文件而不破坏索引，也支持只读索引搜索。

## 架构组件

### 新增文件

| 文件 | 职责 |
|------|------|
| `factory/library/models.py` | `LibraryEntry` Pydantic 模型 |
| `factory/library/store.py` | `LibraryStore` — SQLite + YAML 读写 |
| `gateway/routes/library.py` | FastAPI APIRouter，5 个端点 |
| `webui/src/components/TemplateLibrary.tsx` | 前端「我的模板」页面 |
| `factory/cli.py`（追加）| CLI `library` 命令处理 |

### 复用已有代码

| 依赖 | 用途 |
|------|------|
| `factory/workflow/models.py` | WorkflowTemplate 序列化 |
| `config/schema.py` | AgentSpec、RoleSpec 模型 |
| `factory/workflow/package.py` | PACKAGE_CATEGORIES |
| `factory/skills/repo.py` | SkillRepo SQLite 模式参考 |
| `factory/workshop/manager.py` | WorkshopManager（安装模板到车间） |

## API 端点

| Method | Path | 说明 |
|--------|------|------|
| `POST` | `/api/library/{entry_type}` | 保存模板到库 |
| `GET` | `/api/library/{entry_type}` | 列出模板（支持 ?search=&category=&tag=） |
| `GET` | `/api/library/{entry_type}/{name}` | 查看模板详情 |
| `POST` | `/api/library/{entry_type}/{name}/install` | 安装到指定车间 |
| `DELETE` | `/api/library/{entry_type}/{name}` | 从库删除 |

## CLI 命令

```
library save workflow <name> --workshop <w> --desc "..." --tags a,b
library save agent <name> --workshop <w>
library save role <name> --role-file <path>
library list workflow [--search <q>] [--category <c>]
library list agent
library list role
library show workflow <name>
library install workflow <name> --workshop <w>
library delete workflow <name>
```

## 作用域差异

三种模板的作用域不同，影响「从哪读、装去哪」：

| 类型 | 作用域 | 入库时从哪读 | 安装时装去哪 |
|------|--------|------------|------------|
| workflow | 全局 | `WorkflowStore`（所有车间共用） | 全局 `WorkflowStore` |
| agent | 车间级 | 指定车间的 agent 配置 | 目标车间 |
| role | 全局 | `config/roles/` 下的 YAML 文件 | 全局 `config/roles/` |

工作流是全局的流水线设计，安装后任何车间都能引用。Agent 配置是车间专属的，安装时必须指定目标车间。

## 关键流程

### 入库流程

以 workflow 为例：
1. 用户在工作流编辑器中设计好流水线
2. 执行 `library save workflow <name>`
3. `LibraryStore.save_workflow()` — 从 `WorkflowStore.load(name)` 读取 → YAML 序列化 → 写入 body → 插入 SQLite 索引

以 agent 为例：
1. 用户在车间中配置好 Agent
2. 执行 `library save agent <name> --workshop <w>`
3. `LibraryStore.save_agent()` — 从 `WorkshopManager.list_agents(w)` 找到目标 agent → AgentSpec 转 YAML → 入库

### 安装流程

以 workflow 为例：
1. `library install workflow <name>` → 读取 YAML body → 反序列化为 WorkflowTemplate → 写入 `WorkflowStore.save()`
   → 全局可用

以 agent 为例：
1. `library install agent <name> --workshop <target>` → 读取 YAML body → 反序列化为 AgentSpec → 调用 `WorkshopManager.add_agent(target, spec)`

## 测试

- `factory/library/test_store.py` — 单元测试（store CRUD + install）
- `gateway/test_server.py` — 追加 API 测试
- 覆盖率目标 ≥ 80%

## 不做

- 模板版本历史（保持简单，只存最新版本）
- 模板依赖关系（不追踪 workflow 引用了哪些 agent）
- 远端商店（后续独立设计）
- 模板评分/评论（商店侧功能）

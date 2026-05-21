# AI 工厂 (AI Factory)

开源、自进化、多 Agent 协作的模板化 AI 开发平台。

**壳固定、组织可变、任意创建车间。** 每个车间是一个有记忆、会进化的 AI 团队。

## 快速开始

```bash
# 安装依赖
pip install -e .

# 查看工厂状态
python3 entrypoint.py

# 执行任务
python3 entrypoint.py --run "分析项目结构并输出报告"

# 启动 Gateway
python3 entrypoint.py serve
# 访问 http://127.0.0.1:8600/docs

# 车间管理
python3 entrypoint.py workshop list
python3 entrypoint.py workshop create 新车间
python3 entrypoint.py workshop run 新车间 code-review "审查 PR"

# 看板
python3 entrypoint.py kanban create my-board
python3 entrypoint.py kanban boards

# MCP 工具市场
python3 entrypoint.py mcp list
python3 entrypoint.py mcp search github

# 技能管理
python3 entrypoint.py skill list

# 工作流
python3 entrypoint.py workflow list
python3 entrypoint.py workflow show code-review

# 运行测试
python3 -m pytest factory/ gateway/ -v
```

## 架构

```
entrypoint.py          CLI 入口
gateway/               FastAPI REST + WebSocket 网关
factory/
  org.py               OrgEngine + Workshop
  runner.py            Agent 执行器 (nanobot 集成)
  template.py          Agent 模板库 (super/reviewer/analyst/writer)
  workflow/            DAG 工作流引擎 + 5 个内置模板
  memory/              Memory Tree (SQLite + FTS5 + Obsidian 双写)
  tokenjuice/          工具输出压缩 (5 步管线, 96 规则)
  kanban/              SQLite 看板 (Board/List/Card)
  mcp/                 MCP 客户端 (6 个内置市场工具)
  skills/              Skill.md 渐进披露管理层
  channel/             Channel 插件接口 (Adapter 模式)
  evolution/           GEPA 自我进化引擎
  workshop/            车间运行时管理 + 跨车间桥接
  windmill/            Windmill 集成层 (未来)
  security/            安全守卫 (命令白名单 + 路径防护 + 密钥检测)
config/                配置文件 (org.yaml, mcp_servers.yaml)
templates/             Agent 模板 YAML
```

## 版本

v0.9.0 — 平台内核完成，安全加固 + 文档完善。

## 许可

MIT

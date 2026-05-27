# Nexus AI Works 【重度框架 · 全功能版 · 含 WebUI】

## 项目

Nexus AI Works 是开源、自进化、多 Agent 协作的模板化开发平台。
壳固定、组织可变、任意创建车间。

**Python 3.11+**, **React + Vite + TypeScript + Tailwind v3** 前端。

## 代码风格

- `from __future__ import annotations`
- frozen dataclass 用于领域模型
- Pydantic v2 用于配置
- 类型注解全覆盖
- 无 emoji 在代码中
- 类级 pytest 测试，`@pytest.fixture` + `yield`

## 启动

```bash
python3 entrypoint.py                  # CLI
python3 entrypoint.py serve            # Gateway → :8600
cd webui && npm run dev                # WebUI → :5173
python3 -m pytest factory/ gateway/ -v # 314 tests
```

## 架构路径

```
entrypoint.py          CLI (7 个子命令)
gateway/server.py      FastAPI (20+ routes, WebSocket)
webui/src/             React 前端
factory/org.py         Workshop 管理
factory/workflow/      工作流引擎
factory/memory/        记忆系统
factory/kanban/        看板
factory/mcp/           MCP 客户端
factory/skills/        Skill 管理
factory/channel/       Channel 插件
factory/evolution/     GEPA 进化引擎
factory/security/      安全守卫
```

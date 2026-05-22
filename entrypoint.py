#!/usr/bin/env python3
"""Nexus AI Works 启动入口。"""

import argparse
import asyncio
import sys
from pathlib import Path

from factory.org import OrgEngine
from factory.workflow import WorkflowStore
from factory.workflow.package import validate_package
import yaml
from factory.memory import MemoryStore, SourceTree, VaultWriter
from factory.memory.tree import BucketSeal, dummy_summariser
from factory.runner import NexusAgentRunner
from factory.kanban import KanbanStore, KanbanSync, TaskEvent
from factory.mcp import MCPClient, MCPServerConfig, MCPRegistry
from factory.skills import SkillRepo


async def main():
    parser = argparse.ArgumentParser(description="Nexus AI Works — 模板化 AI 开发平台")
    sub = parser.add_subparsers(dest="command")

    # 全局可选参数
    parser.add_argument("--run", type=str, metavar="TASK", help="执行任务")
    parser.add_argument("--memory-stats", action="store_true", help="查看记忆树统计")
    parser.add_argument("--vault-path", type=str, default="~/.factory/vault", help="Obsidian vault 路径")
    parser.add_argument("--db-path", type=str, default="~/.factory/memory.db", help="SQLite 数据库路径")

    # Phase 3: Gateway 服务器
    serve_p = sub.add_parser("serve", help="启动 FastAPI gateway 服务器")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8600)

    # Phase 3: 看板管理
    kanban_p = sub.add_parser("kanban", help="看板任务管理")
    kanban_sub = kanban_p.add_subparsers(dest="kanban_cmd")
    list_boards = kanban_sub.add_parser("boards", help="列出所有看板")
    show_board = kanban_sub.add_parser("board", help="查看看板详情")
    show_board.add_argument("name", help="看板名称或 workshop 名称")
    create_board = kanban_sub.add_parser("create", help="创建新看板")
    create_board.add_argument("name", help="看板名称")
    create_board.add_argument("--workshop", default="", help="关联的工作区名称")

    # Phase 3: MCP 工具市场
    mcp_p = sub.add_parser("mcp", help="MCP 工具市场")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_cmd")
    mcp_list = mcp_sub.add_parser("list", help="列出已注册的 MCP 服务器")
    mcp_search = mcp_sub.add_parser("search", help="搜索 MCP 工具市场")
    mcp_search.add_argument("query")

    # Phase 3: Skills 管理
    skill_p = sub.add_parser("skill", help="Skill.md 技能管理")
    skill_sub = skill_p.add_subparsers(dest="skill_cmd")
    skill_list = skill_sub.add_parser("list", help="列出可用技能")
    skill_list.add_argument("--query", default="", help="按名称/触发词过滤")
    skill_list.add_argument("--workshop", default="__global__", help="按工作区过滤已安装")
    skill_show = skill_sub.add_parser("show", help="查看技能详情")
    skill_show.add_argument("name")
    skill_install = skill_sub.add_parser("install", help="安装技能到工作区")
    skill_install.add_argument("name")
    skill_install.add_argument("--workshop", default="__global__")

    # Phase 4: 工作区管理
    workshop_p = sub.add_parser("workshop", help="工作区管理")
    workshop_sub = workshop_p.add_subparsers(dest="workshop_cmd")
    ws_create = workshop_sub.add_parser("create", help="创建工作区")
    ws_create.add_argument("name", help="工作区名称")
    ws_create.add_argument("--workflow", default="simple", help="工作流模板")
    ws_create.add_argument("--agents", default="", help="Agent 模板列表，逗号分隔")
    ws_list = workshop_sub.add_parser("list", help="列出所有工作区")
    ws_run = workshop_sub.add_parser("run", help="执行工作流")
    ws_run.add_argument("name", help="工作区名称")
    ws_run.add_argument("workflow", help="工作流模板名")
    ws_run.add_argument("task", help="任务描述")
    ws_show = workshop_sub.add_parser("show", help="查看工作区详情")
    ws_show.add_argument("name")
    ws_delete = workshop_sub.add_parser("delete", help="删除工作区")
    ws_delete.add_argument("name")

    # Phase 4: 工作流管理
    wf_p = sub.add_parser("workflow", help="工作流管理")
    wf_sub = wf_p.add_subparsers(dest="workflow_cmd")
    wf_list = wf_sub.add_parser("list", help="列出所有工作流模板")
    wf_show = wf_sub.add_parser("show", help="查看工作流详情")
    wf_show.add_argument("name")

    # Phase 5: 模块管理 (export/import/remove)
    module_p = sub.add_parser("module", help="模块管理 (导出/导入/卸载)")
    module_sub = module_p.add_subparsers(dest="module_cmd")
    mod_export = module_sub.add_parser("export", help="导出工作区为 .nexus 包")
    mod_export.add_argument("workspace", help="要导出的工作区名称")
    mod_export.add_argument("--output", "-o", default=".", help="输出目录")
    mod_export.add_argument("--version", default="1.0.0", help="包版本")
    mod_import = module_sub.add_parser("import", help="导入 .nexus 包")
    mod_import.add_argument("package", help="包的路径")
    mod_import.add_argument("--force", action="store_true", help="覆盖已有工作区")
    mod_remove = module_sub.add_parser("remove", help="完全卸载工作区")
    mod_remove.add_argument("workspace", help="要卸载的工作区名称")
    mod_remove.add_argument("--force", action="store_true", help="跳过确认")
    mod_list = module_sub.add_parser("list", help="列出已安装模块")

    args = parser.parse_args()

    print("=" * 60)
    print("  Nexus AI Works v1.0.0")
    print("=" * 60)

    if args.command == "serve":
        await cmd_serve(args)
    elif args.command == "kanban":
        cmd_kanban(args)
    elif args.command == "mcp":
        await cmd_mcp(args)
    elif args.command == "skill":
        cmd_skill(args)
    elif args.command == "workshop":
        if args.workshop_cmd == "run":
            await cmd_workshop_run(args)
        else:
            cmd_workshop(args)
    elif args.command == "workflow":
        cmd_workflow(args)
    elif args.command == "module":
        cmd_module(args)
    elif args.run or args.memory_stats:
        await run_default(args)
    else:
        await run_default(args)


async def run_default(args):
    """默认模式：展示骨架状态 或 执行任务"""
    store = MemoryStore(args.db_path)
    org = OrgEngine("config/org.yaml")

    print(f"\n  组织架构: {len(org.spec.departments)} 个工作区")
    print(f"  制品仓库: {org.warehouse.root}")
    print(f"  工作流模板: {len(org.workflow_store.list_all())} 个")
    print(f"  Agent 模板: {len(org.templates.list_all())} 个")

    org.create_all()

    if args.memory_stats:
        show_memory_stats(store)
        return

    if args.run:
        await run_task(org, store, args.run, args.vault_path)
        return

    print(f"\n  工作区状态:")
    print(org.status())
    print(f"\n  制品仓库索引:")
    for dept, products in org.warehouse.index().items():
        for p in products:
            print(f"  - {dept}/{p}")
    print("\n  工厂骨架就绪")
    print("   python3 entrypoint.py --run '任务描述'      → 执行任务")
    print("   python3 entrypoint.py --memory-stats        → 记忆统计")
    print("   python3 entrypoint.py serve                 → 启动 Gateway")
    print("   python3 entrypoint.py kanban boards         → 查看看板")
    print("   python3 entrypoint.py mcp search <query>    → 搜索 MCP 工具")
    print("   python3 entrypoint.py skill list            → 列出技能")


async def run_task(org: OrgEngine, store: MemoryStore, task: str, vault_path: str):
    """执行任务：选择第一个工作区的 super Agent。"""
    departments = org.spec.departments
    if not departments:
        print("  没有配置工作区，请检查 config/org.yaml")
        return

    dept = departments[0]
    if not dept.agents:
        print("  该部门没有 Agent，请在 config/org.yaml 中配置")
        return
    agent_spec = dept.agents[0]
    workshop = next((w for w in org.workshops if w.name == dept.name), None)

    # 初始化看板同步
    kanban_store = KanbanStore()
    kanban_sync = KanbanSync(kanban_store, dept.name)

    print(f"\n  执行任务: {task}")
    print(f"  工作区: {dept.name}")
    print(f"  Agent: {agent_spec.name} ({agent_spec.type})")
    print(f"  模型: {agent_spec.model}")
    print()

    runner = NexusAgentRunner(
        agent_spec, workshop, store,
        vault_path=vault_path,
        kanban_sync=kanban_sync,
    )

    runner.record_chat("system", f"任务开始: {task}", "entrypoint")

    try:
        result = await runner.run(task)
        print("-" * 40)
        print(f"  结果:\n{result.content[:2000]}")
        print(f"\n  使用工具: {', '.join(result.tools_used) or '无'}")
        if result.error:
            print(f"  错误: {result.error}")
    except Exception as e:
        print(f"  执行失败: {e}")

    runner.record_chat("system", "任务结束", "entrypoint")
    show_memory_stats(store)
    kanban_store.close()


def show_memory_stats(store: MemoryStore):
    print(f"\n  记忆树统计:")
    trees = store.conn.execute("SELECT * FROM trees").fetchall()
    for t in trees:
        chunks = store.conn.execute(
            "SELECT COUNT(*) FROM chunks WHERE tree_id = ?", (t["id"],)
        ).fetchone()[0]
        summaries = store.conn.execute(
            "SELECT COUNT(*) FROM summary_nodes WHERE tree_id = ?", (t["id"],)
        ).fetchone()[0]
        buf = store.get_buffer(t["id"], 0)
        print(f"  {t['kind']:8s} | {t['id']:20s} | {chunks} chunks, {summaries} summaries, buffer: {len(buf.item_ids)} items")
    store.close()


# ── Phase 3 命令处理 ────────────────────────────────────────────


async def cmd_serve(args):
    """启动 FastAPI Gateway 服务器。"""
    from gateway.server import create_app, serve

    org = OrgEngine("config/org.yaml")
    org.create_all()
    kanban_store = KanbanStore()

    app = create_app(org, kanban_store)
    print(f"\n  Gateway 启动中: http://{args.host}:{args.port}")
    print(f"  API 文档: http://{args.host}:{args.port}/docs")
    await serve(app, host=args.host, port=args.port)


def cmd_kanban(args):
    """看板管理命令。"""
    store = KanbanStore()

    if args.kanban_cmd == "boards":
        boards = store.list_boards()
        if not boards:
            print("  (暂无看板)")
        else:
            for b in boards:
                lists_count = len(store.get_lists(b["id"]))
                print(f"  [{b['workshop_name']}] {b['name']} — {lists_count} 列表 — id={b['id'][:8]}")

    elif args.kanban_cmd == "board":
        board = store.get_board_by_name(args.name, args.name)
        if not board:
            print(f"  看板 '{args.name}' 不存在")
            return
        full = store.get_board_full(board["id"])
        print(f"\n  看板: {full['name']} ({full.get('workshop_name', '')})")
        print(f"  {full.get('description', '')}")
        for lst in full.get("lists", []):
            print(f"\n  [{lst['name']}]")
            for card in lst.get("cards", []):
                status_icon = {"todo": " ", "in_progress": ">", "done": "✓", "blocked": "!"}.get(card["task_status"], " ")
                print(f"    [{status_icon}] {card['title'][:80]}")
                if card.get("source_agent"):
                    print(f"         agent: {card['source_agent']}")

    elif args.kanban_cmd == "create":
        board_obj = store.create_board(args.name, workshop_name=args.workshop or args.name)
        # 创建默认列表
        for list_name in ["To Do", "In Progress", "Done", "Blocked"]:
            store.create_list(board_obj.id, list_name)
        print(f"  已创建看板: {args.name} (id={board_obj.id[:8]})")

    store.close()


async def cmd_mcp(args):
    """MCP 工具市场命令。"""
    registry = MCPRegistry(Path("config"))

    if args.mcp_cmd == "list":
        servers = registry.list_servers()
        if not servers:
            print("  (暂无已注册的 MCP 服务器)")
        else:
            for s in servers:
                print(f"  [{s.transport}] {s.name} — {s.description or '(无描述)'}")

    elif args.mcp_cmd == "search":
        results = registry.search_marketplace(args.query)
        if not results:
            print(f"  未找到匹配 '{args.query}' 的工具")
        else:
            print(f"\n  搜索结果 ({len(results)}):")
            for r in results:
                print(f"  [{r.category}] {r.name}")
                print(f"      {r.description[:120]}")
                print(f"      install: {r.install_command}")


def cmd_skill(args):
    """Skill.md 技能管理命令。"""
    repo = SkillRepo()

    if args.skill_cmd == "list":
        skills = repo.loader.list_skills(args.query)
        if not skills:
            print(f"  (未找到技能)  skills_dir={repo.loader.skills_dir}")
        else:
            print(f"\n  技能列表 ({len(skills)}):")
            for s in skills:
                installed = repo.is_installed(s.name, args.workshop)
                prefix = "[*]" if installed else "[ ]"
                triggers = ", ".join(s.triggers[:3])
                print(f"  {prefix} {s.name} v{s.version}")
                print(f"      {s.description[:100]}")
                if triggers:
                    print(f"      触发词: {triggers}")

    elif args.skill_cmd == "show":
        skill = repo.loader.load_skill(args.name)
        if not skill:
            print(f"  技能 '{args.name}' 未找到")
            return
        print(f"\n  {skill.name} v{skill.version}")
        print(f"  {skill.description}")
        if skill.triggers:
            print(f"  触发词: {', '.join(skill.triggers)}")
        if skill.tools:
            print(f"  工具: {', '.join(skill.tools)}")
        if skill.body:
            print(f"\n  ---")
            print(f"  {skill.body[:2000]}")

    elif args.skill_cmd == "install":
        # Check skill exists
        if not repo.loader.load_skill(args.name):
            print(f"  技能 '{args.name}' 未找到，请先创建 Skill.md")
            return
        repo.install(args.name, args.workshop)
        print(f"  已安装: {args.name} -> {args.workshop}")


# ── Phase 4 命令处理 ────────────────────────────────────────────


def cmd_workshop(args):
    """工作区管理命令。"""
    org = OrgEngine("config/org.yaml")
    org.create_all()  # 加载配置中已定义的工作区
    kanban_store = KanbanStore()
    from factory.workshop.manager import WorkshopManager
    mgr = WorkshopManager(org, kanban_store)

    if args.workshop_cmd == "create":
        agent_names = [a.strip() for a in (args.agents or "").split(",") if a.strip()]
        ws = mgr.create(name=args.name, workflow_name=args.workflow, agent_names=agent_names)
        # 持久化到 org.yaml
        _save_workshop_to_config(org, args.name, args.workflow, agent_names)
        print(f"  已创建工作区: {ws.name}")
        print(f"  workspace: {ws.workspace}")
        print(f"  agents: {list(ws.agents.keys())}")
        print(f"  workflow: {ws.workflow_name}")

    elif args.workshop_cmd == "list":
        workshops = mgr.list_all()
        if not workshops:
            print("  (暂无工作区)")
        else:
            print(f"\n  工作区列表 ({len(workshops)}):")
            for w in workshops:
                board_icon = "[B]" if w.has_kanban else "[ ]"
                print(f"  {board_icon} {w.name} — {w.agent_count} agents, workflow={w.workflow_name}")

    elif args.workshop_cmd == "show":
        status = mgr.status(args.name)
        if status is None:
            print(f"  工作区 '{args.name}' 不存在")
            return
        print(f"\n  工作区: {status['name']}")
        print(f"  workspace: {status['workspace']}")
        print(f"  agents: {status['agents']}")
        if "kanban_stats" in status:
            print(f"  看板统计: {status['kanban_stats']}")

    elif args.workshop_cmd == "run":
        # Handled via async cmd_workshop_run
        pass

    elif args.workshop_cmd == "delete":
        deleted = mgr.delete(args.name)
        if deleted:
            print(f"  已删除工作区: {args.name}")
        else:
            print(f"  工作区 '{args.name}' 不存在")

    kanban_store.close()


def cmd_workflow(args):
    """工作流管理命令。"""
    org = OrgEngine("config/org.yaml")
    org.create_all()

    if args.workflow_cmd == "list":
        workflows = org.workflow_store.list_all()
        print(f"\n  工作流模板 ({len(workflows)}):")
        for w in workflows:
            print(f"  {w['name']}: {w['description']} ({w.get('node_count', 0)} nodes)")

    elif args.workflow_cmd == "show":
        tmpl = org.workflow_store.load(args.name)
        if tmpl is None:
            print(f"  工作流 '{args.name}' 不存在")
            return
        print(f"\n  {tmpl.name} — {tmpl.description}")
        print(f"  节点 ({len(tmpl.nodes)}):")
        for n in tmpl.nodes:
            deps = f" (depends: {', '.join(n.depends_on)})" if n.depends_on else ""

    # ── Module export/import/remove ──────────────────────────────


def cmd_module(args):
    """Handle module subcommands."""
    org = OrgEngine("config/org.yaml")
    org.create_all()
    from factory.workshop.manager import WorkshopManager
    mgr = WorkshopManager(org, KanbanStore())

    if args.module_cmd == "export":
        pkg_dir = mgr.export_workspace(args.workspace, output_dir=args.output, version=args.version)
        if pkg_dir is None:
            print(f"  工作区 '{args.workspace}' 不存在")
            return
        print(f"\n  已导出: {pkg_dir}")
        manifest_path = Path(pkg_dir) / "nexus.yaml"
        if manifest_path.exists():
            manifest = yaml.safe_load(manifest_path.read_text("utf-8"))
            print(f"  名称: {manifest.get('name')}")
            print(f"  版本: {manifest.get('version')}")
            print(f"  Agents: {len(manifest.get('agents', []))}")
            print(f"  Workflows: {len(manifest.get('workflows', []))}")

    elif args.module_cmd == "import":
        if not Path(args.package).is_dir():
            print(f"  包不存在: {args.package}")
            return
        issues = validate_package(args.package)
        if issues:
            print("  包验证失败:")
            for issue in issues:
                print(f"    - {issue}")
            return
        result = mgr.import_package(args.package)
        if result is None:
            print(f"  导入失败（工作区可能已存在，使用 --force 覆盖）")
            return
        print(f"\n  已导入:")
        for k, v in result.items():
            print(f"    {k}: {v}")

    elif args.module_cmd == "remove":
        if not args.force:
            confirm = input(f"  确定要完全删除工作区 '{args.workspace}'？(y/N) ")
            if confirm.lower() != "y":
                print("  已取消")
                return
        result = mgr.remove_workspace(args.workspace)
        if result is None:
            print(f"  工作区 '{args.workspace}' 不存在")
            return
        print(f"\n  已卸载:")
        for k, v in result.items():
            print(f"    {k}: {v}")

    elif args.module_cmd == "list":
        workshops = mgr.list_all()
        if not workshops:
            print("  暂无已安装的模块")
            return
        print(f"\n  已安装模块 ({len(workshops)}):")
        for w in workshops:
            print(f"    [{w.workflow_name}] {w.name} — {w.agent_count} agents")


async def cmd_workshop_run(args):
    """异步执行工作流。"""
    org = OrgEngine("config/org.yaml")
    org.create_all()
    from factory.workshop.manager import WorkshopManager
    mgr = WorkshopManager(org, KanbanStore())
    ws = mgr.get(args.name)
    if ws is None:
        print(f"  工作区 '{args.name}' 不存在")
        return
    tmpl = org.workflow_store.load(args.workflow)
    if tmpl is None:
        print(f"  工作流 '{args.workflow}' 不存在")
        print(f"  可用: {[w['name'] for w in org.workflow_store.list_all()]}")
        return
    from factory.workflow.engine import WorkflowRunner
    runner = WorkflowRunner(ws)
    result = await runner.run(tmpl, args.task)
    print(f"\n  工作流结果: {result.status.value}")
    for nid, nr in result.node_results.items():
        icon = "✓" if nr.status.value == "passed" else "✗" if nr.status.value == "failed" else " "
        print(f"  [{icon}] {nr.node_id} ({nr.agent_name}): {nr.output[:120]}")


def _save_workshop_to_config(org, name: str, workflow_name: str, agent_names: list[str]) -> None:
    """将新工作区追加到 org.yaml。"""
    import yaml
    config_path = Path("config/org.yaml")
    with open(config_path) as f:
        data = yaml.safe_load(f) or {}
    existing = {d["name"] for d in data.get("departments", [])}
    if name in existing:
        return
    entry = {
        "name": name,
        "type": "custom",
        "workspace": f"workspaces/{name}",
        "agents": [{"name": aname, "template": aname, "model": "anthropic/claude-sonnet-4-6"} for aname in agent_names],
        "workflow": {"name": workflow_name},
    }
    data.setdefault("departments", []).append(entry)
    with open(config_path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


if __name__ == "__main__":
    asyncio.run(main())

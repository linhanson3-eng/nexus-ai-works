#!/usr/bin/env python3
"""Nexus AI Works — CLI entry point.

Parses arguments and delegates to command handlers in factory.cli.
"""

from __future__ import annotations

import argparse
import asyncio

from factory.cli import (
    cmd_kanban,
    cmd_library,
    cmd_mcp,
    cmd_module,
    cmd_serve,
    cmd_skill,
    cmd_workflow,
    cmd_workshop,
    cmd_workshop_run,
)
from factory.org import OrgEngine
from factory.memory import MemoryStore
from factory.kanban import KanbanStore, KanbanSync
from factory.runner import NexusAgentRunner


async def main():
    parser = argparse.ArgumentParser(description="Nexus AI Works — 模板化 AI 开发平台")
    sub = parser.add_subparsers(dest="command")

    parser.add_argument("--run", type=str, metavar="TASK", help="执行任务")
    parser.add_argument("--memory-stats", action="store_true", help="查看记忆树统计")
    parser.add_argument("--vault-path", type=str, default="~/.factory/vault", help="Obsidian vault 路径")
    parser.add_argument("--db-path", type=str, default="~/.factory/memory.db", help="SQLite 数据库路径")

    # serve
    serve_p = sub.add_parser("serve", help="启动 FastAPI gateway 服务器")
    serve_p.add_argument("--host", default="127.0.0.1")
    serve_p.add_argument("--port", type=int, default=8600)

    # kanban
    kanban_p = sub.add_parser("kanban", help="看板任务管理")
    kanban_sub = kanban_p.add_subparsers(dest="kanban_cmd")
    kanban_sub.add_parser("boards", help="列出所有看板")
    show_board = kanban_sub.add_parser("board", help="查看看板详情")
    show_board.add_argument("name", help="看板名称或 workshop 名称")
    create_board = kanban_sub.add_parser("create", help="创建新看板")
    create_board.add_argument("name", help="看板名称")
    create_board.add_argument("--workshop", default="", help="关联的工作区名称")

    # mcp
    mcp_p = sub.add_parser("mcp", help="MCP 工具市场")
    mcp_sub = mcp_p.add_subparsers(dest="mcp_cmd")
    mcp_sub.add_parser("list", help="列出已注册的 MCP 服务器")
    mcp_search = mcp_sub.add_parser("search", help="搜索 MCP 工具市场")
    mcp_search.add_argument("query")

    # skill
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

    # workshop
    workshop_p = sub.add_parser("workshop", help="工作区管理")
    workshop_sub = workshop_p.add_subparsers(dest="workshop_cmd")
    ws_create = workshop_sub.add_parser("create", help="创建工作区")
    ws_create.add_argument("name", help="工作区名称")
    ws_create.add_argument("--workflow", default="simple", help="工作流模板")
    ws_create.add_argument("--agents", default="", help="Agent 模板列表，逗号分隔")
    workshop_sub.add_parser("list", help="列出所有工作区")
    ws_run = workshop_sub.add_parser("run", help="执行工作流")
    ws_run.add_argument("name", help="工作区名称")
    ws_run.add_argument("workflow", help="工作流模板名")
    ws_run.add_argument("task", help="任务描述")
    ws_show = workshop_sub.add_parser("show", help="查看工作区详情")
    ws_show.add_argument("name")
    ws_delete = workshop_sub.add_parser("delete", help="删除工作区")
    ws_delete.add_argument("name")

    # workflow
    wf_p = sub.add_parser("workflow", help="工作流管理")
    wf_sub = wf_p.add_subparsers(dest="workflow_cmd")
    wf_sub.add_parser("list", help="列出所有工作流模板")
    wf_show = wf_sub.add_parser("show", help="查看工作流详情")
    wf_show.add_argument("name")

    # module
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
    module_sub.add_parser("list", help="列出已安装模块")

    # library
    lib_p = sub.add_parser("library", help="模板库管理")
    lib_sub = lib_p.add_subparsers(dest="library_cmd")
    lib_list = lib_sub.add_parser("list", help="列出模板")
    lib_list.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_list.add_argument("--search", default="", help="搜索关键词")
    lib_list.add_argument("--category", default="", help="按分类过滤")
    lib_save = lib_sub.add_parser("save", help="保存模板到库")
    lib_save.add_argument("type", choices=["workflow", "agent"], help="模板类型")
    lib_save.add_argument("name", help="模板名称")
    lib_save.add_argument("--workshop", "-w", default="", help="来源车间")
    lib_save.add_argument("--desc", default="", help="说明")
    lib_save.add_argument("--tags", default="", help="标签，逗号分隔")
    lib_save.add_argument("--category", default="其他", help="分类")
    lib_show = lib_sub.add_parser("show", help="查看模板详情")
    lib_show.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_show.add_argument("name", help="模板名称")
    lib_install = lib_sub.add_parser("install", help="安装模板")
    lib_install.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_install.add_argument("name", help="模板名称")
    lib_install.add_argument("--workshop", "-w", default="", help="目标车间")
    lib_delete = lib_sub.add_parser("delete", help="删除模板")
    lib_delete.add_argument("type", choices=["workflow", "agent", "role"], help="模板类型")
    lib_delete.add_argument("name", help="模板名称")

    args = parser.parse_args()

    print("=" * 60)
    print("  Nexus AI Works v1.0.0")
    print("=" * 60)

    if args.command == "serve":
        cmd_serve(args)
    elif args.command == "kanban":
        cmd_kanban(args)
    elif args.command == "mcp":
        cmd_mcp(args)
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
    elif args.command == "library":
        cmd_library(args)
    else:
        await _run_default(args)


async def _run_default(args):
    """Default mode: show skeleton status or execute a task."""
    store = MemoryStore(args.db_path)
    org = OrgEngine("config/org.yaml")

    print(f"\n  组织架构: {len(org.spec.departments)} 个工作区")
    print(f"  制品仓库: {org.warehouse.root}")
    print(f"  工作流模板: {len(org.workflow_store.list_all())} 个")


    org.create_all()

    if args.memory_stats:
        _show_memory_stats(store)
        return

    if args.run:
        await _run_task(org, store, args.run, args.vault_path)
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


async def _run_task(org: OrgEngine, store: MemoryStore, task: str, vault_path: str):
    """Execute a task using the first workshop's super Agent."""
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
    _show_memory_stats(store)
    kanban_store.close()


def _show_memory_stats(store: MemoryStore):
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
        print(
            f"  {t['kind']:8s} | {t['id']:20s} | "
            f"{chunks} chunks, {summaries} summaries, buffer: {len(buf.item_ids)} items"
        )
    store.close()


if __name__ == "__main__":
    asyncio.run(main())

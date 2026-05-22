"""CLI command handlers for the Nexus AI Works platform.

Each function is invoked from entrypoint.py based on the parsed subcommand.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import yaml

from factory.kanban import KanbanStore
from factory.mcp import MCPRegistry
from factory.org import OrgEngine
from factory.skills import SkillRepo
from factory.workflow.package import validate_package


async def cmd_serve(args):
    """Start the FastAPI Gateway server."""
    await _serve(args)


async def _serve(args):
    from gateway.server import create_app, serve

    org = OrgEngine("config/org.yaml")
    org.create_all()
    kanban_store = KanbanStore()

    app = create_app(org, kanban_store)
    print(f"\n  Gateway 启动中: http://{args.host}:{args.port}")
    print(f"  API 文档: http://{args.host}:{args.port}/docs")
    await serve(app, host=args.host, port=args.port)


def cmd_kanban(args):
    """Kanban management commands."""
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
                status_icon = {"todo": " ", "in_progress": ">", "done": "✓", "blocked": "!"}.get(
                    card["task_status"], " "
                )
                print(f"    [{status_icon}] {card['title'][:80]}")
                if card.get("source_agent"):
                    print(f"         agent: {card['source_agent']}")

    elif args.kanban_cmd == "create":
        board_obj = store.create_board(args.name, workshop_name=args.workshop or args.name)
        for list_name in ["To Do", "In Progress", "Done", "Blocked"]:
            store.create_list(board_obj.id, list_name)
        print(f"  已创建看板: {args.name} (id={board_obj.id[:8]})")

    store.close()


def cmd_mcp(args):
    """MCP marketplace commands (synchronous wrapper)."""
    asyncio.run(_mcp(args))


async def _mcp(args):
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
    """Skill.md management commands."""
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
        if not repo.loader.load_skill(args.name):
            print(f"  技能 '{args.name}' 未找到，请先创建 Skill.md")
            return
        repo.install(args.name, args.workshop)
        print(f"  已安装: {args.name} -> {args.workshop}")


def cmd_workshop(args):
    """Workshop management commands."""
    org = OrgEngine("config/org.yaml")
    org.create_all()
    kanban_store = KanbanStore()
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(org, kanban_store)

    if args.workshop_cmd == "create":
        agent_names = [a.strip() for a in (args.agents or "").split(",") if a.strip()]
        ws = mgr.create(name=args.name, workflow_name=args.workflow, agent_names=agent_names)
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

    elif args.workshop_cmd == "delete":
        deleted = mgr.delete(args.name)
        if deleted:
            print(f"  已删除工作区: {args.name}")
        else:
            print(f"  工作区 '{args.name}' 不存在")

    kanban_store.close()


async def cmd_workshop_run(args):
    """Execute a workflow in a workshop."""
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


def cmd_workflow(args):
    """Workflow template management commands."""
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
            print(f"    {n.id}: {n.task[:120]}{deps}")


def cmd_module(args):
    """Module export/import/remove commands."""
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
        result = mgr.import_package(args.package, force=getattr(args, "force", False))
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


def _save_workshop_to_config(org, name: str, workflow_name: str, agent_names: list[str]) -> None:
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
        "agents": [
            {"name": aname, "template": aname, "model": ""}
            for aname in agent_names
        ],
        "workflow": {"name": workflow_name},
    }
    data.setdefault("departments", []).append(entry)
    with open(config_path, "w") as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


# ── Library commands ──


def cmd_library(args):
    """Template library management commands."""
    if args.library_cmd == "list":
        _library_list(args)
    elif args.library_cmd == "save":
        _library_save(args)
    elif args.library_cmd == "show":
        _library_show(args)
    elif args.library_cmd == "install":
        _library_install(args)
    elif args.library_cmd == "delete":
        _library_delete(args)


def _library_list(args):
    from factory.library.models import EntryType
    from factory.library.store import LibraryStore

    et = EntryType(args.type)
    store = LibraryStore()
    search = getattr(args, "search", "") or ""
    category = getattr(args, "category", "") or ""
    entries = store.list_all(et, search=search, category=category)
    type_name = {"workflow": "生产方案", "agent": "智能体配置", "role": "岗位规格"}
    print(f"\n  我的模板 — {type_name.get(args.type, args.type)} ({len(entries)}):")
    if not entries:
        print("    (暂无)")
        return
    for e in entries:
        tags = f" [{', '.join(e.tags)}]" if e.tags else ""
        print(f"    [{e.category}] {e.name} v{e.version}{tags}")
        if e.description:
            print(f"      {e.description[:100]}")
        if e.source_workshop:
            print(f"      来源: {e.source_workshop}")


def _library_save(args):
    from factory.library.store import (
        LibraryStore,
        save_agent_to_library,
        save_workflow_to_library,
    )
    from factory.org import OrgEngine

    store = LibraryStore()
    org = OrgEngine("config/org.yaml")
    org.create_all()
    desc = getattr(args, "desc", "") or ""
    tags = [t.strip() for t in (getattr(args, "tags", "") or "").split(",") if t.strip()]
    category = getattr(args, "category", "其他") or "其他"
    workshop = getattr(args, "workshop", "") or ""

    try:
        if args.type == "workflow":
            entry = save_workflow_to_library(
                store, args.name, org,
                description=desc, category=category, tags=tags,
            )
        elif args.type == "agent":
            entry = save_agent_to_library(
                store, args.name, workshop, org,
                description=desc, category=category, tags=tags,
            )
        else:
            print(f"  不支持的类型: {args.type}")
            return
        print(f"  已入库: [{entry.category}] {entry.name}")
    except ValueError as e:
        print(f"  入库失败: {e}")


def _library_show(args):
    from factory.library.models import EntryType
    from factory.library.store import LibraryStore

    store = LibraryStore()
    entry = store.get(EntryType(args.type), args.name)
    if entry is None:
        print(f"  模板 '{args.name}' 不存在")
        return
    print(f"\n  {entry.name} v{entry.version}")
    print(f"  类型: {entry.entry_type.value}")
    print(f"  分类: {entry.category}")
    if entry.tags:
        print(f"  标签: {', '.join(entry.tags)}")
    if entry.description:
        print(f"  说明: {entry.description}")
    if entry.source_workshop:
        print(f"  来源: {entry.source_workshop}")
    print(f"  入库: {entry.created_at}")
    if entry.body:
        print(f"\n  --- 内容 ---")
        print(f"  {entry.body[:2000]}")


def _library_install(args):
    from factory.library.models import EntryType
    from factory.library.store import LibraryStore
    from factory.org import OrgEngine

    store = LibraryStore()
    org = OrgEngine("config/org.yaml")
    org.create_all()
    et = EntryType(args.type)
    workshop = getattr(args, "workshop", "") or ""

    if et == EntryType.WORKFLOW:
        ok = store.install_workflow(args.name, org.workflow_store)
    elif et == EntryType.AGENT:
        if not workshop:
            print("  Agent 安装需要指定 --workshop")
            return
        ok = store.install_agent(args.name, workshop, org)
    elif et == EntryType.ROLE:
        ok = store.install_role(args.name)
    else:
        print(f"  不支持的类型: {args.type}")
        return

    if ok:
        print(f"  已安装: {args.name} ({args.type})")
    else:
        print(f"  安装失败: 模板 '{args.name}' 不存在")


def _library_delete(args):
    from factory.library.models import EntryType
    from factory.library.store import LibraryStore

    store = LibraryStore()
    ok = store.delete(EntryType(args.type), args.name)
    if ok:
        print(f"  已删除: {args.name}")
    else:
        print(f"  模板 '{args.name}' 不存在")

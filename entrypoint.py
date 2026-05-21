#!/usr/bin/env python3
"""AI 工厂启动入口。"""

import argparse
import asyncio
import sys
from pathlib import Path

from factory.org import OrgEngine
from factory.workflow import WorkflowLibrary
from factory.memory import MemoryStore, SourceTree, VaultWriter
from factory.memory.tree import BucketSeal, dummy_summariser
from factory.runner import FactoryAgentRunner


async def main():
    parser = argparse.ArgumentParser(description="AI 工厂模板化开发平台")
    parser.add_argument("--run", type=str, metavar="TASK", help="执行任务")
    parser.add_argument("--memory-stats", action="store_true", help="查看记忆树统计")
    parser.add_argument("--vault-path", type=str, default="~/.factory/vault", help="Obsidian vault 路径")
    parser.add_argument("--db-path", type=str, default="~/.factory/memory.db", help="SQLite 数据库路径")
    args = parser.parse_args()

    print("=" * 60)
    print("  AI 工厂 v0.3.0")
    print("=" * 60)

    # 初始化存储
    store = MemoryStore(args.db_path)

    # 加载组织架构
    org = OrgEngine("config/org.yaml")
    print(f"\n📋 组织架构: {len(org.spec.departments)} 个车间")
    print(f"📦 制品仓库: {org.warehouse.root}")

    # 工作流模板库
    workflows = WorkflowLibrary()
    print(f"\n🔧 工作流模板: {len(workflows.list_all())} 个")

    # Agent 模板库
    print(f"🤖 Agent 模板: {len(org.templates.list_all())} 个")

    # 创建车间
    org.create_all()

    if args.memory_stats:
        show_memory_stats(store)
        return

    if args.run:
        await run_task(org, store, args.run, args.vault_path)
        return

    # 默认：展示骨架状态
    print(f"\n🏭 车间状态:")
    print(org.status())
    print(f"\n📦 制品仓库索引:")
    for dept, products in org.warehouse.index().items():
        for p in products:
            print(f"  - {dept}/{p}")
    print("\n✅ 工厂骨架就绪")
    print("   python3 entrypoint.py --run '任务描述'   → 执行任务")
    print("   python3 entrypoint.py --memory-stats     → 记忆统计")


async def run_task(org: OrgEngine, store: MemoryStore, task: str, vault_path: str):
    """执行任务：选择第一个车间的 super Agent。"""
    departments = org.spec.departments
    if not departments:
        print("❌ 没有配置车间，请检查 config/org.yaml")
        return

    dept = departments[0]
    agent_spec = next((a for a in dept.agents if a.type == "super"), dept.agents[0])
    workshop = next((w for w in org.workshops if w.name == dept.name), None)

    print(f"\n🚀 执行任务: {task}")
    print(f"🏭 车间: {dept.name}")
    print(f"🤖 Agent: {agent_spec.name} ({agent_spec.type})")
    print(f"🧠 模型: {agent_spec.model}")
    print()

    runner = FactoryAgentRunner(agent_spec, workshop, store, vault_path=vault_path)

    # 记录任务开始
    runner.record_chat("system", f"任务开始: {task}", "entrypoint")

    try:
        result = await runner.run(task)
        print("─" * 40)
        print(f"📤 结果:\n{result.content[:2000]}")
        print(f"\n🔧 使用工具: {', '.join(result.tools_used) or '无'}")
        if result.error:
            print(f"⚠️ 错误: {result.error}")
    except Exception as e:
        print(f"❌ 执行失败: {e}")

    # 记录任务结束
    runner.record_chat("system", f"任务结束", "entrypoint")

    # 显示记忆统计
    show_memory_stats(store)


def show_memory_stats(store: MemoryStore):
    print(f"\n🧠 记忆树统计:")
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


if __name__ == "__main__":
    asyncio.run(main())

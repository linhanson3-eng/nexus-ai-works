#!/usr/bin/env python3
"""AI 工厂启动入口。单车间测试。"""

import asyncio

from factory.org import OrgEngine
from factory.workflow import WorkflowLibrary


async def main():
    print("=" * 50)
    print("  AI 工厂 v0.1")
    print("=" * 50)

    # 1. 加载组织架构
    org = OrgEngine("config/org.yaml")
    print(f"\n📋 加载组织架构: {len(org.spec.departments)} 个车间")
    print(f"📦 制品仓库: {org.warehouse.root}")

    # 2. 工作流模板库
    workflows = WorkflowLibrary()
    print(f"\n🔧 工作流模板库:")
    for wf in workflows.list_all():
        src = "内置" if wf["source"] == "builtin" else "自定义"
        print(f"  - {wf['name']} ({src}): {wf['description']}")

    # 3. Agent 模板库
    print(f"\n🤖 Agent 模板库:")
    for t in org.templates.list_all():
        src = "内置" if t["source"] == "builtin" else "自定义"
        print(f"  - {t['name']} ({t['type']}, {src}): {t['description']}")

    # 4. 创建车间
    org.create_all()
    print(f"\n🏭 车间状态:")
    print(org.status())

    # 5. 列出制品仓库
    print(f"\n📦 制品仓库索引:")
    for dept, products in org.warehouse.index().items():
        for p in products:
            print(f"  - {dept}/{p}")

    print("\n✅ 工厂骨架搭建完成（单车间验证）")
    print("\n下一步：接入 nanobot AgentRunner 执行实际任务")


if __name__ == "__main__":
    asyncio.run(main())

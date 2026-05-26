"""完整闭环测试: Coder → Reviewer → Coder fix → Reviewer confirm。

4 个 step，每个 step fork 前一个，形成闭环审查链。
"""
import asyncio
import json
import os
import httpx

MCP = "http://localhost:8600/mcp"
TOKEN_URL = "http://localhost:8600/mcp/token"
WORKSHOP = "demo"


async def new_token() -> str:
    async with httpx.AsyncClient() as c:
        return (await c.post(TOKEN_URL, json={"workshop_name": WORKSHOP})).json()["token"]


async def exec_task(task: str, mode: str, parent_id: str = "") -> dict:
    """通过 MCP 调 Agent，返回解析结果."""
    tok = await new_token()
    async with httpx.AsyncClient(timeout=180) as c:
        resp = await c.post(
            MCP,
            headers={"Authorization": f"Bearer {tok}"},
            json={"jsonrpc": "2.0", "method": "tools/call", "params": {
                "name": "nexus_execute_task",
                "arguments": {
                    "task": task, "workshop": WORKSHOP,
                    "mode": mode, "parent_session_id": parent_id,
                },
            }, "id": 1},
        )
    r = resp.json()
    if "error" in r:
        return {"error": r["error"]["message"][:300]}
    return json.loads(r["result"]["content"][0]["text"])


def show(name: str, r: dict, prev_sid: str = ""):
    sid = r.get("session_id", "")
    is_new = sid != prev_sid if prev_sid else True
    flag = "NEW" if is_new else "SAME"
    print(f"[{name}] sid={sid[:16]}... {flag} turns={r.get('turns',0)}")
    if r.get("error"):
        print(f"  ERROR: {r['error'][:200]}")
        return sid
    out = r.get("output", "")
    if len(out) > 350:
        out = out[:350] + "..."
    for line in out.split("\n")[:15]:
        print(f"  {line}")
    return sid


async def main():
    print("=" * 60)
    print("闭环审查: Coder → Reviewer → Coder fix → Confirm")
    print("=" * 60)

    # Step 1: Coder
    print()
    r1 = await exec_task(
        "在 workspace 写 sort.py，实现 bubble_sort(arr) 函数。只写代码。",
        mode="spawn",
    )
    s1 = show("1.Coder   ", r1)
    if r1.get("error"):
        return

    # Step 2: Reviewer fork
    print()
    r2 = await exec_task(
        "审查 sort.py。检查: 1) 是否有优化版(提前终止) 2) 边界条件 3) 类型提示。如有问题请列出。",
        mode="fork",
        parent_id=s1,
    )
    s2 = show("2.Reviewer", r2, s1)

    # Step 3: Coder 根据审查意见修改
    print()
    review_text = r2.get("output", "")
    if "问题" in review_text or "缺少" in review_text or "建议" in review_text or "没有" in review_text:
        r3 = await exec_task(
            "根据审查意见修改 sort.py。逐条回应并修改代码。输出修改后的完整代码。",
            mode="fork",
            parent_id=s2,
        )
    else:
        r3 = await exec_task(
            "给 sort.py 添加 docstring 和类型提示。输出修改后的代码。",
            mode="fork",
            parent_id=s2,
        )
    s3 = show("3.CoderFix", r3, s2)

    # Step 4: Reviewer 确认
    print()
    r4 = await exec_task(
        "逐条确认修改结果。每个问题标注 ✓(已解决) 或 ✗(未解决)。全部 ✓ 才算通过。",
        mode="fork",
        parent_id=s3,
    )
    s4 = show("4.Confirm ", r4, s3)

    # 总结
    print()
    print("=" * 60)
    print(f"Session chain: {s1[:12]} → {s2[:12]} → {s3[:12]} → {s4[:12]}")
    all_new = s1 != s2 and s2 != s3 and s3 != s4
    print(f"All unique sessions: {all_new}")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

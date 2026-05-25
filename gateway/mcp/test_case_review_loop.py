"""测试 MCP fork/spawn 闭环审查流程。

模拟: Coder 写代码 → Reviewer fork 审查 → Reviewer 提出修改意见
      → Coder fork 回去修改 → Reviewer 再审查确认

默认 demo workspace，不需要额外配置。
"""
import asyncio
import json
import httpx


MCP_URL = "http://localhost:8600/mcp"
TOKEN_URL = "http://localhost:8600/mcp/token"
WORKSHOP = "demo"


async def mcp_call(token: str, method: str, params: dict) -> dict:
    """发送 JSON-RPC 2.0 请求到 MCP endpoint."""
    async with httpx.AsyncClient(timeout=120) as client:
        resp = await client.post(
            MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        )
        return resp.json()


async def get_token() -> str:
    """获取新的 MCP token（max_uses=1，每次调工具都要新 token）"""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            json={"workshop_name": WORKSHOP, "user_id": "test-case"},
        )
        return resp.json()["token"]


async def execute_task(token: str, task: str, mode: str = "spawn",
                       parent_id: str = "") -> dict:
    """执行一个 Agent 任务，返回解析后的结果."""
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_execute_task",
        "arguments": {
            "task": task,
            "workshop": WORKSHOP,
            "mode": mode,
            "parent_session_id": parent_id,
        },
    })
    if "error" in resp:
        return {"error": resp["error"]}
    text = resp["result"]["content"][0]["text"]
    return json.loads(text)


async def list_sessions(token: str) -> list[dict]:
    """列出所有 session."""
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_list_sessions",
        "arguments": {"workshop": WORKSHOP},
    })
    return json.loads(resp["result"]["content"][0]["text"])


async def stop_session(token: str, session_id: str, reason: str) -> dict:
    """停止一个 session."""
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_stop_session",
        "arguments": {"session_id": session_id, "reason": reason},
    })
    return json.loads(resp["result"]["content"][0]["text"])


async def main():
    print("=" * 60)
    print("MCP 闭环审查测试")
    print("=" * 60)

    # Step 1: Coder 写代码
    print("\n[1] Coder 开始实现功能...")
    t1 = await get_token()
    r1 = await execute_task(t1,
        "写一个 Python 函数 fibonacci(n)，返回第 n 个斐波那契数。"
        "只输出代码，不要解释。",
        mode="spawn",
    )
    coder_sid = r1.get("session_id", "")
    print(f"    session: {coder_sid[:20]}...")
    print(f"    output:  {r1.get('output', '')[:200]}")
    print(f"    turns:   {r1.get('turns', 0)}")

    # Step 2: Reviewer 审查（fork from coder）
    print("\n[2] Reviewer 审查代码...")
    t2 = await get_token()
    r2 = await execute_task(t2,
        f"审查 session {coder_sid[:12]} 中的代码。"
        "检查: 1) 边界条件 2) 性能 3) 可读性。"
        "逐条列出问题。如果没有问题，说「通过」。",
        mode="fork",
        parent_id=coder_sid,
    )
    review_sid = r2.get("session_id", "")
    review_output = r2.get("output", "")
    print(f"    session: {review_sid[:20]}...")
    print(f"    review:  {review_output[:300]}")

    # Step 3: Coder 修改（fork from reviewer）
    print("\n[3] Coder 根据审查意见修改...")
    t3 = await get_token()
    r3 = await execute_task(t3,
        f"根据 session {review_sid[:12]} 中的审查意见修改代码。"
        "逐条回应每个问题。输出修改后的完整代码。",
        mode="fork",
        parent_id=review_sid,
    )
    fix_sid = r3.get("session_id", "")
    print(f"    session: {fix_sid[:20]}...")
    print(f"    output:  {r3.get('output', '')[:200]}")

    # Step 4: Reviewer 确认（fork from fix）
    print("\n[4] Reviewer 逐条确认修改...")
    t4 = await get_token()
    r4 = await execute_task(t4,
        f"确认 session {fix_sid[:12]} 中的修改是否解决了所有问题。"
        "逐条标注: ✓ 已解决 / ✗ 未解决。全部 ✓ 才算通过。",
        mode="fork",
        parent_id=fix_sid,
    )
    confirm_sid = r4.get("session_id", "")
    print(f"    session: {confirm_sid[:20]}...")
    print(f"    confirm: {r4.get('output', '')[:300]}")

    # Step 5: 查看 session tree
    print("\n[5] Session Tree 结构:")
    t5 = await get_token()
    sessions = await list_sessions(t5)
    for s in sessions:
        parent = s.get("parent_id", "")[:12] or "root"
        sid = s["session_id"][:12]
        task_preview = s["task"][:50]
        print(f"    [{s['type']:6}] {sid}... ← {parent}  {task_preview}")

    print("\n" + "=" * 60)
    print("测试完成 — 闭环审查链路跑通")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())

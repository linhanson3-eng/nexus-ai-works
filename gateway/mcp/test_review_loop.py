"""测试 nexus_review_loop — 审查→修复→验证闭环。

1. 写一个有 bug 的代码文件
2. 调用 nexus_review_loop 做审查→修复→验证
3. 验证 before/after 对比
"""
import asyncio
import json
import sys

import httpx

MCP_URL = "http://localhost:8600/mcp"
TOKEN_URL = "http://localhost:8600/mcp/token"
WORKSHOP = "demo"


async def mcp_call(token: str, method: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=600) as client:
        resp = await client.post(
            MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        )
        return resp.json()


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL, json={"workshop_name": WORKSHOP, "user_id": "review-loop-test"},
        )
        return resp.json()["token"]


async def execute_task(token: str, task: str, mode: str = "spawn",
                       model: str = "") -> dict:
    args = {"task": task, "workshop": WORKSHOP, "mode": mode}
    if model:
        args["model"] = model
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_execute_task",
        "arguments": args,
    })
    if "error" in resp:
        return {"error": resp["error"]}
    return json.loads(resp["result"]["content"][0]["text"])


async def review_loop(token: str, target: str, models: list[str]) -> dict:
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_review_loop",
        "arguments": {
            "workshop": WORKSHOP,
            "target": target,
            "models": models,
        },
    })
    if "error" in resp:
        return {"error": resp["error"]}
    return json.loads(resp["result"]["content"][0]["text"])


async def main():
    print("=" * 65)
    print("nexus_review_loop E2E 测试")
    print("=" * 65)

    models = [
        "deepseek/deepseek-v4-pro",
        "siliconflow/Pro/moonshotai/Kimi-K2.6",
    ]

    # Step 1: Write buggy code
    print("[1] 写入测试代码...")
    t1 = await get_token()
    r1 = await execute_task(t1, (
        "用 nexus_write_workspace 创建 src/review_loop_test.py，写入:\n\n"
        "def calculate_discount(price, percent):\n"
        "    if price < 0 or percent < 0:\n"
        "        raise ValueError('negative input')\n"
        "    return price - price * percent / 100\n\n"
        "def apply_coupon(order_total, coupon_code):\n"
        "    discounts = {'SAVE10': 10, 'SAVE20': 20}\n"
        "    if coupon_code not in discounts:\n"
        "        return order_total\n"
        "    return order_total - order_total * discounts[coupon_code] / 100\n\n"
        "def split_bill(amount, num_people):\n"
        "    return amount / num_people\n\n"
        "直接写入，不要修改。"
    ), mode="spawn", model=models[0])
    if r1.get("error"):
        print(f"    ERROR: {r1['error']}")
        return 1
    print(f"    done, session: {r1.get('session_id', '')[:20]}...")

    # Step 2: Run review loop
    print(f"\n[2] 运行 nexus_review_loop (审查→修复→验证)...")
    print(f"    Reviewers: {models}")
    t2 = await get_token()
    result = await review_loop(t2, "src/review_loop_test.py", models)

    if "error" in result:
        print(f"    ERROR: {result['error']}")
        return 1

    # Validate structure
    phases = result.get("phases", {})
    comparison = result.get("comparison", {})

    print(f"\n[3] 结果:")
    print(f"    Verdict: {result.get('verdict', '?')}")
    print(f"    Fix applied: {result.get('fix_applied', False)}")
    print(f"    Comparison:")
    print(f"      Before → consensus={comparison.get('before', {}).get('consensus', 0)}, "
          f"unique={comparison.get('before', {}).get('unique', 0)}")
    print(f"      After  → consensus={comparison.get('after', {}).get('consensus', 0)}, "
          f"unique={comparison.get('after', {}).get('unique', 0)}")
    print(f"      Resolved: {comparison.get('resolved_consensus', 0)}")
    print(f"      Fix effective: {comparison.get('fix_effective', False)}")

    # Phase details
    before_consensus = phases.get("before", {}).get("consensus", [])
    after_consensus = phases.get("after", {}).get("consensus", [])

    print(f"\n[4] Before — 发现 {len(before_consensus)} 个共识问题:")
    for item in before_consensus[:5]:
        print(f"    [{item.get('severity', '?')}] {item.get('description', '')[:100]}")

    print(f"\n[5] After — 剩余 {len(after_consensus)} 个共识问题:")
    for item in after_consensus[:5]:
        print(f"    [{item.get('severity', '?')}] {item.get('description', '')[:100]}")

    # Check fix output
    fix_out = result.get("fix_output", "")
    print(f"\n[6] Fix output ({len(fix_out)} chars):")
    print(f"    {fix_out[:400]}")

    # Validation
    print("\n" + "=" * 65)
    total_before = len(before_consensus) + sum(len(v) for v in phases.get("before", {}).get("unique", {}).values())
    total_after = len(after_consensus) + sum(len(v) for v in phases.get("after", {}).get("unique", {}).values())
    fix_applied = result.get("fix_applied", False)

    checks = [
        ("Phases present", "before" in phases and "after" in phases),
        ("Comparison present", bool(comparison)),
        ("Total findings > 0 (before)", total_before > 0),
        ("Fix output produced", bool(result.get("fix_output", ""))),
        ("Loop completed", result.get("verdict") is not None),
    ]
    all_pass = True
    for name, ok in checks:
        status = "PASS" if ok else "FAIL"
        if not ok:
            all_pass = False
        print(f"[{status}] {name}")

    if all_pass:
        print("PASS: 闭环测试通过")
    else:
        print("FAIL: 部分检查未通过")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

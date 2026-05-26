"""测试 nexus_cross_review — 并行多模型交叉审查。

1. 先写一个有问题的代码文件
2. 调用 nexus_cross_review 让 2 个不同模型并行审查
3. 验证输出结构: verdict, consensus, unique, conflicts, findings_by_model
"""
import asyncio
import json
import httpx
import sys


MCP_URL = "http://localhost:8600/mcp"
TOKEN_URL = "http://localhost:8600/mcp/token"
WORKSHOP = "demo"

MODEL_A = "deepseek/deepseek-v4-pro"
MODEL_B = "siliconflow/Pro/moonshotai/Kimi-K2.6"


async def mcp_call(token: str, method: str, params: dict) -> dict:
    async with httpx.AsyncClient(timeout=300) as client:
        resp = await client.post(
            MCP_URL,
            headers={"Authorization": f"Bearer {token}"},
            json={"jsonrpc": "2.0", "method": method, "params": params, "id": 1},
        )
        return resp.json()


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            TOKEN_URL,
            json={"workshop_name": WORKSHOP, "user_id": "cross-review-test"},
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


async def cross_review(token: str, target: str, models: list[str],
                       focus: str = "") -> dict:
    resp = await mcp_call(token, "tools/call", {
        "name": "nexus_cross_review",
        "arguments": {
            "workshop": WORKSHOP,
            "target": target,
            "models": models,
            "focus": focus,
        },
    })
    if "error" in resp:
        return {"error": resp["error"]}
    return json.loads(resp["result"]["content"][0]["text"])


async def main():
    print("=" * 65)
    print("nexus_cross_review E2E 测试")
    print("=" * 65)
    print(f"Model A: {MODEL_A}")
    print(f"Model B: {MODEL_B}")
    print()

    # ── Step 1: Coder 写代码 ──
    print("[1] 写入测试代码...")
    t1 = await get_token()
    r1 = await execute_task(t1, (
        "用 nexus_write_workspace 创建文件 src/cross_test.py，写入以下代码:\n\n"
        "class OrderProcessor:\n"
        "    def __init__(self):\n"
        "        self.orders = []\n"
        "    def add_order(self, items, total):\n"
        "        self.orders.append({'items': items, 'total': total})\n"
        "    def get_total_revenue(self):\n"
        "        return sum(o.total for o in self.orders)\n"
        "    def apply_discount(self, order_id, percent):\n"
        "        order = self.orders[order_id]\n"
        "        order['total'] = order['total'] * (1 - percent/100)\n"
        "\n"
        "直接写入这段代码，不要修改。"
    ), mode="spawn", model=MODEL_A)
    if r1.get("error"):
        print(f"    ERROR: {r1['error']}")
        return 1
    print(f"    Coder session: {r1.get('session_id', '')[:20]}...")
    print()

    # ── Step 2: 交叉审查 ──
    print("[2] 并行交叉审查 (2 models)...")
    t2 = await get_token()
    result = await cross_review(t2, "src/cross_test.py",
        models=[MODEL_A, MODEL_B],
        focus="逻辑正确性和异常处理",
    )
    if "error" in result:
        print(f"    ERROR: {result['error']}")
        return 1

    print(f"    Verdict: {result.get('verdict', 'N/A')}")
    print()

    # ── Validate output structure ──
    print("[3] 验证输出结构:")
    required_fields = ["verdict", "target", "models", "findings_by_model",
                       "consensus", "unique", "conflicts"]
    all_ok = True
    for field in required_fields:
        exists = field in result
        status = "PASS" if exists else "FAIL"
        if not exists:
            all_ok = False
        print(f"    [{status}] {field}")

    print()
    print("[4] 各模型发现的问题:")
    for model, findings in result.get("findings_by_model", {}).items():
        print(f"    --- {model} ({len(findings)} 个问题) ---")
        for f in findings:
            sev = f.get('severity', '?')
            desc = f.get('description', '')[:100]
            print(f"      [{sev}] {desc}")

    print()
    print("[5] 共识 (2+ 模型都发现):")
    consensus = result.get("consensus", [])
    for g in consensus:
        print(f"    [{g.get('severity', '?')}] {g.get('description', '')[:120]}")
        print(f"      发现者: {', '.join(g.get('found_by', []))}")

    print()
    print("[6] 独有发现 (仅 1 个模型):")
    unique = result.get("unique", {})
    for model, findings in unique.items():
        for g in findings:
            print(f"    [{g.get('severity', '?')}] ({model}) {g.get('description', '')[:120]}")

    print()
    print("[7] 结论冲突:")
    conflicts = result.get("conflicts", [])
    if conflicts:
        for c in conflicts:
            print(f"    {json.dumps(c, ensure_ascii=False, indent=4)[:300]}")
    else:
        print("    (无显著冲突)")

    print()
    print("=" * 65)
    if all_ok:
        print("PASS: 所有结构字段存在")
    else:
        print("FAIL: 缺少字段")
        return 1

    if len(result.get("findings_by_model", {})) == 2:
        print("PASS: 2 个模型都返回了结果")
    else:
        print("FAIL: 模型返回数量不对")
        return 1

    # Key test: did the different model find things the same model missed?
    findings_by = result.get("findings_by_model", {})
    model_a_findings = len(findings_by.get(MODEL_A, []))
    model_b_findings = len(findings_by.get(MODEL_B, []))
    print(f"PASS: {MODEL_A.split('/')[-1]}={model_a_findings} findings, "
          f"{MODEL_B.split('/')[-1]}={model_b_findings} findings")

    unique_findings = result.get("unique", {})
    unique_count = sum(len(v) for v in unique_findings.values())
    consensus_count = len(result.get("consensus", []))
    print(f"PASS: consensus={consensus_count}, unique={unique_count}")
    print("=" * 65)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))

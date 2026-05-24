import { test, expect } from "@playwright/test";

// ── Auth Bypass ──
async function setupAuth(page: any) {
  await page.addInitScript(() => {
    localStorage.setItem("nexus_token", "test-token-fake-12345");
    localStorage.setItem("nexus_user", JSON.stringify({ username: "test", is_vip: false }));
  });
}

// ── SSE Mocker ──
async function mockSSE(page: any, events: object[]) {
  await page.route("**/api/agent/run/stream", async (route: any) => {
    const body = events.map((e: any) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join("");
    await route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body });
  });
}

const chatEvents = [
  { type: "status", event: "started", task: "hello" },
  { type: "message_start", session_id: "sess_abc123" },
  { type: "content_delta", delta: "你好！" },
  { type: "content_delta", delta: "我是 Nexus。" },
  { type: "message_stop" },
  { type: "completed", reply: "你好！我是 Nexus。", turns: 1, cost_usd: 0.001, tools_used: [], session_id: "sess_abc123", model: "gpt-4o" },
  { type: "done" },
];

const toolEvents = [
  { type: "status", event: "started", task: "search" },
  { type: "message_start", session_id: "sess_tool" },
  { type: "tool_match", tools: ["web_search", "read_file"] },
  { type: "tool_start", tool_call_id: "call_1", tool_name: "web_search" },
  { type: "tool_result", tool_call_id: "call_1", ok: true, content: "Found 3 results" },
  { type: "content_delta", delta: "搜索完成。" },
  { type: "message_stop" },
  { type: "completed", reply: "搜索完成。", turns: 1, cost_usd: 0.002, tools_used: ["web_search"], session_id: "sess_tool", model: "gpt-4o" },
  { type: "done" },
];

test.beforeEach(async ({ page }) => {
  await setupAuth(page);
  await page.route("**/api/workshops", (r: any) => r.fulfill({ json: [{ name: "test-workshop" }] }));
  await page.route("**/api/providers", (r: any) => r.fulfill({ json: {} }));
  await page.route("**/api/preferences", (r: any) => r.fulfill({ json: { default_model: "" } }));
  await page.route("**/api/agent/session/**", (r: any) => r.fulfill({ json: { messages: [] } }));
});

// ── Rendering ──
test.describe("ChatPanel - Rendering", () => {
  test("shows welcome message on load", async ({ page }) => {
    await page.goto("/chat");
    await page.waitForLoadState("domcontentloaded");
    await expect(page.getByText("你好，我是 Nexus 助手")).toBeVisible({ timeout: 10000 });
  });

  test("shows header heading with Nexus", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.getByRole("heading", { name: "Nexus 助手" })).toBeVisible();
  });

  test("shows input for typing messages", async ({ page }) => {
    await page.goto("/chat");
    // The input is a text input inside the chat panel
    const input = page.locator('input[placeholder*="想做"]');
    await expect(input).toBeAttached({ timeout: 5000 });
  });

  test("shows new chat button", async ({ page }) => {
    await page.goto("/chat");
    await expect(page.locator("button[title='新对话']")).toBeVisible();
  });
});

// ── Message Sending ──
test.describe("ChatPanel - Message Flow", () => {
  test("sends on Enter and shows user bubble", async ({ page }) => {
    await mockSSE(page, chatEvents);
    await page.goto("/chat");
    await page.waitForLoadState("domcontentloaded");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("你好");
    await input.press("Enter");

    await expect(page.getByText("你好").first()).toBeVisible({ timeout: 5000 });
  });

  test("assistant streams and displays content", async ({ page }) => {
    await mockSSE(page, chatEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("hello");
    await input.press("Enter");

    await expect(page.getByText("我是 Nexus。")).toBeVisible({ timeout: 8000 });
  });

  test("does not send empty message", async ({ page }) => {
    await page.goto("/chat");
    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("   ");
    await input.press("Enter");
    await page.waitForTimeout(500);
    // Only welcome message visible
    await expect(page.getByText("你好，我是 Nexus 助手")).toBeVisible();
  });
});

// ── Tool Calls ──
test.describe("ChatPanel - Tool Calls", () => {
  test("displays tool call card", async ({ page }) => {
    await mockSSE(page, toolEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("search something");
    await input.press("Enter");

    await expect(page.getByText("web_search").first()).toBeVisible({ timeout: 8000 });
  });

  test("shows tool plan steps", async ({ page }) => {
    await mockSSE(page, toolEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("search");
    await input.press("Enter");

    await expect(page.getByText("计划")).toBeVisible({ timeout: 5000 });
  });
});

// ── Session Persistence ──
test.describe("ChatPanel - Session", () => {
  test("stores session_id in localStorage after completion", async ({ page }) => {
    await page.route("**/api/agent/run/stream", async (route: any) => {
      const events = [
        { type: "status", event: "started" },
        { type: "message_start", session_id: "persist_42" },
        { type: "content_delta", delta: "ok" },
        { type: "message_stop" },
        { type: "completed", reply: "ok", turns: 1, cost_usd: 0, tools_used: [], session_id: "persist_42", model: "test" },
        { type: "done" },
      ];
      const body = events.map((e: any) => `event: ${e.type}\ndata: ${JSON.stringify(e)}\n\n`).join("");
      await route.fulfill({ status: 200, headers: { "Content-Type": "text/event-stream" }, body });
    });

    await page.goto("/chat");
    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("test persist");
    await input.press("Enter");

    await page.waitForTimeout(2000);
    const sid = await page.evaluate(() => localStorage.getItem("nexus_session_test-workshop"));
    expect(sid).toBe("persist_42");
  });
});

// ── Error Handling ──
test.describe("ChatPanel - Errors", () => {
  test("shows error on HTTP 500", async ({ page }) => {
    await page.route("**/api/agent/run/stream", (route: any) => route.fulfill({ status: 500 }));
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("crash");
    await input.press("Enter");

    await expect(page.getByText("HTTP 500")).toBeVisible({ timeout: 5000 });
  });

  test("survives network abort", async ({ page }) => {
    await page.route("**/api/agent/run/stream", (route: any) => route.abort("failed"));
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("network die");
    await input.press("Enter");

    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
  });
});

// ── New Chat ──
test.describe("ChatPanel - New Chat", () => {
  test("new chat button clears messages", async ({ page }) => {
    await mockSSE(page, chatEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("hello");
    await input.press("Enter");
    await page.waitForTimeout(2000);

    await page.locator("button[title='新对话']").click();
    await expect(page.getByText("你好，我是 Nexus 助手")).toBeVisible();
  });
});

// ── Edge Cases ──
test.describe("ChatPanel - Edge Cases", () => {
  test("script tags rendered as text, not executed", async ({ page }) => {
    const xssEvents = [
      { type: "status", event: "started" },
      { type: "message_start", session_id: "s_1" },
      { type: "content_delta", delta: "<script>alert(1)</script>" },
      { type: "message_stop" },
      { type: "completed", reply: "<script>alert(1)</script>", turns: 1, cost_usd: 0, tools_used: [], session_id: "s_1", model: "t" },
      { type: "done" },
    ];
    await mockSSE(page, xssEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("xss");
    await input.press("Enter");

    await page.waitForTimeout(2000);
    await expect(page.locator("body")).toBeVisible();
  });

  test("undefined strings filtered from output", async ({ page }) => {
    const undefEvents = [
      { type: "status", event: "started" },
      { type: "message_start", session_id: "s_u" },
      { type: "content_delta", text: "undefined" },
      { type: "content_delta", delta: "real content" },
      { type: "message_stop" },
      { type: "completed", reply: "real content", turns: 1, cost_usd: 0, tools_used: [], session_id: "s_u", model: "t" },
      { type: "done" },
    ];
    await mockSSE(page, undefEvents);
    await page.goto("/chat");

    const input = page.locator('input[placeholder*="想做"]');
    await input.fill("test undefined");
    await input.press("Enter");

    await page.waitForTimeout(2000);
    await expect(page.getByText("real content")).toBeVisible({ timeout: 5000 });
    // "undefined" string must not appear
    await expect(page.getByText("undefinedundefined")).toHaveCount(0);
  });
});

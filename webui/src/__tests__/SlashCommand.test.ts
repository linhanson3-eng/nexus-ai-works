import { describe, it, expect } from "vitest";
import { SLASH_COMMANDS, filterCommands, getCommandsByGroup } from "../lib/slashCommands";

describe("SlashCommand definitions", () => {
  it("所有命令 / 开头", () => {
    for (const cmd of SLASH_COMMANDS) {
      expect(cmd.name.startsWith("/")).toBe(true);
    }
  });

  it("无重复命令名", () => {
    const names = SLASH_COMMANDS.map((c) => c.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("所有命令都有可用的 icon", () => {
    for (const cmd of SLASH_COMMANDS) {
      expect(cmd.icon).toBeDefined();
    }
  });

  it("所有命令都有 action", () => {
    for (const cmd of SLASH_COMMANDS) {
      expect(cmd.action).toBeDefined();
      expect(["navigate", "send", "local"]).toContain(cmd.action.type);
    }
  });
});

describe("filterCommands", () => {
  it("空查询返回所有命令", () => {
    expect(filterCommands("")).toEqual(SLASH_COMMANDS);
  });

  it("按名称过滤", () => {
    const results = filterCommands("/help");
    expect(results.length).toBeGreaterThanOrEqual(1);
    expect(results[0].name).toBe("/help");
  });

  it("按描述过滤", () => {
    const results = filterCommands("token");
    expect(results.some((c) => c.name === "/cost" || c.name === "/compact")).toBe(true);
  });

  it("无匹配时返回空数组", () => {
    expect(filterCommands("/nonexistentxyz")).toEqual([]);
  });
});

describe("getCommandsByGroup", () => {
  it("按分组聚合命令", () => {
    const grouped = getCommandsByGroup(SLASH_COMMANDS);
    expect(grouped.has("navigation")).toBe(true);
    expect(grouped.has("agent")).toBe(true);
    const navCommands = grouped.get("navigation");
    expect(navCommands!.length).toBeGreaterThan(0);
  });

  it("分组按 order 排序", () => {
    const grouped = getCommandsByGroup(SLASH_COMMANDS);
    const entries = [...grouped.entries()];
    for (let i = 1; i < entries.length; i++) {
      const prevOrder = entries[i - 1][0] === "navigation" ? 1
        : entries[i - 1][0] === "agent" ? 2
        : entries[i - 1][0] === "workspace" ? 3
        : entries[i - 1][0] === "tools" ? 4
        : entries[i - 1][0] === "skills" ? 5 : 6;
      const currOrder = entries[i][0] === "navigation" ? 1
        : entries[i][0] === "agent" ? 2
        : entries[i][0] === "workspace" ? 3
        : entries[i][0] === "tools" ? 4
        : entries[i][0] === "skills" ? 5 : 6;
      expect(prevOrder).toBeLessThanOrEqual(currOrder);
    }
  });
});

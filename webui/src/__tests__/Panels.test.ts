import { describe, it, expect } from "vitest";
import {
  PANEL_REGISTRY, getMainPanels, getAdvancedPanels, getAllPanels,
} from "../lib/panels";

describe("PanelRegistry", () => {
  it("main 面板包含对话、我的助手、方案市场、定时任务", () => {
    const panels = getMainPanels();
    const ids = panels.map((p) => p.id);
    expect(ids).toEqual(["chat", "my-assistant", "market", "scheduled-tasks"]);
  });

  it("main 面板按 sortOrder 排序", () => {
    const panels = getMainPanels();
    for (let i = 1; i < panels.length; i++) {
      expect(panels[i - 1].sortOrder).toBeLessThan(panels[i].sortOrder);
    }
  });

  it("advanced 面板包含工作流、模版仓库、协作链、看板", () => {
    const panels = getAdvancedPanels();
    const ids = panels.map((p) => p.id);
    expect(ids).toContain("workflows");
    expect(ids).toContain("factory");
    expect(ids).toContain("chain");
    expect(ids).toContain("kanban");
  });

  it("factory 标签为 模版仓库", () => {
    const factory = PANEL_REGISTRY["factory"];
    expect(factory.label).toBe("模版仓库");
  });

  it("getAllPanels 返回 main + advanced", () => {
    const all = getAllPanels();
    expect(all.length).toBe(getMainPanels().length + getAdvancedPanels().length);
  });

  it("所有面板 id 不重复", () => {
    const all = getAllPanels();
    const ids = all.map((p) => p.id);
    expect(new Set(ids).size).toBe(ids.length);
  });

  it("所有面板都有 element", () => {
    const all = getAllPanels();
    for (const p of all) {
      expect(p.element).toBeDefined();
    }
  });
});

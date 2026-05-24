import { useState } from "react";
import { Key, Puzzle, Wrench, Blocks, Search } from "lucide-react";
import { useToast } from "./Toast";
import { ProvidersTab } from "./settings/ProvidersTab";
import { SearchTab } from "./settings/SearchTab";
import { SkillsTab } from "./settings/SkillsTab";
import { ToolsTab } from "./settings/ToolsTab";
import { PluginsTab } from "./settings/PluginsTab";

type TabId = "providers" | "search" | "skills" | "tools" | "plugins";

const tabs: { id: TabId; label: string; icon: typeof Key }[] = [
  { id: "providers", label: "LLM Key", icon: Key },
  { id: "search", label: "Web Search", icon: Search },
  { id: "skills", label: "技能库", icon: Puzzle },
  { id: "tools", label: "工具箱", icon: Wrench },
  { id: "plugins", label: "插件", icon: Blocks },
];

export function Settings() {
  const [tab, setTab] = useState<TabId>("providers");
  const toast = useToast();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">设置</h1>
        <p className="text-muted-foreground text-sm mt-1">LLM、技能、工具与插件管理</p>
      </div>

      <div className="flex gap-1 bg-card border border-border rounded-xl p-1.5 w-fit flex-wrap">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-md text-sm font-medium transition-all ${
              tab === id
                ? "bg-primary/10 text-primary border border-primary/20 shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      <div className="bg-card border border-border rounded-xl p-6">
        {tab === "providers" && <ProvidersTab toast={toast} />}
        {tab === "search" && <SearchTab toast={toast} />}
        {tab === "skills" && <SkillsTab toast={toast} />}
        {tab === "tools" && <ToolsTab toast={toast} />}
        {tab === "plugins" && <PluginsTab toast={toast} />}
      </div>
    </div>
  );
}

import { useState, DragEvent } from "react";
import { Search, Bot, GitBranch, Braces, ChevronDown, ChevronRight } from "lucide-react";

export interface PaletteNode {
  type: "agent" | "condition" | "transform";
  label: string;
  icon: React.ReactNode;
  description: string;
  defaultLabel: string;
}

const BUILTIN_NODES: { category: string; nodes: PaletteNode[] }[] = [
  {
    category: "AI Agent",
    nodes: [
      {
        type: "agent",
        label: "Agent 执行",
        icon: <Bot className="w-4 h-4" />,
        description: "选择一个 Agent 执行任务",
        defaultLabel: "Agent",
      },
    ],
  },
  {
    category: "控制流程",
    nodes: [
      {
        type: "condition",
        label: "条件判断",
        icon: <GitBranch className="w-4 h-4" />,
        description: "判断条件，分流到不同分支",
        defaultLabel: "IF",
      },
    ],
  },
  {
    category: "数据处理",
    nodes: [
      {
        type: "transform",
        label: "代码转换",
        icon: <Braces className="w-4 h-4" />,
        description: "执行代码或数据转换",
        defaultLabel: "Code",
      },
    ],
  },
];

interface Props {
  workspaceAgents: { name: string; type: string; model: string }[];
  onAddNode: (type: string, label: string) => void;
  onAddAgentNode: (agent: { name: string }) => void;
}

export function NodePalette({ workspaceAgents, onAddNode, onAddAgentNode }: Props) {
  const [search, setSearch] = useState("");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});

  const toggle = (cat: string) =>
    setCollapsed((c) => ({ ...c, [cat]: !c[cat] }));

  const filteredBuiltins = BUILTIN_NODES
    .map((cat) => ({
      ...cat,
      nodes: cat.nodes.filter(
        (n) =>
          !search ||
          n.label.includes(search) ||
          n.description.includes(search)
      ),
    }))
    .filter((cat) => cat.nodes.length > 0);

  const filteredAgents = workspaceAgents.filter(
    (a) => !search || a.name.includes(search)
  );

  const onDragStart = (event: DragEvent, data: { type: string; label: string; agentName?: string }) => {
    event.dataTransfer.setData("application/reactflow-type", data.type);
    event.dataTransfer.setData("application/reactflow-label", data.label);
    if (data.agentName) {
      event.dataTransfer.setData("application/reactflow-agent", data.agentName);
    }
    event.dataTransfer.effectAllowed = "move";
  };

  return (
    <div className="w-56 shrink-0 bg-card border border-border rounded-xl flex flex-col h-full">
      {/* Search */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center gap-2 px-2 py-1.5 bg-background border border-border rounded-md">
          <Search className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
          <input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="搜索节点..."
            className="bg-transparent text-xs outline-none w-full placeholder:text-muted-foreground/50"
          />
        </div>
      </div>

      {/* Node list */}
      <div className="flex-1 overflow-auto p-2 space-y-4">
        {filteredBuiltins.map((cat) => (
          <div key={cat.category}>
            <button
              onClick={() => toggle(cat.category)}
              className="flex items-center gap-1 w-full px-1 py-1 text-left"
            >
              {collapsed[cat.category] ? (
                <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
              ) : (
                <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
              )}
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground/60 font-medium">
                {cat.category}
              </span>
            </button>
            {!collapsed[cat.category] && (
              <div className="space-y-1 mt-1">
                {cat.nodes.map((node) => (
                  <button
                    key={node.type}
                    draggable
                    onDragStart={(e) =>
                      onDragStart(e, { type: node.type, label: node.defaultLabel })
                    }
                    onClick={() => onAddNode(node.type, node.defaultLabel)}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-left text-sm text-foreground/80 hover:text-foreground hover:bg-accent border border-transparent hover:border-ring/30 transition-all group"
                  >
                    <span className="text-muted-foreground group-hover:text-primary shrink-0">
                      {node.icon}
                    </span>
                    <div className="min-w-0">
                      <div className="text-xs font-medium truncate">
                        {node.label}
                      </div>
                      <div className="text-[9px] text-muted-foreground/50 truncate">
                        {node.description}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Workspace Agents */}
        {filteredAgents.length > 0 && (
          <div>
            <button
              onClick={() => toggle("workspace-agents")}
              className="flex items-center gap-1 w-full px-1 py-1 text-left"
            >
              {collapsed["workspace-agents"] ? (
                <ChevronRight className="w-3 h-3 text-muted-foreground/50" />
              ) : (
                <ChevronDown className="w-3 h-3 text-muted-foreground/50" />
              )}
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground/60 font-medium">
                项目 Agent
              </span>
              <span className="text-[9px] text-muted-foreground/40 ml-1">
                ({filteredAgents.length})
              </span>
            </button>
            {!collapsed["workspace-agents"] && (
              <div className="space-y-1 mt-1">
                {filteredAgents.map((a) => (
                  <button
                    key={a.name}
                    draggable
                    onDragStart={(e) =>
                      onDragStart(e, {
                        type: "agent",
                        label: a.name,
                        agentName: a.name,
                      })
                    }
                    onClick={() => onAddAgentNode(a)}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-left text-sm text-foreground/80 hover:text-foreground hover:bg-accent border border-transparent hover:border-ring/30 transition-all group"
                  >
                    <Bot className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary shrink-0" />
                    <div className="min-w-0">
                      <div className="text-xs truncate">{a.name}</div>
                      <div className="text-[9px] text-muted-foreground/50">
                        {a.type} · {a.model || "默认"}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}

        {filteredBuiltins.length === 0 && filteredAgents.length === 0 && (
          <p className="text-xs text-muted-foreground/40 text-center py-4">
            无匹配节点
          </p>
        )}
      </div>

      {/* Hint at bottom */}
      <div className="p-2 border-t border-border">
        <p className="text-[9px] text-muted-foreground/40 text-center">
          Tab 打开面板 · 拖拽到画布
        </p>
      </div>
    </div>
  );
}

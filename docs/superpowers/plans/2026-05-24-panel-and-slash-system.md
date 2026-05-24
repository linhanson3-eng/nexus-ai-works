# 板块添加系统 + / 命令系统 实现方案

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打造"技术流 3 分钟 aha moment"——ChatInput 按下 `/` 弹出与 Claude Code 完全一致的命令面板 + 默认界面干净（仅对话/总览），技术板块可整块添加。

**Architecture:** 两个独立子系统：(1) SlashCommand 系统——cmdk 驱动的命令面板嵌入 ChatInput，`/` 触发，命令镜像 Claude Code；(2) Panel 注册表——替代硬编码 navItems，支持动态启用/禁用板块，持久化到 localStorage。两者通过 ChatInput 的 `/panel` 命令和 Settings 的 Panels 标签建立联系。

**Tech Stack:** React 19, TypeScript 6, cmdk (已安装), Tailwind v3, shadcn/ui, react-router-dom v7, lucide-react

---

## 文件结构

```
webui/src/
├── lib/
│   ├── slashCommands.ts          # 新建 - Slash command 定义 + 分组
│   └── panels.ts                 # 新建 - Panel 注册表 + usePanels hook
├── components/
│   ├── ChatInput.tsx             # 修改 - 集成 / 命令面板
│   ├── Layout.tsx                # 修改 - 动态导航 + 板块快捷键
│   ├── Settings.tsx              # 修改 - 添加 Panels 标签页
│   └── settings/
│       └── PanelsTab.tsx         # 新建 - 板块管理 UI
```

---

### Task 1: Slash Command 定义

**Files:**
- Create: `webui/src/lib/slashCommands.ts`

- [ ] **Step 1: 创建 slash command 定义文件**

```typescript
import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Lightbulb, Settings, Sun, Moon, Monitor,
  Brain, Shield, Search, Terminal, FileText, Wrench,
  Puzzle, Zap, HelpCircle, Trash2, DollarSign,
  Globe, Key, Bug, Play, Pause, RotateCcw, BookOpen,
  Users, BarChart3, Clock, Layers, FolderOpen,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface SlashCommand {
  name: string;
  description: string;
  icon: LucideIcon;
  group: SlashCommandGroup;
  action: SlashCommandAction;
}

export type SlashCommandGroup =
  | "navigation"
  | "agent"
  | "tools"
  | "settings"
  | "workspace"
  | "skills";

export interface SlashCommandAction {
  type: "navigate" | "toggle" | "send" | "local";
  payload?: string;
}

export const SLASH_COMMAND_GROUPS: Record<SlashCommandGroup, { label: string; order: number }> = {
  navigation:  { label: "导航",       order: 1 },
  agent:       { label: "Agent",      order: 2 },
  workspace:   { label: "工作区",     order: 3 },
  tools:       { label: "工具",       order: 4 },
  skills:      { label: "技能",       order: 5 },
  settings:    { label: "设置",       order: 6 },
};

export const SLASH_COMMANDS: SlashCommand[] = [
  // ── Navigation ──
  { name: "/help",       description: "查看帮助和可用命令",           icon: HelpCircle,   group: "navigation", action: { type: "navigate", payload: "/dashboard" } },
  { name: "/chat",       description: "切换到对话",                   icon: MessageSquare, group: "navigation", action: { type: "navigate", payload: "/chat" } },
  { name: "/dashboard",  description: "切换到总览面板",               icon: Activity,      group: "navigation", action: { type: "navigate", payload: "/dashboard" } },
  { name: "/workshops",  description: "管理项目工作区",               icon: Blocks,        group: "navigation", action: { type: "navigate", payload: "/workshops" } },
  { name: "/factory",    description: "模版仓库",                     icon: Package,       group: "navigation", action: { type: "navigate", payload: "/factory" } },
  { name: "/kanban",     description: "打开看板",                     icon: Kanban,        group: "navigation", action: { type: "navigate", payload: "/kanban" } },
  { name: "/workflows",  description: "管理工作流",                   icon: GitBranch,     group: "navigation", action: { type: "navigate", payload: "/workflows" } },
  { name: "/market",     description: "方案市场",                     icon: Lightbulb,     group: "navigation", action: { type: "navigate", payload: "/market" } },
  { name: "/settings",   description: "打开设置",                     icon: Settings,      group: "navigation", action: { type: "navigate", payload: "/settings" } },

  // ── Agent ──
  { name: "/clear",      description: "清除当前对话上下文",           icon: Trash2,        group: "agent",      action: { type: "send", payload: "/clear" } },
  { name: "/compact",    description: "压缩上下文以释放 token",       icon: Layers,        group: "agent",      action: { type: "send", payload: "/compact" } },
  { name: "/model",      description: "切换 AI 模型",                 icon: Brain,         group: "agent",      action: { type: "local" } },
  { name: "/cost",       description: "查看 token 用量和成本",       icon: DollarSign,    group: "agent",      action: { type: "navigate", payload: "/dashboard" } },
  { name: "/status",     description: "显示当前 Agent 状态",          icon: Activity,      group: "agent",      action: { type: "send", payload: "/status" } },
  { name: "/context",    description: "查看当前上下文信息",           icon: FileText,      group: "agent",      action: { type: "send", payload: "/context" } },
  { name: "/memory",     description: "查看记忆系统状态",             icon: Brain,         group: "agent",      action: { type: "send", payload: "/memory" } },

  // ── Workspace ──
  { name: "/init",       description: "初始化当前工作区",             icon: Zap,           group: "workspace",  action: { type: "send", payload: "/init" } },
  { name: "/workspace",  description: "切换工作区",                   icon: Blocks,        group: "workspace",  action: { type: "local" } },
  { name: "/doctor",     description: "检查环境配置是否正确",         icon: Bug,           group: "workspace",  action: { type: "send", payload: "/doctor" } },
  { name: "/search",     description: "搜索代码库",                   icon: Search,        group: "workspace",  action: { type: "send", payload: "/search" } },

  // ── Tools ──
  { name: "/agents",     description: "列出所有 Agent",               icon: Users,         group: "tools",      action: { type: "send", payload: "/agents" } },
  { name: "/tasks",      description: "查看当前任务列表",             icon: BarChart3,     group: "tools",      action: { type: "send", payload: "/tasks" } },
  { name: "/todos",      description: "管理待办事项",                 icon: BarChart3,     group: "tools",      action: { type: "send", payload: "/todos" } },
  { name: "/permissions",description: "管理工具权限",                 icon: Shield,        group: "tools",      action: { type: "navigate", payload: "/settings" } },
  { name: "/plugin",     description: "管理插件",                     icon: Puzzle,        group: "tools",      action: { type: "navigate", payload: "/settings" } },
  { name: "/mcp",        description: "管理 MCP 服务",                icon: Wrench,        group: "tools",      action: { type: "send", payload: "/mcp" } },
  { name: "/bashes",     description: "查看最近执行的命令",           icon: Terminal,      group: "tools",      action: { type: "send", payload: "/bashes" } },
  { name: "/stats",      description: "查看使用统计",                 icon: BarChart3,     group: "tools",      action: { type: "navigate", payload: "/dashboard" } },

  // ── Skills ──
  { name: "/skills",     description: "列出可用技能",                 icon: Puzzle,        group: "skills",     action: { type: "navigate", payload: "/settings" } },
  { name: "/hooks",      description: "配置自动化钩子",               icon: Zap,           group: "skills",     action: { type: "send", payload: "/hooks" } },
  { name: "/checkpoint", description: "创建检查点",                   icon: Clock,         group: "skills",     action: { type: "send", payload: "/checkpoint" } },
  { name: "/loop",       description: "循环执行任务",                 icon: RotateCcw,     group: "skills",     action: { type: "send", payload: "/loop" } },
  { name: "/plan",       description: "创建实施计划",                 icon: BookOpen,      group: "skills",     action: { type: "send", payload: "/plan" } },
  { name: "/review",     description: "代码审查",                     icon: Shield,        group: "skills",     action: { type: "send", payload: "/review" } },
  { name: "/security-review", description: "安全审计",                icon: Shield,        group: "skills",     action: { type: "send", payload: "/security-review" } },
  { name: "/pr",         description: "创建 Pull Request",            icon: GitBranch,     group: "skills",     action: { type: "send", payload: "/pr" } },

  // ── Settings ──
  { name: "/config",     description: "配置 LLM 提供商和 API Key",    icon: Key,           group: "settings",   action: { type: "navigate", payload: "/settings" } },
  { name: "/theme",      description: "切换主题 (亮色/暗色/系统)",    icon: Sun,           group: "settings",   action: { type: "local" } },
  { name: "/output-style", description: "设置输出风格",               icon: FileText,      group: "settings",   action: { type: "send", payload: "/output-style" } },
  { name: "/panel",      description: "管理界面板块 (添加/移除功能)", icon: Blocks,        group: "settings",   action: { type: "navigate", payload: "/settings" } },
  { name: "/export",     description: "导出对话记录",                 icon: FolderOpen,    group: "settings",   action: { type: "send", payload: "/export" } },
  { name: "/login",      description: "登录账号",                     icon: Key,           group: "settings",   action: { type: "navigate", payload: "/auth" } },
  { name: "/logout",     description: "退出登录",                     icon: Key,           group: "settings",   action: { type: "local" } },
];

export function filterCommands(query: string): SlashCommand[] {
  if (!query) return SLASH_COMMANDS;
  const q = query.toLowerCase();
  return SLASH_COMMANDS.filter(
    (c) =>
      c.name.toLowerCase().includes(q) ||
      c.description.toLowerCase().includes(q) ||
      c.group.toLowerCase().includes(q)
  );
}

export function getCommandsByGroup(commands: SlashCommand[]): Map<SlashCommandGroup, SlashCommand[]> {
  const map = new Map<SlashCommandGroup, SlashCommand[]>();
  for (const c of commands) {
    const list = map.get(c.group) ?? [];
    list.push(c);
    map.set(c.group, list);
  }
  const sorted = new Map<SlashCommandGroup, SlashCommand[]>();
  const entries = [...map.entries()].sort(
    (a, b) => SLASH_COMMAND_GROUPS[a[0]].order - SLASH_COMMAND_GROUPS[b[0]].order
  );
  for (const [k, v] of entries) sorted.set(k, v);
  return sorted;
}
```

---

### Task 2: ChatInput 集成 / 命令面板

**Files:**
- Modify: `webui/src/components/ChatInput.tsx`

- [ ] **Step 1: 在 ChatInput 中集成 cmdk 弹出面板**

修改 ChatInput.tsx，关键变更：

1. 添加 `useRef` 追踪 `/` 触发状态
2. 用 cmdk 的 `Command` 组件包裹弹出面板
3. 监听 `onChange` —— 输入以 `/` 开头时展开命令菜单
4. 选择命令后执行对应 action（navigate/发送/本地 toggle）
5. 需要 `useNavigate` 和 `useTheme` hooks 来支持 navigate 和 theme 切换 action

将 ChatInput 改为：

```tsx
import { type FormEvent, type DragEvent, useRef, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Square, Paperclip, ChevronDown, Brain, CornerDownRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Command, CommandInput, CommandList, CommandEmpty, CommandGroup, CommandItem,
} from "@/components/ui/command";
import {
  SLASH_COMMANDS, filterCommands, getCommandsByGroup,
  SLASH_COMMAND_GROUPS,
} from "../lib/slashCommands";
import { useTheme } from "./ThemeProvider";
import type { SlashCommand, SlashCommandGroup } from "../lib/slashCommands";

// ... [保留 Attachment, ProviderGroup 等 interface 不变] ...

// ... [保留 REASONING_EFFORTS, REASONING_LABELS, REASONING_MODEL_KEYWORDS 等常量不变] ...

function supportsReasoning(model: string): boolean {
  return REASONING_MODEL_KEYWORDS.some((k) => model.toLowerCase().includes(k));
}

// ... [保留 ModelCombobox 组件不变] ...

interface ChatInputProps {
  // ... [保留原有 props 不变] ...
  onSlashSend?: (command: string) => void;  // 新增: 用于 /command 直接发送到后端
}

export function ChatInput({
  input, setInput, loading, workshops, activeWs, setActiveWs,
  model, setModel, reasoningEffort, setReasoningEffort,
  chatProviderGroups, attachments, removeAttachment,
  onSend, onCancel, onFileSelect,
  onSlashSend,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const { setTheme } = useTheme();

  const [slashOpen, setSlashOpen] = useState(false);
  const [slashQuery, setSlashQuery] = useState("");

  // 追踪输入内容中 / 是否触发命令面板
  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);

    // 仅当输入以独立 / 开头时触发命令面板
    if (value.startsWith("/") && !value.includes(" ")) {
      setSlashOpen(true);
      setSlashQuery(value);
    } else if (slashOpen) {
      setSlashOpen(false);
      setSlashQuery("");
    }
  };

  // 执行命令
  const executeSlashCommand = (cmd: SlashCommand) => {
    setSlashOpen(false);
    setSlashQuery("");

    switch (cmd.action.type) {
      case "navigate":
        setInput("");
        navigate(cmd.action.payload ?? "/");
        break;
      case "send":
        setInput("");
        onSlashSend?.(cmd.action.payload ?? cmd.name);
        break;
      case "local":
        setInput("");
        if (cmd.name === "/theme") {
          const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
          import("./ThemeProvider").then(({ useTheme: _useTheme }) => {
            // 通过 document 事件触发主题切换，避免循环依赖
            document.dispatchEvent(new CustomEvent("nexus:cycle-theme"));
          });
        } else if (cmd.name === "/workspace") {
          // focus workspace select
          inputRef.current?.focus();
        } else if (cmd.name === "/model") {
          // focus model select — handled by focus ring
        } else if (cmd.name === "/logout") {
          document.dispatchEvent(new CustomEvent("nexus:logout"));
        }
        break;
    }
  };

  // 根据输入过滤命令
  const filteredCommands = slashOpen ? filterCommands(slashQuery) : [];
  const groupedCommands = slashOpen ? getCommandsByGroup(filteredCommands) : new Map();

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (slashOpen) return; // 命令面板展开时不发送
    const text = input.trim();
    if ((!text && !attachments.length) || loading) return;
    onSend();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (slashOpen) {
      if (e.key === "Escape") {
        setSlashOpen(false);
        setSlashQuery("");
        setInput("");
        e.preventDefault();
      }
      return; // cmdk 接管键盘导航
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const showReasoning = supportsReasoning(model);

  return (
    <div className="shrink-0 pt-3 border-t border-border relative">
      {/* ... [保留附件预览部分不变] ... */}
      {attachments.length > 0 && (
        <div className="flex gap-2 flex-wrap pb-2">
          {attachments.map((a, i) => (
            <div key={i} className="relative group bg-muted border border-border rounded-md overflow-hidden">
              {a.type === "image" && a.dataUrl ? (
                <div className="w-14 h-14"><img src={a.dataUrl} alt={a.name} className="w-full h-full object-cover" /></div>
              ) : (
                <div className="w-14 h-14 flex items-center justify-center text-[10px] text-muted-foreground px-1 text-center leading-tight">{a.name.slice(0, 20)}</div>
              )}
              <button onClick={() => removeAttachment(i)} className="absolute -top-1 -right-1 w-4 h-4 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">&times;</button>
            </div>
          ))}
        </div>
      )}

      {/* Slash Command Panel */}
      {slashOpen && filteredCommands.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-1 z-50">
          <div className="bg-popover border border-border rounded-lg shadow-lg overflow-hidden max-h-72">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <span className="text-xs text-muted-foreground">命令</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">esc</span>
              <span className="text-[10px] text-muted-foreground/50">关闭</span>
            </div>
            <div className="overflow-y-auto max-h-56">
              {[...groupedCommands.entries()].map(([group, cmds]) => {
                const groupMeta = SLASH_COMMAND_GROUPS[group as SlashCommandGroup];
                return (
                  <div key={group}>
                    <div className="px-3 py-1.5 text-[10px] text-muted-foreground/50 uppercase tracking-wider">
                      {groupMeta?.label ?? group}
                    </div>
                    {cmds.map((cmd) => (
                      <button
                        key={cmd.name}
                        onClick={() => executeSlashCommand(cmd)}
                        className="w-full flex items-center gap-2.5 px-4 py-1.5 text-sm hover:bg-accent transition-colors text-left"
                      >
                        <cmd.icon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="font-mono text-xs text-foreground font-medium">{cmd.name}</span>
                        <span className="text-xs text-muted-foreground/70 truncate">{cmd.description}</span>
                        <CornerDownRight className="w-3 h-3 text-muted-foreground/30 ml-auto shrink-0" />
                      </button>
                    ))}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {slashOpen && filteredCommands.length === 0 && slashQuery !== "/" && (
        <div className="absolute bottom-full left-0 right-0 mb-1 z-50">
          <div className="bg-popover border border-border rounded-lg shadow-lg p-6 text-center">
            <p className="text-sm text-muted-foreground">未匹配到命令</p>
            <p className="text-xs text-muted-foreground/50 mt-1">输入 / 查看所有可用命令</p>
          </div>
        </div>
      )}

      <form onSubmit={submit} className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2 focus-within:border-primary/30 transition-colors shadow-sm">
        <input ref={fileInputRef} type="file" multiple className="hidden"
          onChange={(e) => { onFileSelect(e.target.files); e.target.value = ""; }}
          accept="image/*,.pdf,.txt,.md,.json,.csv,.yaml,.yml,.py,.ts,.tsx,.js,.jsx,.html,.css" />
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={loading}
          className="p-1.5 text-muted-foreground/50 hover:text-muted-foreground hover:bg-accent/50 rounded-md transition-colors disabled:opacity-30 shrink-0" title="上传附件">
          <Paperclip className="w-4 h-4" />
        </button>

        <input ref={inputRef}
          value={input} onChange={handleInputChange} onKeyDown={handleKeyDown}
          placeholder={loading ? "Agent 正在工作中..." : "说你想做什么... 输入 / 查看命令"} disabled={loading}
          className="flex-1 bg-transparent border-none outline-none px-0 py-1 text-sm text-foreground placeholder:text-muted-foreground/50 disabled:opacity-50 min-w-0" />

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Workspace */}
          <div className="relative">
            <select value={activeWs} onChange={(e) => setActiveWs(e.target.value)}
              className="appearance-none bg-background border border-border hover:border-ring/30 rounded-md pl-2 pr-5 py-1 text-[11px] text-muted-foreground outline-none cursor-pointer transition-colors max-w-[90px] truncate">
              <option value="">项目</option>
              {workshops.map((w) => <option key={w.name} value={w.name}>{w.name}</option>)}
            </select>
            <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-muted-foreground/40 pointer-events-none" />
          </div>

          {/* Model combobox */}
          <ModelCombobox
            value={model}
            onChange={(v) => { setModel(v); if (!supportsReasoning(v)) setReasoningEffort(""); }}
            groups={chatProviderGroups}
            onSelectEnd={() => {}}
          />

          {/* Reasoning */}
          {showReasoning && (
            <div className="relative">
              <select value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)}
                className="appearance-none bg-primary/[0.06] border border-primary/[0.15] hover:border-primary/30 rounded-md pl-2 pr-4 py-1 text-[11px] text-primary/80 outline-none cursor-pointer transition-colors">
                {REASONING_EFFORTS.map((e) => <option key={e} value={e}>{e ? REASONING_LABELS[e] : "关"}</option>)}
              </select>
              <Brain className="absolute right-0.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-primary/30 pointer-events-none" />
            </div>
          )}

          {loading ? (
            <button type="button" onClick={onCancel}
              className="p-1.5 text-destructive hover:bg-destructive/10 rounded-md transition-colors" title="停止">
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <Button type="submit" variant="outline" size="icon" disabled={(!input.trim() && !attachments.length) || slashOpen} className="h-8 w-8">
              <Send className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}
```

- [ ] **Step 2: ChatPanel 适配 onSlashSend**

修改 `webui/src/components/ChatPanel.tsx`——在 ChatInput 上添加 `onSlashSend` prop，将命令文本直接发送到 SSE 流：

```tsx
const handleSlashSend = (command: string) => {
  // 直接以 command 文本发送到后端
  sendMessage(command);
};
```

传入 ChatInput：`<ChatInput ... onSlashSend={handleSlashSend} />`

---

### Task 3: Panel 注册表 + Dynamic 导航

**Files:**
- Create: `webui/src/lib/panels.ts`
- Modify: `webui/src/components/Layout.tsx`

- [ ] **Step 1: 创建 Panel 注册表**

```typescript
import { lazy, type LazyExoticComponent, type ComponentType } from "react";
import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Lightbulb, Bot, Clock,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface PanelDefinition {
  id: string;
  label: string;
  icon: LucideIcon;
  route: string;
  category: "core" | "advanced";
  defaultEnabled: boolean;
  description: string;
  element: LazyExoticComponent<ComponentType<Record<string, never>>>;
}

const ChatPanel = lazy(() => import("../components/ChatPanel"));
const Dashboard = lazy(() => import("../components/Dashboard"));
const MyAssistant = lazy(() => import("../components/MyAssistant"));       // 新建
const ScheduledTasks = lazy(() => import("../components/ScheduledTasks")); // 新建
const WorkshopList = lazy(() => import("../components/WorkshopList"));
const KanbanBoard = lazy(() => import("../components/KanbanBoard"));
const WorkflowList = lazy(() => import("../components/WorkflowList"));
const ModuleFactory = lazy(() => import("../components/ModuleFactory"));
const Marketplace = lazy(() => import("../components/Marketplace"));

export const PANEL_REGISTRY: Record<string, PanelDefinition> = {
  chat: {
    id: "chat",
    label: "对话",
    icon: MessageSquare,
    route: "/chat",
    category: "core",
    defaultEnabled: true,
    description: "Agent 对话窗口，输入 / 查看命令",
    element: ChatPanel,
  },
  "my-assistant": {
    id: "my-assistant",
    label: "我的助手",
    icon: Bot,
    route: "/my-assistant",
    category: "core",
    defaultEnabled: true,
    description: "管理和配置你的 AI 助手：选角色、调风格、设偏好",
    element: MyAssistant,  // 新建占位组件
  },
  "scheduled-tasks": {
    id: "scheduled-tasks",
    label: "定时任务",
    icon: Clock,
    route: "/scheduled-tasks",
    category: "core",
    defaultEnabled: true,
    description: "安排 AI 定时帮你做事：每天总结、定时检查、周期性报告",
    element: ScheduledTasks,  // 新建占位组件
  },
  dashboard: {
    id: "dashboard",
    label: "总览",
    icon: Activity,
    route: "/dashboard",
    category: "advanced",
    defaultEnabled: false,
    description: "运营仪表盘：token 消耗、Agent 执行成功率、成本曲线",
    element: Dashboard,
  },
  workshops: {
    id: "workshops",
    label: "项目",
    icon: Blocks,
    route: "/workshops",
    category: "advanced",
    defaultEnabled: false,
    description: "管理多个工作区，每个工作区有独立的 Agent、记忆和上下文",
    element: WorkshopList,
  },
  workflows: {
    id: "workflows",
    label: "工作流",
    icon: GitBranch,
    route: "/workflows",
    category: "advanced",
    defaultEnabled: false,
    description: "DAG 工作流画布，拖拽编排多 Agent 协作流程",
    element: WorkflowList,
  },
  kanban: {
    id: "kanban",
    label: "看板",
    icon: Kanban,
    route: "/kanban",
    category: "advanced",
    defaultEnabled: false,
    description: "项目看板，拖拽管理任务，WebSocket 实时同步",
    element: KanbanBoard,
  },
  factory: {
    id: "factory",
    label: "模版",
    icon: Package,
    route: "/factory",
    category: "advanced",
    defaultEnabled: false,
    description: "模版仓库，导入/导出工作流模板和 Agent 配置",
    element: ModuleFactory,
  },
  market: {
    id: "market",
    label: "方案",
    icon: Lightbulb,
    route: "/market",
    category: "advanced",
    defaultEnabled: false,
    description: "方案市场，发现和安装社区共享的方案包",
    element: Marketplace,
  },
};

const STORAGE_KEY = "nexus_enabled_panels";

function loadEnabledPanels(): string[] {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw) as string[];
  } catch { /* ignore */ }
  return Object.values(PANEL_REGISTRY)
    .filter((p) => p.defaultEnabled)
    .map((p) => p.id);
}

function saveEnabledPanels(ids: string[]): void {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
}

export function getEnabledPanels(): PanelDefinition[] {
  const ids = loadEnabledPanels();
  return ids.map((id) => PANEL_REGISTRY[id]).filter(Boolean);
}

export function getAvailablePanels(): PanelDefinition[] {
  return Object.values(PANEL_REGISTRY);
}

export function isPanelEnabled(id: string): boolean {
  return loadEnabledPanels().includes(id);
}

export function enablePanel(id: string): void {
  const ids = loadEnabledPanels();
  if (!ids.includes(id)) {
    ids.push(id);
    saveEnabledPanels(ids);
  }
}

export function disablePanel(id: string): void {
  const ids = loadEnabledPanels().filter((i) => i !== id);
  saveEnabledPanels(ids);
}

export function resetPanels(): void {
  localStorage.removeItem(STORAGE_KEY);
}
```

- [ ] **Step 2: 重写 Layout.tsx 使用动态导航**

Layout.tsx 改为从 `usePanels` hook 读取启用的板块：

```tsx
import { useState, useMemo } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  Zap, Settings, LogOut, User,
  Sun, Moon, Monitor, Search, ChevronRight, ChevronLeft,
} from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { useTheme } from "./ThemeProvider";
import { getEnabledPanels } from "../lib/panels";

const themeIcons: Record<string, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

export function Layout() {
  function loadSidebarPref(): boolean {
    const v = localStorage.getItem("nexus_sidebar_collapsed");
    if (v === null) return false;
    return v === "1";
  }

  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(loadSidebarPref);

  // 动态读取启用的板块
  const [panelVersion, setPanelVersion] = useState(0);
  const navItems = useMemo(() => {
    // panelVersion 用于在板块变更后强制刷新
    void panelVersion;
    return getEnabledPanels().map((p) => ({
      to: p.route,
      label: p.label,
      icon: p.icon,
      id: p.id,
    }));
  }, [panelVersion]);

  // 监听板块变更事件
  const refreshPanels = () => setPanelVersion((v) => v + 1);

  // 监听主题切换事件（来自 /theme 命令）
  const cycleTheme = () => {
    const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % order.length]);
  };

  // ... 省略 Layout 返回的 JSX，与现有一致但 navItems 改为 useMemo 计算 ...

  return (
    <div className="flex h-screen bg-background">
      {/* Left sidebar */}
      <aside
        className={`shrink-0 bg-card border-r border-border flex flex-col transition-all duration-200 max-md:hidden ${
          collapsed ? "w-14" : "w-56"
        }`}
      >
        {/* Logo */}
        <button
          onClick={toggleCollapsed}
          className="h-12 flex items-center gap-2.5 px-3 border-b border-border hover:bg-accent/50 transition-colors"
        >
          <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
            <Zap className="w-3.5 h-3.5 text-primary" />
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight">Nexus AI</span>
          )}
        </button>

        {/* User ping */}
        {user && !collapsed && (
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
              <User className="w-2.5 h-2.5 text-primary" />
            </div>
            <span className="text-xs text-muted-foreground truncate">{user.username}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0 ml-auto" />
          </div>
        )}

        {/* Dynamic Nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                }`
              }
              title={collapsed ? label : undefined}
            >
              <Icon className="w-4.5 h-4.5 shrink-0" />
              {!collapsed && <span className="text-sm">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-2 border-t border-border space-y-0.5">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              }`
            }
            title={collapsed ? "设置" : undefined}
          >
            <Settings className="w-4.5 h-4.5 shrink-0" />
            {!collapsed && <span className="text-sm">设置</span>}
          </NavLink>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-md w-full text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-colors"
          >
            <LogOut className="w-4.5 h-4.5 shrink-0" />
            {!collapsed && <span className="text-sm">退出</span>}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-12 border-b border-border bg-card/50 backdrop-blur-sm flex items-center px-4 gap-3 shrink-0">
          <button
            onClick={toggleCollapsed}
            className="p-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md max-md:hidden"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>

          <div className="flex-1" />

          {/* Search trigger */}
          <button
            onClick={() => console.log("[Search] global search triggered")}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground bg-accent/50 border border-border rounded-md hover:border-ring/30 transition-colors"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="w-32 text-left">搜索...</span>
            <kbd className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground font-mono">/</kbd>
          </button>

          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className="p-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md"
            title={`主题: ${theme}`}
          >
            <ThemeIcon className="w-4 h-4" />
          </button>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6 max-md:pb-20">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav — also dynamic */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/90 backdrop-blur-xl border-t border-border z-40 flex justify-around py-2">
        {[...navItems, { to: "/settings", label: "设置", icon: Settings }].map(
          ({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] transition-colors ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              <Icon className="w-5 h-5" />
              {label}
            </NavLink>
          ),
        )}
      </nav>
    </div>
  );
}
```

需要补齐 Layout 中缺失的变量声明：
```tsx
const toggleCollapsed = () => {
  const next = !collapsed;
  setCollapsed(next);
  localStorage.setItem("nexus_sidebar_collapsed", next ? "1" : "0");
};

const handleLogout = () => {
  logout();
  navigate("/auth", { replace: true });
};

const ThemeIcon = themeIcons[theme];
```

- [ ] **Step 3: 更新 App.tsx 路由动态注册**

修改 `webui/src/App.tsx`——用 `PANEL_REGISTRY` 动态生成 `<Route>`：

```tsx
function AppRoutes() {
  const [showOnboarding, setShowOnboarding] = useState(
    !localStorage.getItem("nexus_onboarding_done"),
  );
  const [enabledPanels, setEnabledPanels] = useState<string[]>(() => {
    try {
      const raw = localStorage.getItem("nexus_enabled_panels");
      if (raw) return JSON.parse(raw) as string[];
    } catch { /* */ }
    return Object.values(PANEL_REGISTRY)
      .filter((p) => p.defaultEnabled)
      .map((p) => p.id);
  });

  const finishOnboarding = () => {
    localStorage.setItem("nexus_onboarding_done", "1");
    setShowOnboarding(false);
    api.savePreferences({ onboarding_done: true }).catch(() => {});
  };

  return (
    <>
      {showOnboarding && <Onboarding onDone={finishOnboarding} />}
      <Routes>
        <Route path="/auth" element={<PublicRoute><AuthPage /></PublicRoute>} />
        <Route element={<ProtectedRoute><Layout /></ProtectedRoute>}>
          <Route path="/" element={<Navigate to="/chat" replace />} />
          {/* Dynamic routes from panel registry */}
          {Object.values(PANEL_REGISTRY).map((panel) => (
            <Route
              key={panel.id}
              path={panel.route.replace("/", "")}
              element={
                <ErrorBoundary>
                  <Suspense fallback={
                    <div className="flex items-center justify-center h-full min-h-[200px]">
                      <div className="w-6 h-6 border-2 border-accent/30 border-t-accent rounded-full animate-spin" />
                    </div>
                  }>
                    <panel.element />
                  </Suspense>
                </ErrorBoundary>
              }
            />
          ))}
          <Route path="/settings" element={<ErrorBoundary><Settings /></ErrorBoundary>} />
          <Route path="*" element={<Navigate to="/chat" replace />} />
        </Route>
      </Routes>
    </>
  );
}
```

需要在 App.tsx 顶部添加 import：
```tsx
import { Suspense } from "react";
import { PANEL_REGISTRY } from "./lib/panels";
```

---

### Task 4: Settings Panels 标签页

**Files:**
- Create: `webui/src/components/settings/PanelsTab.tsx`
- Modify: `webui/src/components/Settings.tsx`

- [ ] **Step 1: 创建 PanelsTab 组件**

```tsx
import { useState } from "react";
import { Switch } from "@/components/ui/switch";
import { Badge } from "@/components/ui/badge";
import {
  getAvailablePanels,
  isPanelEnabled,
  enablePanel,
  disablePanel,
  PANEL_REGISTRY,
} from "../../lib/panels";
import type { PanelDefinition } from "../../lib/panels";

interface PanelsTabProps {
  toast: { show: (msg: string) => void };
}

export function PanelsTab({ toast }: PanelsTabProps) {
  const [refresh, setRefresh] = useState(0);

  const panels = getAvailablePanels();
  const corePanels = panels.filter((p) => p.category === "core");
  const advancedPanels = panels.filter((p) => p.category === "advanced");

  const handleToggle = (panel: PanelDefinition) => {
    if (isPanelEnabled(panel.id)) {
      // 核心板块不允许禁用
      if (panel.category === "core") {
        toast.show("核心板块不可禁用");
        return;
      }
      disablePanel(panel.id);
      toast.show(`已移除「${panel.label}」板块`);
    } else {
      enablePanel(panel.id);
      toast.show(`已添加「${panel.label}」板块`);
    }
    setRefresh((v) => v + 1);
  };

  const PanelCard = ({ panel }: { panel: PanelDefinition }) => {
    const enabled = isPanelEnabled(panel.id);
    return (
      <div
        className={`flex items-start gap-4 p-4 rounded-lg border transition-colors ${
          enabled
            ? "border-primary/30 bg-primary/[0.02]"
            : "border-border bg-card hover:border-ring/20"
        }`}
      >
        <div className="w-9 h-9 rounded-md bg-primary/10 flex items-center justify-center shrink-0 mt-0.5">
          <panel.icon className="w-4.5 h-4.5 text-primary/70" />
        </div>
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <h3 className="text-sm font-medium">{panel.label}</h3>
            {panel.category === "core" && (
              <Badge variant="outline" className="text-[10px] px-1.5 py-0">核心</Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground mt-1">{panel.description}</p>
        </div>
        <Switch
          checked={enabled}
          onCheckedChange={() => handleToggle(panel)}
          disabled={panel.category === "core"}
          className="shrink-0 mt-1"
        />
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold">高级功能</h2>
        <p className="text-sm text-muted-foreground mt-1">
          根据需要开启高级功能。核心功能始终启用。
        </p>
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">核心板块</h3>
        {corePanels.map((p) => (
          <PanelCard key={p.id} panel={p} />
        ))}
      </div>

      <div className="space-y-3">
        <h3 className="text-sm font-medium text-muted-foreground">高级板块</h3>
        {advancedPanels.map((p) => (
          <PanelCard key={p.id} panel={p} />
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 需要在 ui/ 中确认 Switch 和 Badge 组件存在**

检查：
```
webui/src/components/ui/switch.tsx
webui/src/components/ui/badge.tsx
```

如果不存在（badge.tsx 存在于 `webui/src/components/ui/badge.tsx` 但 Switch 可能不存在于当前项目中），需要创建：

**webui/src/components/ui/switch.tsx:**
```tsx
import * as React from "react";
import * as SwitchPrimitives from "@radix-ui/react-switch";
import { cn } from "@/lib/utils";

function Switch({
  className,
  ...props
}: React.ComponentProps<typeof SwitchPrimitives.Root>) {
  return (
    <SwitchPrimitives.Root
      data-slot="switch"
      className={cn(
        "peer inline-flex h-5 w-9 shrink-0 cursor-pointer items-center rounded-full border-2 border-transparent shadow-sm transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background disabled:cursor-not-allowed disabled:opacity-50 data-[state=checked]:bg-primary data-[state=unchecked]:bg-input",
        className
      )}
      {...props}
    >
      <SwitchPrimitives.Thumb
        data-slot="switch-thumb"
        className={cn(
          "pointer-events-none block h-4 w-4 rounded-full bg-background shadow-lg ring-0 transition-transform data-[state=checked]:translate-x-4 data-[state=unchecked]:translate-x-0"
        )}
      />
    </SwitchPrimitives.Root>
  );
}

export { Switch };
```

- [ ] **Step 3: 更新 Settings.tsx 添加板块标签**

在 Settings.tsx 中添加 "板块" 标签：

```tsx
import { PanelsTab } from "./settings/PanelsTab";

type TabId = "providers" | "search" | "skills" | "tools" | "plugins" | "panels";

const tabs: { id: TabId; label: string; icon: typeof Key }[] = [
  { id: "providers", label: "LLM Key", icon: Key },
  { id: "search", label: "Web Search", icon: Search },
  { id: "skills", label: "技能库", icon: Puzzle },
  { id: "tools", label: "工具箱", icon: Wrench },
  { id: "plugins", label: "插件", icon: Blocks },
  { id: "panels", label: "高级功能", icon: Layout },  // 新增
];
```

并在 tab 内容区添加：
```tsx
{tab === "panels" && <PanelsTab toast={toast} />}
```

需要引入 `Layout` 图标：
```tsx
import { Key, Puzzle, Wrench, Blocks, Search, Layout } from "lucide-react";
```

---

### Task 5: 板块变更通知机制

**Files:**
- Modify: `webui/src/components/Layout.tsx` — 已完成（useMemo + panelVersion）
- Modify: `webui/src/components/settings/PanelsTab.tsx` — 已完成（toggle 后 setRefresh）

板块启用/禁用后，Layout 需要重新渲染导航。由于 Layout 和 PanelsTab 不在同一个 React 子树中，使用自定义事件来通知：

- [ ] **Step 1: 在 PanelsTab toggle 后触发自定义事件**

在 PanelsTab.tsx 的 `handleToggle` 最后添加：
```tsx
window.dispatchEvent(new CustomEvent("nexus:panels-changed"));
```

- [ ] **Step 2: 在 Layout.tsx 中监听事件**

在 Layout 组件中添加 useEffect：
```tsx
useEffect(() => {
  const handler = () => setPanelVersion((v) => v + 1);
  window.addEventListener("nexus:panels-changed", handler);
  return () => window.removeEventListener("nexus:panels-changed", handler);
}, []);
```

Layout 顶部需要引入 `useEffect`。

---

### Task 6: 默认面板策略 —— 首次访问初始化

**Files:**
- Modify: `webui/src/lib/panels.ts` — 添加初始化逻辑

- [ ] **Step: 添加首次使用初始化函数**

```typescript
const INIT_FLAG_KEY = "nexus_panels_initialized";

export function ensurePanelsInitialized(): void {
  if (localStorage.getItem(INIT_FLAG_KEY)) return;

  // 首次访问：仅启用核心面板
  const coreIds = Object.values(PANEL_REGISTRY)
    .filter((p) => p.category === "core" && p.defaultEnabled)
    .map((p) => p.id);

  saveEnabledPanels(coreIds);
  localStorage.setItem(INIT_FLAG_KEY, "1");
}
```

在 `App.tsx` 的 `AppRoutes` 组件中调用：
```tsx
import { ensurePanelsInitialized } from "../lib/panels";

function AppRoutes() {
  // 在组件初始化时调用
  ensurePanelsInitialized();
  // ... 其余不变
}
```

---

### Task 7: 验证 + 测试

**Files:**
- 测试: `webui/src/components/__tests__/SlashCommand.test.tsx`
- 测试: `webui/src/components/__tests__/Panels.test.tsx`

- [ ] **Step 1: SlashCommand 数据完整性测试**

```typescript
import { describe, it, expect } from "vitest";
import { SLASH_COMMANDS, filterCommands, getCommandsByGroup } from "../../lib/slashCommands";

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
});
```

- [ ] **Step 2: Panel 注册表测试**

```typescript
import { describe, it, expect, beforeEach } from "vitest";
import {
  PANEL_REGISTRY, getEnabledPanels, getAvailablePanels,
  isPanelEnabled, enablePanel, disablePanel, resetPanels,
} from "../../lib/panels";

describe("PanelRegistry", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("默认仅核心面板启用", () => {
    const panels = getEnabledPanels();
    const nonCoreEnabled = panels.filter((p) => p.category !== "core");
    expect(nonCoreEnabled).toEqual([]);
  });

  it("核心面板 chat、my-assistant、scheduled-tasks 默认启用", () => {
    const panels = getEnabledPanels();
    const ids = panels.map((p) => p.id);
    expect(ids).toContain("chat");
    expect(ids).toContain("my-assistant");
    expect(ids).toContain("scheduled-tasks");
  });

  it("enablePanel + disablePanel 工作正常", () => {
    expect(isPanelEnabled("kanban")).toBe(false);
    enablePanel("kanban");
    expect(isPanelEnabled("kanban")).toBe(true);
    disablePanel("kanban");
    expect(isPanelEnabled("kanban")).toBe(false);
  });

  it("核心面板列表在 PANEL_REGISTRY 中", () => {
    const all = getAvailablePanels();
    const core = all.filter((p) => p.category === "core");
    expect(core.length).toBe(3); // chat + my-assistant + scheduled-tasks
  });
});
```

- [ ] **Step 3: 运行现有测试确保无回归**

```bash
cd /Users/linhan/ai-factory/webui && npx vitest run
```

---

## 摘要

| 任务 | 文件 | 说明 |
|------|------|------|
| Task 1 | `webui/src/lib/slashCommands.ts` (新建) | 38 个 slash command 定义，与 Claude Code 一致 |
| Task 2 | `webui/src/components/ChatInput.tsx` (修改) | 集成 `/` 命令面板弹出层 |
| Task 2 | `webui/src/components/ChatPanel.tsx` (修改) | 添加 onSlashSend 适配 |
| Task 3 | `webui/src/lib/panels.ts` (新建) | Panel 注册表 + localStorage 持久化 |
| Task 3 | `webui/src/components/Layout.tsx` (修改) | 动态导航替换硬编码 |
| Task 3 | `webui/src/components/MyAssistant.tsx` (新建) | 我的助手占位组件 |
| Task 3 | `webui/src/components/ScheduledTasks.tsx` (新建) | 定时任务占位组件 |
| Task 3 | `webui/src/App.tsx` (修改) | 路由动态注册 + Suspense |
| Task 4 | `webui/src/components/settings/PanelsTab.tsx` (新建) | 高级功能管理 UI（核心/高级分组开关） |
| Task 4 | `webui/src/components/Settings.tsx` (修改) | 添加高级功能标签页 |
| Task 5 | Layout.tsx + PanelsTab.tsx | 事件通知机制 |
| Task 6 | `webui/src/lib/panels.ts` + `App.tsx` | 首次初始化策略 |
| Task 7 | `__tests__/` (新建 2 个) | 数据完整性 + 功能测试 |

**默认体验：**
- 新用户首次访问 → 侧栏三个核心项：**对话** + **我的助手** + **定时任务**
- 高级用户 → 设置 → 高级功能 → 一键开启"工作流"+"项目"+"总览"+"看板"等
- 技术用户 → 输入 `/` → 38 个 Claude Code 命令弹出 → 3 秒完成"这个不一样"的判断

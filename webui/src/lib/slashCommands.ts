import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Lightbulb, Settings, Sun,
  Brain, Shield, Search, Terminal, FileText, Wrench,
  Puzzle, Zap, HelpCircle, Trash2, DollarSign,
  Key, Bug, RotateCcw, BookOpen,
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
  type: "navigate" | "send" | "local";
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

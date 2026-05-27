import { lazy, type LazyExoticComponent, type ComponentType } from "react";
import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Lightbulb, Clock,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";

export interface PanelDefinition {
  id: string;
  label: string;
  icon: LucideIcon;
  route: string;
  section: "main" | "advanced";
  sortOrder: number;
  description: string;
  element: LazyExoticComponent<ComponentType<Record<string, never>>>;
}

const ChatPanel = lazy(() => import("../components/ChatPanel").then((m) => ({ default: m.ChatPanel })));
const Marketplace = lazy(() => import("../components/Marketplace").then((m) => ({ default: m.Marketplace })));
const ScheduledTasks = lazy(() => import("../components/ScheduledTasks").then((m) => ({ default: m.ScheduledTasks })));
const Dashboard = lazy(() => import("../components/Dashboard").then((m) => ({ default: m.Dashboard })));
const WorkshopList = lazy(() => import("../components/WorkshopList").then((m) => ({ default: m.WorkshopList })));
const WorkflowList = lazy(() => import("../components/WorkflowList").then((m) => ({ default: m.WorkflowList })));
const ModuleFactory = lazy(() => import("../components/ModuleFactory").then((m) => ({ default: m.ModuleFactory })));
const KanbanBoard = lazy(() => import("../components/KanbanBoard").then((m) => ({ default: m.KanbanBoard })));

export const PANEL_REGISTRY: Record<string, PanelDefinition> = {
  chat: {
    id: "chat",
    label: "对话",
    icon: MessageSquare,
    route: "/chat",
    section: "main",
    sortOrder: 1,
    description: "Agent 对话窗口，输入 / 查看命令",
    element: ChatPanel,
  },
  market: {
    id: "market",
    label: "方案市场",
    icon: Lightbulb,
    route: "/market",
    section: "main",
    sortOrder: 3,
    description: "发现和安装社区共享的方案包",
    element: Marketplace,
  },
  "scheduled-tasks": {
    id: "scheduled-tasks",
    label: "定时任务",
    icon: Clock,
    route: "/scheduled-tasks",
    section: "main",
    sortOrder: 4,
    description: "安排 AI 定时帮你做事",
    element: ScheduledTasks,
  },
  workflows: {
    id: "workflows",
    label: "工作流",
    icon: GitBranch,
    route: "/workflows",
    section: "advanced",
    sortOrder: 1,
    description: "DAG 工作流画布，拖拽编排多 Agent 协作流程",
    element: WorkflowList,
  },
  factory: {
    id: "factory",
    label: "模版仓库",
    icon: Package,
    route: "/factory",
    section: "advanced",
    sortOrder: 2,
    description: "导入/导出工作流模板和 Agent 配置",
    element: ModuleFactory,
  },
  kanban: {
    id: "kanban",
    label: "看板",
    icon: Kanban,
    route: "/kanban",
    section: "advanced",
    sortOrder: 4,
    description: "项目看板，拖拽管理任务，WebSocket 实时同步",
    element: KanbanBoard,
  },
  dashboard: {
    id: "dashboard",
    label: "总览",
    icon: Activity,
    route: "/dashboard",
    section: "advanced",
    sortOrder: 5,
    description: "运营仪表盘：token 消耗、Agent 执行成功率",
    element: Dashboard,
  },
  workshops: {
    id: "workshops",
    label: "项目",
    icon: Blocks,
    route: "/workshops",
    section: "advanced",
    sortOrder: 6,
    description: "管理多个工作区，独立 Agent、记忆和上下文",
    element: WorkshopList,
  },
};

export function getMainPanels(): PanelDefinition[] {
  return Object.values(PANEL_REGISTRY)
    .filter((p) => p.section === "main")
    .sort((a, b) => a.sortOrder - b.sortOrder);
}

export function getAdvancedPanels(): PanelDefinition[] {
  return Object.values(PANEL_REGISTRY)
    .filter((p) => p.section === "advanced")
    .sort((a, b) => a.sortOrder - b.sortOrder);
}

export function getAllPanels(): PanelDefinition[] {
  return [...getMainPanels(), ...getAdvancedPanels()];
}

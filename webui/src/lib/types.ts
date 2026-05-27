export interface Workshop {
  name: string;
  workspace: string;
  agent_count: number;
  agent_names: string[];
  workflow_name: string;
  has_kanban: boolean;
  kanban_board_id?: string;
  agents?: Record<string, { type: string; model: string; tools: string[] }>;
  kanban_stats?: Record<string, number>;
}

export interface KanbanBoard {
  id: string;
  name: string;
  workshop_name: string;
  description: string;
  lists?: KanbanList[];
}

export interface KanbanList {
  id: string;
  board_id: string;
  name: string;
  position: number;
  cards?: KanbanCard[];
}

export interface KanbanCard {
  id: string;
  list_id: string;
  title: string;
  description: string;
  position: number;
  labels: string[];
  task_status: "todo" | "in_progress" | "done" | "blocked";
  source_agent: string;
  source_task_id: string;
  /** Parsed execution metadata from description */
  output_summary?: string;
  turns?: number;
  cost_usd?: number;
  tools_used?: string[];
  model?: string;
  /** Whether this is an agent-generated card (has source_agent) */
  is_agent: boolean;
}

export interface WorkflowTemplate {
  name: string;
  description: string;
  workspace: string;
  nodes: WorkflowNode[];
}

export interface WorkflowNode {
  id: string;
  label: string;
  node_type: "agent" | "condition" | "transform";
  agent_name: string;
  prompt: string;
  depends_on: string[];
  expected_output: string;
  gate?: { type: string };
  timeout_seconds: number;
  notes: string;
  retry_on_fail: boolean;
  continue_on_fail: boolean;
}

export interface WorkflowInfo {
  name: string;
  description: string;
  workspace: string;
  node_count: number;
}

export interface WorkflowResult {
  status: string;
  template_name: string;
  stage_results: Record<string, { stage_id: string; agent_name: string; status: string; output: string }>;
  final_output: string;
}

export interface OrgStatus {
  departments: Workshop[];
  total_agents: number;
}

export interface WSMessage {
  event: string;
  data: unknown;
}

// ── Settings ──

export interface ProviderConfig {
  name: string;
  provider_type: string;
  base_url: string;
  api_key: string;
  models: string[];
}

export interface SearchConfig {
  tavily_api_key: string;
  brave_api_key: string;
  searxng_base_url: string;
  active_provider: string;
  deep_search_enabled: boolean;
  max_results: number;
}

export interface SkillEntry {
  name: string;
  full_name: string;
  description: string;
  plugin: string;
  source: string;
  file_path?: string;
}

export interface SkillDetail extends SkillEntry {
  body: string;
}

export interface ToolConfig {
  name?: string;
  [key: string]: unknown;
}

export interface FileTreeNode {
  name: string;
  type: "file" | "directory";
  path: string;
  children?: FileTreeNode[];
}

export interface SessionSummary {
  id: string;
  first_message: string;
  created_at: string;
  timestamp: number;
}

export interface PluginEntry {
  name: string;
  enabled: boolean;
  healthy: boolean | null;
  source?: string;
  description?: string;
  category?: string;
  transport?: string;
  homepage?: string;
}

// ── Agent ──

export interface AgentInfo {
  name: string;
  mode: "super" | "normal";
  model: string;
  tools: string[];
  tools_all: boolean;
  system_prompt: string;
  guide_file: string;
  skills: string[];
  permissions: {
    file_write: boolean;
    shell_exec: boolean;
    subagent_spawn: boolean;
  };
  is_super: boolean;
}

// ── Chain ──


// ── Marketplace ──

export interface MarketPackage {
  id: string;
  name: string;
  description: string;
  long_description: string;
  category: string;
  tags: string[];
  author: string;
  version: string;
  icon_url: string;
  screenshots: string[];
  plan_monthly_price: number;
  plan_yearly_price: number;
  package_size: number;
  download_count: number;
  created_at: string;
  updated_at: string;
}

export interface MarketSubscription {
  package_id: string;
  plan_type: string;
  expires_at: string;
  created_at: string;
  name: string;
  category: string;
  version: string;
}

export interface UserInfo {
  user_id: string;
  username: string;
  is_vip: boolean;
}

// ── Scheduled Tasks ──

export interface ScheduleTask {
  id: string;
  name: string;
  prompt: string;
  workshop: string;
  frequency: "daily" | "workday" | "weekly" | "monthly";
  time_str: string;
  weekday: number | null;
  monthday: number | null;
  timezone: string;
  cron_expr: string;
  enabled: boolean;
  model: string;
  is_running: boolean;
  last_run_at: string | null;
  last_status: "success" | "failed" | "timeout" | null;
  last_output: string | null;
  next_run_at: string | null;
  run_history: Array<{
    time: string;
    status: string;
    duration: number;
    output_summary: string;
  }>;
  consecutive_failures: number;
  run_count: number;
  created_at: string;
}

export interface ScheduleTemplate {
  name: string;
  icon: string;
  description: string;
  preview: string;
  category: string;
  default_frequency: string;
  default_time: string;
}

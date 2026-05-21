export interface Workshop {
  name: string;
  workspace: string;
  agent_count: number;
  super_agents: string[];
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
}

export interface WorkflowTemplate {
  name: string;
  description: string;
  source: string;
  stages?: WorkflowStage[];
}

export interface WorkflowStage {
  id: string;
  agent: string;
  action: string;
  output: string;
  depends_on?: string[];
  gate?: { type: string; pass: string; fail: string };
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
  super_agents: number;
}

export interface WSMessage {
  event: string;
  data: unknown;
}

import type { KanbanBoard, KanbanCard, KanbanList, OrgStatus, WorkflowResult, WorkflowTemplate, Workshop } from "./types";

const BASE = "/api";

async function get<T>(url: string): Promise<T> {
  const res = await fetch(`${BASE}${url}`);
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

async function post<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

async function del(url: string): Promise<void> {
  const res = await fetch(`${BASE}${url}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}

async function put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

// ── API ──

export const api = {
  // Health
  health: () => get<{ status: string; version: string }>("/health"),

  // Org
  orgStatus: () => get<OrgStatus>("/org/status"),

  // Workshops
  listWorkshops: () => get<Workshop[]>("/workshops"),
  getWorkshop: (name: string) => get<Workshop>(`/workshops/${name}`),
  createWorkshop: (name: string, workflow?: string) =>
    post<Workshop>("/workshops", { name, workflow_name: workflow || "simple" }),
  deleteWorkshop: (name: string) => del(`/workshops/${name}`),
  runWorkflow: (name: string, workflow: string, task: string) =>
    post<WorkflowResult>(`/workshops/${name}/run`, { workflow, task }),
  listProducts: (name: string) =>
    get<{ workshop: string; products: string[] }>(`/workshops/${name}/products`),

  // Workflows
  listWorkflows: () => get<WorkflowTemplate[]>("/workflows"),
  getWorkflow: (name: string) => get<WorkflowTemplate>(`/workflows/${name}`),

  // Kanban
  listBoards: () => get<KanbanBoard[]>("/boards"),
  getBoard: (id: string) => get<KanbanBoard & { lists: KanbanList[] }>(`/boards/${id}`),
  createBoard: (name: string, workshop: string) =>
    post<KanbanBoard>("/boards", { name, workshop_name: workshop }),
  deleteBoard: (id: string) => del(`/boards/${id}`),
  getLists: (boardId: string) => get<KanbanList[]>(`/boards/${boardId}/lists`),
  createList: (boardId: string, name: string) =>
    post<KanbanList>(`/boards/${boardId}/lists`, { name }),
  getCards: (listId: string) => get<KanbanCard[]>(`/lists/${listId}/cards`),
  createCard: (listId: string, title: string) =>
    post<KanbanCard>(`/lists/${listId}/cards`, { title }),
  moveCard: (cardId: string, listId: string) =>
    put<KanbanCard>(`/cards/${cardId}/move`, { list_id: listId }),
  updateCard: (cardId: string, data: Partial<KanbanCard>) =>
    put<KanbanCard>(`/cards/${cardId}`, data),
  deleteCard: (cardId: string) => del(`/cards/${cardId}`),

  // ── Settings ──

  // Providers (LLM Keys)
  listProviders: () => get<Record<string, { provider_type: string; base_url: string; api_key: string }>>("/settings/providers"),
  saveProvider: (name: string, data: { provider_type?: string; base_url?: string; api_key?: string }) =>
    post(`/settings/providers`, { name, ...data }),
  deleteProvider: (name: string) => del(`/settings/providers/${name}`),

  // Skills
  listSkills: () => get<{ name: string; description: string; version: string }[]>("/settings/skills"),
  syncSkills: () => post<{ status: string; count: number }>("/settings/skills/sync", {}),

  // Tools (MCP + profiles)
  listTools: () => get<{ mcp_servers: unknown[]; profiles: Record<string, unknown> }>("/settings/tools"),
  saveTool: (name: string, data: Record<string, unknown>) => post("/settings/tools", { name, ...data }),
  syncTools: () => post<{ status: string; count: number }>("/settings/tools/sync", {}),

  // Plugins
  listPlugins: () => get<Record<string, { name: string; enabled: boolean; healthy: boolean }>>("/settings/plugins"),
  savePlugin: (name: string, data: { enabled?: boolean }) => post("/settings/plugins", { name, ...data }),
  deletePlugin: (name: string) => del(`/settings/plugins/${name}`),
};

// ── WebSocket ──

export function connectWS(boardId: string, onMessage: (event: string, data: unknown) => void): () => void {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws/boards/${boardId}`);

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      onMessage(msg.event, msg.data);
    } catch { /* ignore */ }
  };

  ws.onclose = () => { /* reconnect handled by caller */ };

  return () => ws.close();
}

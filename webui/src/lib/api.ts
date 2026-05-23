import type { KanbanBoard, KanbanCard, KanbanList, MarketPackage, MarketSubscription, OrgStatus, SearchConfig, SkillDetail, UserInfo, WorkflowInfo, WorkflowResult, WorkflowTemplate, Workshop } from "./types";

const BASE = "/api";

let _csrfToken: string | null = null;
let _authToken: string | null = null;
let _apiKey: string | null = null;

export function setAuthToken(token: string | null): void {
  _authToken = token;
}

export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (_csrfToken) headers["X-CSRF-Token"] = _csrfToken;
  if (_authToken) headers["Authorization"] = `Bearer ${_authToken}`;
  if (_apiKey) headers["X-API-Key"] = _apiKey;
  return headers;
}

function defaultHeaders(authToken?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (_apiKey) headers["X-API-Key"] = _apiKey;
  const token = authToken || _authToken;
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return headers;
}

function csrfHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};
  if (_csrfToken) headers["X-CSRF-Token"] = _csrfToken;
  return headers;
}

export async function fetchCsrfToken(): Promise<void> {
  const res = await fetch(`${BASE}/csrf-token`, { credentials: "include" });
  if (res.ok) {
    const data = await res.json();
    _csrfToken = data.token;
  }
}

async function fetchApiKey(): Promise<void> {
  try {
    const res = await fetch(`${BASE}/auth/api-key`, { credentials: "include" });
    if (res.ok) {
      const data = await res.json();
      _apiKey = data.api_key;
    }
  } catch { /* gateway may not be running yet */ }
}

/** Initialize auth — call once on app startup. */
export async function initApi(): Promise<void> {
  await Promise.all([fetchCsrfToken(), fetchApiKey()]);
}

async function get<T>(url: string, authToken?: string): Promise<T> {
  const headers: Record<string, string> = { ...defaultHeaders(authToken) };
  const res = await fetch(`${BASE}${url}`, { headers, credentials: "include" });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

async function post<T>(url: string, body: unknown, authToken?: string): Promise<T> {
  const headers: Record<string, string> = { "Content-Type": "application/json", ...csrfHeaders(), ...defaultHeaders(authToken) };
  const res = await fetch(`${BASE}${url}`, {
    method: "POST",
    headers,
    credentials: "include",
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
  return res.json();
}

async function del(url: string): Promise<void> {
  const res = await fetch(`${BASE}${url}`, {
    method: "DELETE",
    headers: { ...csrfHeaders(), ...defaultHeaders() },
    credentials: "include",
  });
  if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
}

async function put<T>(url: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${url}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json", ...csrfHeaders(), ...defaultHeaders() },
    credentials: "include",
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
  createWorkshop: (name: string, workflow?: string, model?: string) =>
    post<Workshop>("/workshops", { name, workflow_name: workflow || "simple", model: model || "" }),
  deleteWorkshop: (name: string) => del(`/workshops/${name}`),
  runWorkflow: (name: string, workflow: string, task: string) =>
    post<WorkflowResult>(`/workshops/${name}/run`, { workflow, task }),
  listProducts: (name: string) =>
    get<{ workshop: string; products: string[] }>(`/workshops/${name}/products`),

  // Workflows
  listWorkflows: () => get<WorkflowInfo[]>("/workflows"),
  getWorkflow: (name: string) => get<WorkflowTemplate>(`/workflows/${name}`),
  saveWorkflow: (data: WorkflowTemplate) => post<WorkflowTemplate>("/workflows", data),
  deleteWorkflow: (name: string) => del(`/workflows/${name}`),

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
  listProviders: () => get<Record<string, { provider_type: string; base_url: string; api_key: string; models: string[] }>>("/settings/providers"),
  saveProvider: (name: string, data: { provider_type?: string; base_url?: string; api_key?: string; models?: string[] }) =>
    post(`/settings/providers`, { name, ...data }),
  deleteProvider: (name: string) => del(`/settings/providers/${name}`),
  syncProviderModels: (name: string) => post<{ name: string; models: string[]; updated: number; error: string | null }>(`/settings/providers/${name}/sync-models`, {}),

  // Preferences
  getPreferences: () => get<Record<string, unknown>>("/settings/preferences"),
  savePreferences: (data: Record<string, unknown>) => post<Record<string, unknown>>("/settings/preferences", data),

  // Search
  getSearchConfig: () => get<SearchConfig>("/settings/search"),
  saveSearchConfig: (data: Partial<SearchConfig>) => post("/settings/search", data),

  // Skills
  listSkills: () => get<import("./types").SkillEntry[]>("/settings/skills"),
  syncSkills: () => post<{ status: string; count: number; skills: import("./types").SkillEntry[] }>("/settings/skills/sync", {}),
  getSkillDetail: (name: string) => get<SkillDetail>(`/settings/skills/${name}`),

  // Tools (MCP + profiles)
  listTools: () => get<{ name: string; description: string; category: string; install_command?: string }[]>("/settings/tools"),
  saveTool: (name: string, data: Record<string, unknown>) => post("/settings/tools", { name, ...data }),
  syncTools: () => post<{ status: string; count: number }>("/settings/tools/sync", {}),

  // Plugins
  listPlugins: () => get<Record<string, { name: string; enabled: boolean; healthy: boolean }>>("/settings/plugins"),
  savePlugin: (name: string, data: { enabled?: boolean }) => post("/settings/plugins", { name, ...data }),
  deletePlugin: (name: string) => del(`/settings/plugins/${name}`),

  // Agents
  listAgents: (workshop: string) => get<import("./types").AgentInfo[]>(`/workshops/${workshop}/agents`),
  createAgent: (workshop: string, data: Record<string, unknown>) =>
    post<import("./types").AgentInfo>(`/workshops/${workshop}/agents`, data),
  updateAgent: (workshop: string, name: string, data: Record<string, unknown>) =>
    put<import("./types").AgentInfo>(`/workshops/${workshop}/agents/${name}`, data),
  deleteAgent: (workshop: string, name: string) => del(`/workshops/${workshop}/agents/${name}`),


  // ── Marketplace ──
  marketCatalog: (category?: string) =>
    get<MarketPackage[]>(`/market/catalog?category=${encodeURIComponent(category || "")}`),
  marketPackage: (id: string) =>
    get<MarketPackage>(`/market/packages/${id}`),
  marketInstall: (id: string, token: string) =>
    post<Record<string, unknown>>(`/market/packages/${id}/install`, {}, token),
  marketMy: (token: string) =>
    get<MarketSubscription[]>("/market/my", token),
  marketLogin: (username: string, password: string) =>
    post<{ token: string; user: UserInfo }>("/market/auth/login", { username, password }),
  marketRegister: (username: string, password: string) =>
    post<{ token: string; user: UserInfo }>("/market/auth/register", { username, password }),
};

// ── WebSocket ──

export function connectWS(
  boardId: string,
  onMessage: (event: string, data: unknown) => void,
  onClose?: () => void,
): () => void {
  const protocol = location.protocol === "https:" ? "wss:" : "ws:";
  const ws = new WebSocket(`${protocol}//${location.host}/ws/boards/${boardId}`);

  ws.onmessage = (e) => {
    try {
      const msg = JSON.parse(e.data);
      onMessage(msg.event, msg.data);
    } catch { /* ignore malformed messages */ }
  };

  ws.onclose = () => onClose?.();

  return () => {
    ws.onclose = null;
    ws.close();
  };
}

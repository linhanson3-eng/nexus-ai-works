import { useEffect, useState, useCallback } from "react";
import { AlertTriangle, Plus, Trash2, Play, Loader2, Blocks, RefreshCw, Bot, Settings, X, Shield, FileText, Wrench, Zap } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { Workshop, WorkflowResult, AgentInfo } from "../lib/types";

const AVAILABLE_TOOLS = [
  "think", "search", "deep_search", "read_file", "write_file",
  "execute_command", "task", "web_fetch", "ask_user_question",
];

export function WorkshopList() {
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [model, setModel] = useState("anthropic/claude-sonnet-4-6");
  const [providerModels, setProviderModels] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Workshop | null>(null);
  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  // Agent management
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [agentsLoading, setAgentsLoading] = useState(false);
  const [showAgentEditor, setShowAgentEditor] = useState(false);
  const [editingAgent, setEditingAgent] = useState<AgentInfo | null>(null);
  const [agentForm, setAgentForm] = useState({
    name: "", mode: "super" as "super" | "normal",
    model: "anthropic/claude-sonnet-4-6",
    system_prompt: "", guide_file: "", guide_content: "", skills: "",
    tools: "" as string | string[],
    file_write: true, shell_exec: true, subagent_spawn: true,
  });
  const [agentSaving, setAgentSaving] = useState(false);
  const [availableSkills, setAvailableSkills] = useState<{ name: string; description: string }[]>([]);
  const [skillsDropdownOpen, setSkillsDropdownOpen] = useState(false);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listWorkshops();
      setWorkshops(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Load provider models for dropdown
  useEffect(() => {
    api.listProviders().then(providers => {
      const models: string[] = [];
      for (const [pname, cfg] of Object.entries(providers)) {
        for (const m of cfg.models || []) {
          models.push(`${pname}/${m}`);
        }
      }
      setProviderModels(models);
    }).catch(() => {});
  }, []);

  // Load available skills for dropdown
  useEffect(() => {
    api.listSkills().then(data => {
      setAvailableSkills(data.map((s: { name: string; description: string }) => ({ name: s.name, description: s.description || "" })));
    }).catch(() => {});
  }, []);

  // Close skills dropdown on outside click
  useEffect(() => {
    if (!skillsDropdownOpen) return;
    const handler = () => setSkillsDropdownOpen(false);
    document.addEventListener("click", handler);
    return () => document.removeEventListener("click", handler);
  }, [skillsDropdownOpen]);

  const create = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      await api.createWorkshop(trimmed, undefined, model);
      setName("");
      setShowCreate(false);
      toast.success(`工作区 "${trimmed}" 已创建`);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const remove = async (wsName: string) => {
    try {
      await api.deleteWorkshop(wsName);
      toast.success(`工作区 "${wsName}" 已删除`);
      if (selected?.name === wsName) setSelected(null);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleteTarget(null);
    }
  };

  const run = async () => {
    if (!selected || !task.trim()) return;
    setRunning(true);
    setResult(null);
    try {
      const r = await api.runWorkflow(selected.name, selected.workflow_name, task.trim());
      setResult(r);
      toast.success(`工作流 ${r.status === "completed" ? "执行完成" : r.status}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "执行失败");
    } finally {
      setRunning(false);
      setTask("");
    }
  };

  // ── Agent CRUD ────────────────────────────────────────────────

  const loadAgents = async (wsName: string) => {
    setAgentsLoading(true);
    try {
      setAgents(await api.listAgents(wsName));
    } catch {
      setAgents([]);
    } finally {
      setAgentsLoading(false);
    }
  };

  const openAgentCreate = () => {
    setEditingAgent(null);
    setAgentForm({
      name: "", mode: "super", model: "anthropic/claude-sonnet-4-6",
      system_prompt: "", guide_file: "GUIDE.md", guide_content: "", skills: "",
      tools: "", file_write: true, shell_exec: true, subagent_spawn: true,
    });
    setShowAgentEditor(true);
  };

  const openAgentEdit = async (a: AgentInfo) => {
    setEditingAgent(a);
    // Try to load guide file content
    let guideContent = "";
    if (a.guide_file && selected) {
      try {
        const res = await fetch(`/api/workshops/${selected.name}/files/${a.guide_file}`);
        if (res.ok) {
          const data = await res.json();
          guideContent = data.content || "";
        }
      } catch { /* file may not exist yet */ }
    }
    setAgentForm({
      name: a.name,
      mode: a.mode || (a.is_super ? "super" : "normal"),
      model: a.model,
      system_prompt: a.system_prompt || "",
      guide_file: a.guide_file || "",
      guide_content: guideContent,
      skills: (a.skills || []).join(", "),
      tools: a.tools_all ? "" : (a.tools || []).join(", "),
      file_write: a.permissions?.file_write ?? false,
      shell_exec: a.permissions?.shell_exec ?? false,
      subagent_spawn: a.permissions?.subagent_spawn ?? false,
    });
    setShowAgentEditor(true);
  };

  const saveAgent = async () => {
    if (!selected || !agentForm.name.trim()) return;
    setAgentSaving(true);

    const mode = agentForm.mode;
    const isSuper = mode === "super";
    const toolsStr = typeof agentForm.tools === "string" ? agentForm.tools : agentForm.tools.join(", ");

    const tools: string[] = isSuper
      ? []
      : (toolsStr ? toolsStr.split(",").map(t => t.trim()).filter(Boolean) : ["think", "search", "read_file"]);

    const payload: Record<string, unknown> = {
      name: agentForm.name.trim(),
      mode,
      model: agentForm.model,
      tools,
      system_prompt: agentForm.system_prompt,
      guide_file: agentForm.guide_file,
      guide_content: agentForm.guide_content,
      skills: agentForm.skills ? agentForm.skills.split(",").map(s => s.trim()).filter(Boolean) : [],
      permissions: {
        file_write: agentForm.file_write,
        shell_exec: agentForm.shell_exec,
        subagent_spawn: agentForm.subagent_spawn,
      },
    };

    try {
      if (editingAgent) {
        await api.updateAgent(selected.name, editingAgent.name, payload);
        toast.success(`Agent "${payload.name}" 已更新`);
      } else {
        await api.createAgent(selected.name, payload);
        toast.success(`Agent "${payload.name}" 已创建`);
      }
      setShowAgentEditor(false);
      loadAgents(selected.name);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setAgentSaving(false);
    }
  };

  const deleteAgent = async (agentName: string) => {
    if (!selected) return;
    try {
      await api.deleteAgent(selected.name, agentName);
      toast.success(`Agent "${agentName}" 已删除`);
      loadAgents(selected.name);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <div className="h-8 w-24 bg-card rounded animate-pulse" />
            <div className="h-4 w-48 bg-card rounded animate-pulse mt-2" />
          </div>
        </div>
        {[1, 2, 3].map(i => (
          <div key={i} className="bg-card border border-border rounded-[20px] p-5 animate-pulse h-20" />
        ))}
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl font-black tracking-tight text-white">工作区</h1></div>
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <AlertTriangle className="w-10 h-10 text-warning" />
          <p className="text-white font-semibold">加载失败</p>
          <p className="text-sm text-muted">{error}</p>
          <button onClick={load} className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      </div>
    );
  }

  // ── Content ──
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">工作区</h1>
          <p className="text-muted text-sm mt-1">管理所有 AI 工作区</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors"
        >
          <Plus className="w-4 h-4" /> 新建工作区
        </button>
      </div>

      {showCreate && (
        <div className="bg-card border border-border rounded-[20px] p-5 flex flex-col gap-3 sm:flex-row">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !creating && create()}
            placeholder="工作区名称"
            className="flex-1 bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
            autoFocus
          />
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            className="bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white focus:outline-none focus:border-accent/30 min-w-[240px]"
          >
            <option value="">默认模型</option>
            {providerModels.map(m => (
              <option key={m} value={m}>{m}</option>
            ))}
            <option value="__custom__">自定义输入...</option>
          </select>
          {model === "__custom__" && (
            <input
              value=""
              onChange={e => setModel(e.target.value)}
              placeholder="输入模型名..."
              className="flex-1 bg-surface border border-accent/30 rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/50"
              autoFocus
            />
          )}
          <button
            onClick={create}
            disabled={creating || !name.trim()}
            className="px-5 py-2 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-30 flex items-center gap-2 shrink-0"
          >
            {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            创建
          </button>
        </div>
      )}

      {/* Empty state */}
      {!loading && workshops.length === 0 && (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
            <Blocks className="w-7 h-7 text-muted" />
          </div>
          <div className="text-center">
            <p className="text-white font-semibold">暂无工作区</p>
            <p className="text-sm text-muted mt-1">点击上方「新建工作区」开始</p>
          </div>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {workshops.map(w => (
          <div
            key={w.name}
            onClick={() => {
              const next = selected?.name === w.name ? null : w;
              setSelected(next);
              if (next) loadAgents(next.name);
            }}
            className={`bg-card border rounded-[20px] p-5 cursor-pointer transition-all duration-200 hover:bg-card-hover ${
              selected?.name === w.name ? "border-accent/40 ring-1 ring-accent/20" : "border-border"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${w.workflow_name !== "simple" ? "bg-info" : "bg-muted"} ${w.has_kanban ? "shadow-[0_0_6px_rgba(6,182,212,0.4)]" : ""}`} />
                <span className="font-semibold text-white">{w.name}</span>
                <span className="text-[11px] text-muted bg-surface px-2 py-0.5 rounded-md">{w.workflow_name}</span>
              </div>
              <div className="flex items-center gap-4">
                <span className="text-sm text-muted">{w.agent_count} agents</span>
                <button
                  onClick={e => { e.stopPropagation(); setDeleteTarget(w.name); }}
                  className="text-muted hover:text-warning transition-colors"
                  title="删除工作区"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Expanded detail */}
            {selected?.name === w.name && (
              <div className="mt-5 pt-5 border-t border-border space-y-4">
                {/* Agents */}
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-[10px] uppercase tracking-widest text-muted font-medium">Agents</span>
                    <button onClick={(e) => { e.stopPropagation(); openAgentCreate(); }}
                      className="flex items-center gap-1 text-xs text-accent hover:text-white transition-colors">
                      <Plus className="w-3 h-3" /> 添加 Agent
                    </button>
                  </div>
                  {agentsLoading ? (
                    <div className="mt-2 h-10 bg-surface rounded-xl animate-pulse" />
                  ) : agents.length === 0 ? (
                    <p className="text-xs text-muted mt-2">暂无 Agent，点击「添加 Agent」创建</p>
                  ) : (
                    <div className="mt-2 space-y-1.5">
                      {agents.map(a => (
                        <div key={a.name} className="flex items-center justify-between p-2.5 bg-surface border border-border rounded-xl group">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${a.is_super ? "bg-warning/10" : "bg-info/10"}`}>
                              {a.is_super ? <Zap className="w-3 h-3 text-warning" /> : <Bot className="w-3 h-3 text-info" />}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-white font-medium">{a.name}</span>
                                <span className={`text-[9px] px-1.5 py-0.5 rounded font-medium ${
                                  a.is_super ? "bg-warning/10 text-warning" : "bg-info/10 text-info"
                                }`}>{a.is_super ? "超级" : "普通"}</span>
                              </div>
                              <div className="flex items-center gap-2 text-[10px] text-muted mt-0.5">
                                <span>{a.model}</span>
                                <span>·</span>
                                <span>{a.tools_all ? "全工具" : `${a.tools.length} 工具`}</span>
                                {a.permissions?.subagent_spawn && <span className="text-warning">· 可建子Agent</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                            <button onClick={(e) => { e.stopPropagation(); openAgentEdit(a); }}
                              className="p-1.5 rounded-lg text-muted hover:text-white hover:bg-white/5 transition-colors">
                              <Settings className="w-3 h-3" />
                            </button>
                            <button onClick={(e) => { e.stopPropagation(); deleteAgent(a.name); }}
                              className="p-1.5 rounded-lg text-muted/30 hover:text-warning transition-colors">
                              <Trash2 className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {w.kanban_stats && (
                  <div>
                    <span className="text-[10px] uppercase tracking-widest text-muted font-medium">看板</span>
                    <div className="mt-2 flex gap-4">
                      {Object.entries(w.kanban_stats).map(([sname, count]) => (
                        <div key={sname} className="text-center">
                          <div className="text-xl font-bold text-white">{count}</div>
                          <div className="text-[10px] text-muted">{sname}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Task runner */}
                <div>
                  <span className="text-[10px] uppercase tracking-widest text-muted font-medium">执行工作流</span>
                  <div className="mt-2 flex gap-3">
                    <input
                      value={task}
                      onChange={e => setTask(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && !running && task.trim() && run()}
                      placeholder="输入任务描述..."
                      disabled={running}
                      className="flex-1 bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 disabled:opacity-50"
                    />
                    <button
                      onClick={run}
                      disabled={running || !task.trim()}
                      className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors disabled:opacity-30"
                    >
                      {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      执行
                    </button>
                  </div>
                </div>

                {result && (
                  <div className="bg-surface border border-border rounded-xl p-4 font-mono text-xs text-terminal overflow-auto max-h-64">
                    <div className="text-accent mb-2">[{result.status}] {result.template_name}</div>
                    {Object.values(result.stage_results).map((sr: unknown) => {
                      const s = sr as { stage_id: string; status: string; output: string };
                      return (
                        <div key={s.stage_id} className="ml-2 mb-1">
                          <span className="text-info">[{s.status}]</span> {s.stage_id}: {s.output?.slice(0, 200)}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}
          </div>
        ))}
      </div>

      {/* Agent Editor Dialog */}
      {showAgentEditor && selected && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowAgentEditor(false)}>
          <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-lg space-y-4 shadow-2xl max-h-[85vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">{editingAgent ? `编辑 Agent: ${editingAgent.name}` : "新建 Agent"}</h2>
              <button onClick={() => setShowAgentEditor(false)} className="p-1.5 rounded-lg text-muted hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            {/* Name */}
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">名称</label>
              <input value={agentForm.name} onChange={e => setAgentForm(f => ({ ...f, name: e.target.value }))}
                placeholder="Agent 名称"
                disabled={!!editingAgent}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1 disabled:opacity-50" />
            </div>

            {/* Mode + Model */}
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted">模式</label>
                <div className="flex gap-2 mt-1">
                  <button type="button" onClick={() => setAgentForm(f => ({
                    ...f, mode: "super",
                    tools: "", file_write: true, shell_exec: true, subagent_spawn: true,
                  }))}
                    className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-colors ${
                      agentForm.mode === "super"
                        ? "bg-warning/10 text-warning border-warning/30"
                        : "bg-surface border-border text-muted hover:text-white"
                    }`}>
                    <Zap className="w-3.5 h-3.5" /> 超级
                  </button>
                  <button type="button" onClick={() => setAgentForm(f => ({
                    ...f, mode: "normal",
                    tools: "think, search, read_file", file_write: false, shell_exec: false, subagent_spawn: false,
                  }))}
                    className={`flex-1 flex items-center justify-center gap-1.5 px-3 py-2 rounded-xl text-xs font-medium border transition-colors ${
                      agentForm.mode === "normal"
                        ? "bg-info/10 text-info border-info/30"
                        : "bg-surface border-border text-muted hover:text-white"
                    }`}>
                    <Bot className="w-3.5 h-3.5" /> 普通
                  </button>
                </div>
              </div>
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted">模型</label>
                <select value={agentForm.model} onChange={e => setAgentForm(f => ({ ...f, model: e.target.value }))}
                  className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 mt-1">
                  {providerModels.map(m => (
                    <option key={m} value={m}>{m}</option>
                  ))}
                  <option value="__custom__">自定义输入...</option>
                </select>
                {agentForm.model === "__custom__" && (
                  <input value="" onChange={e => setAgentForm(f => ({ ...f, model: e.target.value }))}
                    placeholder="输入模型名，如 anthropic/claude-opus-4-7"
                    autoFocus
                    className="w-full bg-surface border border-accent/30 rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/50 mt-1" />
                )}
              </div>
            </div>

            {/* System prompt */}
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted flex items-center gap-1.5">
                <FileText className="w-3 h-3" /> 系统提示词
              </label>
              <textarea value={agentForm.system_prompt} onChange={e => setAgentForm(f => ({ ...f, system_prompt: e.target.value }))}
                placeholder="Agent 的系统级指令..."
                rows={3}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1 resize-none" />
            </div>

            {/* Tools — only for normal mode */}
            {agentForm.mode === "normal" && (
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted flex items-center gap-1.5">
                  <Wrench className="w-3 h-3" /> 工具
                </label>
                <input value={typeof agentForm.tools === "string" ? agentForm.tools : agentForm.tools.join(", ")}
                  onChange={e => setAgentForm(f => ({ ...f, tools: e.target.value }))}
                  placeholder="think, search, read_file, write_file..."
                  className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
                <div className="flex flex-wrap gap-1 mt-1.5">
                  {AVAILABLE_TOOLS.map(t => (
                    <button key={t} type="button"
                      onClick={() => {
                        const current = typeof agentForm.tools === "string" ? agentForm.tools.split(",").map(s => s.trim()).filter(Boolean) : agentForm.tools;
                        const next = current.includes(t) ? current.filter(x => x !== t) : [...current, t];
                        setAgentForm(f => ({ ...f, tools: next.join(", ") }));
                      }}
                      className={`text-[10px] px-2 py-0.5 rounded-md border transition-colors ${
                        (typeof agentForm.tools === "string" ? agentForm.tools : agentForm.tools.join(",")).includes(t)
                          ? "bg-accent/10 text-accent border-accent/30"
                          : "bg-surface border-border text-muted hover:text-white"
                      }`}>{t}</button>
                  ))}
                </div>
              </div>
            )}

            {/* Guide file */}
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted flex items-center gap-1.5">
                <FileText className="w-3 h-3" /> 引导文件
              </label>
              <div className="flex gap-2 mt-1">
                <input value={agentForm.guide_file} onChange={e => setAgentForm(f => ({ ...f, guide_file: e.target.value }))}
                  placeholder="GUIDE.md"
                  className="w-36 bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30" />
                <span className="text-[10px] text-muted self-center">.md Markdown 文件</span>
              </div>
              <textarea value={agentForm.guide_content} onChange={e => setAgentForm(f => ({ ...f, guide_content: e.target.value }))}
                placeholder="# Agent 引导指令&#10;&#10;## 角色&#10;你是一个...&#10;&#10;## 工作流程&#10;1. ...&#10;2. ...&#10;&#10;## 规则&#10;- ..."
                rows={8}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-2 resize-none font-mono" />
            </div>

            {/* Skills */}
            <div className="relative">
              <label className="text-[10px] uppercase tracking-widest text-muted flex items-center gap-1.5">
                <Zap className="w-3 h-3" /> 技能
              </label>
              <div className="flex flex-wrap gap-1 mt-1 mb-1.5">
                {agentForm.skills ? agentForm.skills.split(",").map(s => s.trim()).filter(Boolean).map(skill => (
                  <span key={skill} className="inline-flex items-center gap-1 px-2 py-0.5 bg-accent/10 text-accent border border-accent/20 rounded-lg text-xs">
                    {skill}
                    <button onClick={() => {
                      const current = agentForm.skills.split(",").map(s => s.trim()).filter(Boolean);
                      setAgentForm(f => ({ ...f, skills: current.filter(x => x !== skill).join(", ") }));
                    }} className="text-accent/60 hover:text-accent">
                      <X className="w-3 h-3" />
                    </button>
                  </span>
                )) : null}
              </div>
              <button type="button" onClick={(e) => { e.stopPropagation(); setSkillsDropdownOpen(!skillsDropdownOpen); }}
                className="w-full flex items-center justify-between bg-surface border border-border rounded-xl px-3 py-2 text-sm text-muted hover:text-white transition-colors">
                <span>{agentForm.skills ? "已选 " + agentForm.skills.split(",").filter(Boolean).length + " 个技能" : "选择技能..."}</span>
                <span className="text-[10px]">{skillsDropdownOpen ? "▲" : "▼"}</span>
              </button>
              {skillsDropdownOpen && (
                <div className="absolute z-50 w-full mt-1 bg-card border border-border rounded-xl shadow-xl max-h-48 overflow-auto">
                  {availableSkills.length === 0 ? (
                    <p className="text-xs text-muted p-3">暂无可用技能，请先在设置中同步</p>
                  ) : (
                    availableSkills.map(skill => {
                      const selected = agentForm.skills.split(",").map(s => s.trim()).includes(skill.name);
                      return (
                        <button key={skill.name} type="button" onClick={() => {
                          const current = agentForm.skills ? agentForm.skills.split(",").map(s => s.trim()).filter(Boolean) : [];
                          const next = selected ? current.filter(x => x !== skill.name) : [...current, skill.name];
                          setAgentForm(f => ({ ...f, skills: next.join(", ") }));
                        }}
                          className={`w-full text-left px-3 py-2 text-xs hover:bg-white/5 transition-colors flex items-center justify-between ${
                            selected ? "text-accent" : "text-slate-300"
                          }`}>
                          <span>{skill.name}</span>
                          {skill.description && <span className="text-[10px] text-muted truncate ml-2 max-w-[200px]">{skill.description}</span>}
                        </button>
                      );
                    })
                  )}
                </div>
              )}
            </div>

            {/* Permissions */}
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted flex items-center gap-1.5 mb-2">
                <Shield className="w-3 h-3" /> 权限
              </label>
              <div className="space-y-2">
                {[
                  { key: "file_write", label: "文件写入", desc: "允许读写工作区文件" },
                  { key: "shell_exec", label: "Shell 执行", desc: "允许执行终端命令" },
                  { key: "subagent_spawn", label: "子 Agent", desc: "允许创建子 Agent 执行子任务" },
                ].map(perm => (
                  <label key={perm.key} className="flex items-center justify-between p-2.5 bg-surface border border-border rounded-xl cursor-pointer hover:border-accent/20 transition-colors">
                    <div>
                      <span className="text-sm text-white">{perm.label}</span>
                      <p className="text-[10px] text-muted">{perm.desc}</p>
                    </div>
                    <button type="button" onClick={() => {
                      setAgentForm(f => ({ ...f, [perm.key]: !(f as Record<string, unknown>)[perm.key] as boolean }));
                    }}
                      className={`w-9 h-5 rounded-full transition-colors relative ${
                        (agentForm as Record<string, unknown>)[perm.key] ? "bg-accent" : "bg-muted/30"
                      }`}>
                      <div className={`absolute top-0.5 w-4 h-4 rounded-full bg-white transition-transform ${
                        (agentForm as Record<string, unknown>)[perm.key] ? "left-4" : "left-0.5"
                      }`} />
                    </button>
                  </label>
                ))}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowAgentEditor(false)}
                className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">取消</button>
              <button onClick={saveAgent} disabled={agentSaving || !agentForm.name.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30">
                {agentSaving ? <Loader2 className="w-4 h-4 animate-spin" /> : null} 保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          title="删除工作区"
          message={`确定要删除工作区 "${deleteTarget}" 吗？此操作不可恢复。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

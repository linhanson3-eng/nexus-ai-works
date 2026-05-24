import { useEffect, useState, useCallback, useRef } from "react";
import { AlertTriangle, Plus, Trash2, Play, Loader2, Blocks, RefreshCw, Bot, Settings, Zap, Download, Upload } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import { AgentEditor } from "./AgentEditor";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import type { Workshop, WorkflowResult, AgentInfo } from "../lib/types";

export function WorkshopList() {
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [model, setModel] = useState("");
  const [providerGroups, setProviderGroups] = useState<{ name: string; hasKey: boolean; models: string[] }[]>([]);
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

  // Import/Export
  const [exporting, setExporting] = useState<string | null>(null);
  const [importing, setImporting] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
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

  // Load provider models for dropdown (grouped by provider)
  useEffect(() => {
    api.listProviders().then(providers => {
      const groups: { name: string; hasKey: boolean; models: string[] }[] = [];
      for (const [pname, cfg] of Object.entries(providers)) {
        if (cfg.models?.length) {
          groups.push({ name: pname, hasKey: !!cfg.api_key, models: cfg.models });
        }
      }
      setProviderGroups(groups);
    }).catch((err) => { console.error("加载模型列表失败", err); });
  }, []);

  const create = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      await api.createWorkshop(trimmed, undefined, model);
      setName("");
      setShowCreate(false);
      toast.success(`项目 "${trimmed}" 已创建`);
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
      toast.success(`项目 "${wsName}" 已删除`);
      if (selected?.name === wsName) setSelected(null);
      await load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    } finally {
      setDeleteTarget(null);
    }
  };

  const exportWorkspace = async (wsName: string) => {
    setExporting(wsName);
    try {
      const res = await fetch(`/api/workshops/${wsName}/export`, { method: "POST", headers: { ...getAuthHeaders() }, credentials: "include" });
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${wsName}.nexus.zip`;
      a.click(); URL.revokeObjectURL(url);
      toast.success(`项目 "${wsName}" 已导出`);
    } catch {
      toast.error("导出失败，请确认 Gateway 已启动");
    } finally {
      setExporting(null);
    }
  };

  const importPackage = async (file: File) => {
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", file);
      const res = await fetch("/api/workshops/import", { method: "POST", headers: { ...getAuthHeaders() }, credentials: "include", body: formData });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "导入失败" }));
        throw new Error(err.detail || "导入失败");
      }
      const data = await res.json();
      toast.success(`模块 "${data.workspace}" 已导入`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "导入失败");
    } finally {
      setImporting(false);
    }
  };

  const removeWorkspace = async (wsName: string) => {
    try {
      await api.deleteWorkshop(wsName);
      toast.success(`项目 "${wsName}" 已卸载`);
      if (selected?.name === wsName) setSelected(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "卸载失败");
    } finally {
      setRemoveTarget(null);
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

  const loadAgents = async (wsName: string) => {
    setAgentsLoading(true);
    try {
      setAgents(await api.listAgents(wsName));
    } catch (err) {
      console.error("加载 Agent 列表失败", err);
      setAgents([]);
    } finally {
      setAgentsLoading(false);
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
            <Skeleton className="h-8 w-24" />
            <Skeleton className="h-4 w-48 mt-2" />
          </div>
        </div>
        {[1, 2, 3].map(i => (
          <Skeleton key={i} className="h-20 rounded-xl" />
        ))}
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl font-semibold tracking-tight text-foreground">项目</h1></div>
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <AlertTriangle className="w-10 h-10 text-destructive" />
          <p className="text-foreground font-semibold">加载失败</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <Button variant="outline" size="sm" onClick={load}>
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-foreground">项目</h1>
          <p className="text-muted-foreground text-sm mt-1">管理所有 AI 项目</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="file" ref={fileInputRef} accept=".zip,.nexus"
            onChange={e => { const f = e.target.files?.[0]; if (f) importPackage(f); }}
            className="hidden" />
          <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={importing}>
            {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />}
            导入模块
          </Button>
          <Button variant="outline" size="sm" onClick={() => setShowCreate(!showCreate)}>
            <Plus className="w-4 h-4" /> 新建项目
          </Button>
        </div>
      </div>

      {showCreate && (
        <div className="bg-card border border-border rounded-xl p-5 flex flex-col gap-3 sm:flex-row">
          <Input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !creating && create()}
            placeholder="项目名称"
            className="flex-1 rounded-xl"
            autoFocus
          />
          <select
            value={model}
            onChange={e => setModel(e.target.value)}
            className="bg-background border border-border rounded-xl px-4 py-2 text-sm text-foreground focus:outline-none focus:border-primary/30 min-w-[240px]"
          >
            <option value="">默认模型（可前往设置页配置）</option>
            {providerGroups.map(g => (
              <optgroup key={g.name} label={`${g.name} ${g.hasKey ? "\u2713" : "(未配置 Key)"}`}>
                {g.models.map(m => (
                  <option key={`${g.name}/${m}`} value={`${g.name}/${m}`}>{m}</option>
                ))}
              </optgroup>
            ))}
            <option value="__custom__">自定义输入...</option>
          </select>
          {model === "__custom__" && (
            <Input
              value=""
              onChange={e => setModel(e.target.value)}
              placeholder="输入模型名..."
              className="flex-1 rounded-xl border-primary/30"
              autoFocus
            />
          )}
          <Button
            size="sm"
            onClick={create}
            disabled={creating || !name.trim()}
            className="shrink-0"
          >
            {creating && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
            创建
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!loading && workshops.length === 0 && (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
            <Blocks className="w-7 h-7 text-muted-foreground" />
          </div>
          <div className="text-center">
            <p className="text-foreground font-semibold">暂无项目</p>
            <p className="text-sm text-muted-foreground mt-1">点击上方「新建项目」开始</p>
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
            className={`bg-card border rounded-xl p-5 cursor-pointer transition-all duration-200 hover:bg-accent ${
              selected?.name === w.name ? "border-primary/40 ring-1 ring-primary/20" : "border-border"
            }`}
          >
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div className={`w-3 h-3 rounded-full ${w.workflow_name !== "simple" ? "bg-primary" : "bg-muted"} ${w.has_kanban ? "shadow-[0_0_6px_rgba(6,182,212,0.4)]" : ""}`} />
                <span className="font-semibold text-foreground">{w.name}</span>
                <Badge variant="secondary" className="text-[11px] rounded-md font-normal">{w.workflow_name}</Badge>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-sm text-muted-foreground">{w.agent_count} agents</span>
                <button onClick={e => { e.stopPropagation(); exportWorkspace(w.name); }} disabled={exporting === w.name}
                  className="text-muted-foreground hover:text-primary transition-colors" title="导出为 .nexus 包">
                  {exporting === w.name ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />}
                </button>
                <button onClick={e => { e.stopPropagation(); setRemoveTarget(w.name); }}
                  className="text-muted-foreground/30 hover:text-destructive transition-colors" title="卸载项目">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>

            {/* Expanded detail */}
            {selected?.name === w.name && (
              <div className="mt-5 pt-5 border-t border-border space-y-4">
                {/* Agents */}
                <div>
                  <div className="flex items-center justify-between">
                    <span className="text-xs uppercase tracking-widest text-muted-foreground font-medium">Agents</span>
                    <button onClick={(e) => { e.stopPropagation(); setEditingAgent(null); setShowAgentEditor(true); }}
                      className="flex items-center gap-1 text-xs text-primary hover:text-foreground transition-colors">
                      <Plus className="w-3 h-3" /> 添加 Agent
                    </button>
                  </div>
                  {agentsLoading ? (
                    <Skeleton className="mt-2 h-10 rounded-xl" />
                  ) : agents.length === 0 ? (
                    <p className="text-xs text-muted-foreground mt-2">暂无 Agent，点击「添加 Agent」创建</p>
                  ) : (
                    <div className="mt-2 space-y-1.5">
                      {agents.map(a => (
                        <div key={a.name} className="flex items-center justify-between p-2.5 bg-background border border-border rounded-xl group">
                          <div className="flex items-center gap-2.5 min-w-0">
                            <div className={`w-6 h-6 rounded-lg flex items-center justify-center shrink-0 ${a.is_super ? "bg-destructive/10" : "bg-primary/10"}`}>
                              {a.is_super ? <Zap className="w-3 h-3 text-destructive" /> : <Bot className="w-3 h-3 text-primary" />}
                            </div>
                            <div className="min-w-0">
                              <div className="flex items-center gap-2">
                                <span className="text-sm text-foreground font-medium">{a.name}</span>
                                <Badge variant={a.is_super ? "destructive" : "secondary"} className="text-[9px] px-1.5 py-0.5 rounded font-medium">
                                  {a.is_super ? "超级" : "普通"}
                                </Badge>
                              </div>
                              <div className="flex items-center gap-2 text-xs text-muted-foreground mt-0.5">
                                <span>{a.model}</span>
                                <span>·</span>
                                <span>{a.tools_all ? "全工具" : `${a.tools.length} 工具`}</span>
                                {a.permissions?.subagent_spawn && <span className="text-destructive">· 可建子Agent</span>}
                              </div>
                            </div>
                          </div>
                          <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                            <button onClick={(e) => { e.stopPropagation(); setEditingAgent(a); setShowAgentEditor(true); }}
                              className="p-1.5 rounded-lg text-muted-foreground hover:text-foreground hover:bg-accent transition-colors">
                              <Settings className="w-3 h-3" />
                            </button>
                            <button onClick={(e) => { e.stopPropagation(); deleteAgent(a.name); }}
                              className="p-1.5 rounded-lg text-muted-foreground/30 hover:text-destructive transition-colors">
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
                    <span className="text-xs uppercase tracking-widest text-muted-foreground font-medium">看板</span>
                    <div className="mt-2 flex gap-4">
                      {Object.entries(w.kanban_stats).map(([sname, count]) => (
                        <div key={sname} className="text-center">
                          <div className="text-xl font-bold text-foreground">{count}</div>
                          <div className="text-xs text-muted-foreground">{sname}</div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Task runner */}
                <div>
                  <span className="text-xs uppercase tracking-widest text-muted-foreground font-medium">执行工作流</span>
                  <div className="mt-2 flex gap-3">
                    <Input
                      value={task}
                      onChange={e => setTask(e.target.value)}
                      onKeyDown={e => e.key === "Enter" && !running && task.trim() && run()}
                      placeholder="输入任务描述..."
                      disabled={running}
                      className="flex-1 rounded-xl"
                    />
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={run}
                      disabled={running || !task.trim()}
                    >
                      {running ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                      执行
                    </Button>
                  </div>
                </div>

                {result && (
                  <div className="bg-background border border-border rounded-xl p-4 font-mono text-xs text-terminal overflow-auto max-h-64">
                    <div className="text-primary mb-2">[{result.status}] {result.template_name}</div>
                    {Object.values(result.stage_results).map((sr: unknown) => {
                      const s = sr as { stage_id: string; status: string; output: string };
                      return (
                        <div key={s.stage_id} className="ml-2 mb-1">
                          <span className="text-primary">[{s.status}]</span> {s.stage_id}: {s.output?.slice(0, 200)}
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
        <AgentEditor
          workshopName={selected.name}
          existingAgent={editingAgent}
          onClose={() => setShowAgentEditor(false)}
          onSaved={() => loadAgents(selected.name)}
          toast={toast}
        />
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          title="删除项目"
          message={`确定要删除项目 "${deleteTarget}" 吗？此操作不可恢复。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}

      {/* Remove (uninstall) confirmation */}
      {removeTarget && (
        <ConfirmDialog
          title="卸载项目"
          message={`确定要完全卸载 "${removeTarget}" 吗？将删除项目目录、Agent、Workflow 和关联看板。此操作不可恢复。`}
          confirmLabel="卸载"
          onConfirm={() => removeWorkspace(removeTarget)}
          onCancel={() => setRemoveTarget(null)}
        />
      )}
    </div>
  );
}

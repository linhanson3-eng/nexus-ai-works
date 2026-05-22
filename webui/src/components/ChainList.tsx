import { useState, useEffect, useRef } from "react";
import { Link, Play, Plus, Trash2, Loader2, X, GitMerge, CheckCircle2, XCircle, Loader, ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { ChainInfo, ChainTemplate, ChainStep } from "../lib/types";

export function ChainList() {
  const toast = useToast();
  const [chains, setChains] = useState<ChainInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [editName, setEditName] = useState("");
  const [editDesc, setEditDesc] = useState("");
  const [editSteps, setEditSteps] = useState<ChainStep[]>([]);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  // Execute state
  const [executing, setExecuting] = useState(false);
  const [execChain, setExecChain] = useState<string | null>(null);
  const [execTask, setExecTask] = useState("");
  const [execStatus, setExecStatus] = useState<Record<string, string>>({});
  const [execResult, setExecResult] = useState<{
    status: string; final_output: string;
    step_results: { workshop: string; workflow: string; status: string; output: string }[];
  } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const loadChains = async () => {
    setLoading(true);
    try {
      setChains(await api.listChains());
    } catch {
      toast.error("加载协作链失败");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { loadChains(); }, []);

  const openCreate = () => {
    setEditName("");
    setEditDesc("");
    setEditSteps([]);
    setShowCreate(true);
  };

  const openEdit = async (name: string) => {
    try {
      const chain = await api.getChain(name);
      setEditName(chain.name);
      setEditDesc(chain.description || "");
      setEditSteps(chain.steps || []);
      setShowCreate(true);
    } catch {
      toast.error("加载链失败");
    }
  };

  const saveChain = async () => {
    if (!editName.trim()) { toast.error("请输入链名称"); return; }
    setSaving(true);
    try {
      await api.saveChain({ name: editName.trim(), description: editDesc, steps: editSteps });
      toast.success("链已保存");
      setShowCreate(false);
      loadChains();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const deleteChain = async (name: string) => {
    try {
      await api.deleteChain(name);
      toast.success("链已删除");
      loadChains();
    } catch {
      toast.error("删除失败");
    } finally {
      setDeleteTarget(null);
    }
  };

  const addStep = () => {
    setEditSteps(prev => [...prev, { workshop: "", workflow: "", description: "" }]);
  };

  const updateStep = (i: number, field: keyof ChainStep, value: string) => {
    setEditSteps(prev => prev.map((s, j) => j === i ? { ...s, [field]: value } : s));
  };

  const removeStep = (i: number) => {
    setEditSteps(prev => prev.filter((_, j) => j !== i));
  };

  // ── Execute ──

  const startExecute = (chainName: string) => {
    setExecChain(chainName);
    setExecTask("");
    setExecStatus({});
    setExecResult(null);
  };

  const runExecute = async () => {
    if (!execChain || !execTask.trim()) return;
    setExecuting(true);
    setExecStatus({});
    setExecResult(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/chains/${encodeURIComponent(execChain)}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: execTask.trim() }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "执行失败" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventName = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventName) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventName === "step_started") {
                setExecStatus(prev => ({ ...prev, [data.target]: "running" }));
              } else if (eventName === "step_completed") {
                setExecStatus(prev => ({ ...prev, [data.target]: data.detail.includes("failed") ? "failed" : "passed" }));
              } else if (eventName === "step_error") {
                setExecStatus(prev => ({ ...prev, [data.target]: "failed" }));
                toast.error(data.detail);
              } else if (eventName === "completed") {
                setExecResult(data);
              } else if (eventName === "error") {
                toast.error(data.message || "执行出错");
              }
            } catch { /* skip */ }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error(err instanceof Error ? err.message : "执行失败");
      }
    } finally {
      setExecuting(false);
      abortRef.current = null;
    }
  };

  // ── Render ──

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">跨工作区协作链</h1>
          <p className="text-muted text-sm mt-1">串联多个工作区，前一个产出作为后一个输入</p>
        </div>
        <button onClick={openCreate}
          className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors">
          <Plus className="w-4 h-4" /> 新建协作链
        </button>
      </div>

      {loading ? (
        <div className="grid grid-cols-2 gap-4">
          {[1, 2].map(i => <div key={i} className="h-28 bg-card rounded-[20px] border border-border animate-pulse" />)}
        </div>
      ) : chains.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
            <GitMerge className="w-7 h-7 text-muted" />
          </div>
          <div className="text-center">
            <p className="text-white font-semibold">暂无协作链</p>
            <p className="text-sm text-muted mt-1">创建跨工作区的流水线，例如：市场分析 → 内容策略 → 内容制作</p>
          </div>
        </div>
      ) : (
        <div className="grid gap-3">
          {chains.map(c => (
            <div key={c.name} className="bg-card border border-border rounded-[20px] p-5 hover:border-accent/10 transition-colors">
              <div className="flex items-start justify-between gap-4">
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-2">
                    <GitMerge className="w-4 h-4 text-info" />
                    <h3 className="text-white font-semibold">{c.name}</h3>
                  </div>
                  {c.description && <p className="text-sm text-muted mb-3">{c.description}</p>}
                  <div className="flex items-center gap-1.5 flex-wrap">
                    {c.steps.map((s, i) => (
                      <span key={i} className="flex items-center gap-1">
                        <span className="text-xs bg-surface border border-border rounded-lg px-2.5 py-1 text-slate-300">{s}</span>
                        {i < c.steps.length - 1 && <ArrowRight className="w-3 h-3 text-muted" />}
                      </span>
                    ))}
                  </div>
                  {execChain === c.name && (
                    <div className="mt-3 space-y-2">
                      {c.steps.map(s => {
                        const status = execStatus[s];
                        return status ? (
                          <div key={s} className={`flex items-center gap-2 text-xs p-2 rounded-lg ${
                            status === "running" ? "bg-info/5 text-info" :
                            status === "passed" ? "bg-success/5 text-success" :
                            "bg-warning/5 text-warning"
                          }`}>
                            {status === "running" ? <Loader className="w-3 h-3 animate-spin" /> :
                             status === "passed" ? <CheckCircle2 className="w-3 h-3" /> :
                             <XCircle className="w-3 h-3" />}
                            {s}
                          </div>
                        ) : (
                          <div key={s} className="flex items-center gap-2 text-xs p-2 text-muted">
                            <div className="w-2 h-2 rounded-full bg-muted/30" /> {s}
                          </div>
                        );
                      })}
                      {execResult && (
                        <div className="mt-2 p-3 bg-surface border border-border rounded-xl">
                          <p className="text-xs text-white font-medium mb-1">
                            {execResult.status === "passed" ? "全部完成" : "执行失败"}
                          </p>
                          {execResult.final_output && (
                            <p className="text-xs text-muted line-clamp-3 whitespace-pre-wrap">{execResult.final_output}</p>
                          )}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => startExecute(c.name)}
                    className="p-2 rounded-xl text-success hover:bg-success/10 transition-colors" title="执行">
                    <Play className="w-4 h-4" />
                  </button>
                  <button onClick={() => openEdit(c.name)}
                    className="p-2 rounded-xl text-muted hover:text-white transition-colors" title="编辑">
                    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></svg>
                  </button>
                  <button onClick={() => setDeleteTarget(c.name)}
                    className="p-2 rounded-xl text-muted/30 hover:text-warning transition-colors" title="删除">
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* ── Create/Edit Dialog ── */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreate(false)}>
          <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-lg space-y-4 shadow-2xl max-h-[80vh] overflow-auto" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">{editName ? "编辑协作链" : "新建协作链"}</h2>
              <button onClick={() => setShowCreate(false)} className="p-1.5 rounded-lg text-muted hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">名称</label>
              <input value={editName} onChange={e => setEditName(e.target.value)}
                placeholder="例如：市场分析流水线"
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">描述</label>
              <input value={editDesc} onChange={e => setEditDesc(e.target.value)}
                placeholder="描述这个协作链的用途..."
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
            </div>

            <div>
              <div className="flex items-center justify-between mb-2">
                <label className="text-[10px] uppercase tracking-widest text-muted">步骤</label>
                <button onClick={addStep}
                  className="text-xs text-accent hover:text-white transition-colors flex items-center gap-1">
                  <Plus className="w-3 h-3" /> 添加步骤
                </button>
              </div>
              <div className="space-y-2">
                {editSteps.map((s, i) => (
                  <div key={i} className="flex items-center gap-2 p-2 bg-surface border border-border rounded-xl">
                    <span className="text-[10px] text-muted shrink-0 w-5 text-right">{i + 1}</span>
                    <input value={s.workshop} onChange={e => updateStep(i, "workshop", e.target.value)}
                      placeholder="工作区"
                      className="flex-1 bg-transparent text-sm text-white placeholder:text-muted/50 focus:outline-none min-w-0" />
                    <input value={s.workflow} onChange={e => updateStep(i, "workflow", e.target.value)}
                      placeholder="工作流(可选)"
                      className="flex-1 bg-transparent text-sm text-white placeholder:text-muted/50 focus:outline-none min-w-0" />
                    <button onClick={() => removeStep(i)}
                      className="p-1 text-muted/40 hover:text-warning shrink-0">
                      <X className="w-3 h-3" />
                    </button>
                  </div>
                ))}
                {editSteps.length === 0 && (
                  <p className="text-xs text-muted text-center py-4">点击「添加步骤」定义协作链的工作区顺序</p>
                )}
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2">
              <button onClick={() => setShowCreate(false)}
                className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">取消</button>
              <button onClick={saveChain} disabled={saving || !editName.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : null} 保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Execute Dialog ── */}
      {execChain && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => { if (!executing) setExecChain(null); }}>
          <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">执行协作链: {execChain}</h2>
              <button onClick={() => { if (!executing) setExecChain(null); }}
                className="p-1.5 rounded-lg text-muted hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">任务描述</label>
              <textarea value={execTask} onChange={e => setExecTask(e.target.value)}
                placeholder="描述要跨工作区执行的任务..."
                rows={4}
                disabled={executing}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1 resize-none disabled:opacity-50" />
            </div>

            {execResult && (
              <div className="p-4 bg-surface border border-border rounded-xl">
                <p className="text-sm text-white font-medium mb-2">
                  {execResult.status === "passed" ? "全部步骤完成" : "执行失败"}
                </p>
                {execResult.step_results?.map((r, i) => (
                  <div key={i} className="flex items-center gap-2 text-xs py-1">
                    {r.status === "passed" ? <CheckCircle2 className="w-3 h-3 text-success" /> :
                     <XCircle className="w-3 h-3 text-warning" />}
                    <span className="text-white">{r.workshop}</span>
                    {r.workflow && <span className="text-muted">({r.workflow})</span>}
                  </div>
                ))}
                {execResult.final_output && (
                  <p className="text-xs text-muted mt-2 line-clamp-3 whitespace-pre-wrap">{execResult.final_output}</p>
                )}
              </div>
            )}

            <div className="flex justify-end gap-2">
              <button onClick={() => { if (!executing) setExecChain(null); }}
                className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">
                {execResult ? "关闭" : "取消"}
              </button>
              {!execResult && (
                <button onClick={runExecute} disabled={executing || !execTask.trim()}
                  className="flex items-center gap-1.5 px-4 py-2 bg-success/10 text-success border border-success/20 rounded-xl text-sm font-medium hover:bg-success/20 transition-colors disabled:opacity-30">
                  {executing ? <Loader2 className="w-4 h-4 animate-spin" /> : <Play className="w-4 h-4" />}
                  {executing ? "执行中..." : "开始执行"}
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ── Delete Confirm ── */}
      {deleteTarget && (
        <ConfirmDialog
          title="删除协作链"
          message={`确定要删除协作链 "${deleteTarget}" 吗？`}
          confirmLabel="删除"
          onConfirm={() => deleteChain(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

import { useEffect, useState, useCallback } from "react";
import { AlertTriangle, Plus, Trash2, Play, Loader2, Blocks, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { Workshop, WorkflowResult } from "../lib/types";

export function WorkshopList() {
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [creating, setCreating] = useState(false);
  const [selected, setSelected] = useState<Workshop | null>(null);
  const [task, setTask] = useState("");
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<WorkflowResult | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
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

  const create = async () => {
    const trimmed = name.trim();
    if (!trimmed) return;
    setCreating(true);
    try {
      await api.createWorkshop(trimmed);
      setName("");
      setShowCreate(false);
      toast.success(`车间 "${trimmed}" 已创建`);
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
      toast.success(`车间 "${wsName}" 已删除`);
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
        <div><h1 className="text-2xl font-black tracking-tight text-white">车间</h1></div>
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
          <h1 className="text-2xl font-black tracking-tight text-white">车间</h1>
          <p className="text-muted text-sm mt-1">管理所有 AI 工作车间</p>
        </div>
        <button
          onClick={() => setShowCreate(!showCreate)}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors"
        >
          <Plus className="w-4 h-4" /> 新建车间
        </button>
      </div>

      {showCreate && (
        <div className="bg-card border border-border rounded-[20px] p-5 flex gap-3">
          <input
            value={name}
            onChange={e => setName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !creating && create()}
            placeholder="车间名称（不能为空）"
            className="flex-1 bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
            autoFocus
          />
          <button
            onClick={create}
            disabled={creating || !name.trim()}
            className="px-5 py-2 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-30 flex items-center gap-2"
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
            <p className="text-white font-semibold">暂无车间</p>
            <p className="text-sm text-muted mt-1">创建第一个 AI 工作车间来开始使用</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors"
          >
            <Plus className="w-4 h-4" /> 创建车间
          </button>
        </div>
      )}

      <div className="grid grid-cols-1 gap-3">
        {workshops.map(w => (
          <div
            key={w.name}
            onClick={() => setSelected(selected?.name === w.name ? null : w)}
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
                  title="删除车间"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            {/* Expanded detail */}
            {selected?.name === w.name && (
              <div className="mt-5 pt-5 border-t border-border space-y-4">
                {w.agents && (
                  <div>
                    <span className="text-[10px] uppercase tracking-widest text-muted font-medium">Agents</span>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {Object.entries(w.agents).map(([aname, info]) => (
                        <span key={aname} className="px-3 py-1 bg-surface border border-border rounded-lg text-xs text-slate-300">
                          {aname} <span className="text-muted">· {(info as { model: string }).model}</span>
                        </span>
                      ))}
                    </div>
                  </div>
                )}

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

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          title="删除车间"
          message={`确定要删除车间 "${deleteTarget}" 吗？此操作不可恢复。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

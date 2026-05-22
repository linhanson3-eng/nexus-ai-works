import { useEffect, useState, useCallback } from "react";
import { GitBranch, Plus, Trash2, Loader2, AlertTriangle, RefreshCw, Zap } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import { WorkflowEditor } from "./WorkflowEditor";
import type { WorkflowInfo } from "../lib/types";

export function WorkflowList() {
  const [workflows, setWorkflows] = useState<WorkflowInfo[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editorOpen, setEditorOpen] = useState(false);
  const [editTarget, setEditTarget] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const toast = useToast();

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setWorkflows(await api.listWorkflows()); }
    catch (err) { setError(err instanceof Error ? err.message : "加载失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const remove = async (name: string) => {
    try { await api.deleteWorkflow(name); toast.success(`"${name}" 已删除`); load(); setDeleteTarget(null); }
    catch (err) { toast.error(err instanceof Error ? err.message : "删除失败"); }
  };

  if (editorOpen) {
    return <WorkflowEditor templateName={editTarget} onBack={() => { setEditorOpen(false); setEditTarget(null); load(); }} />;
  }

  if (loading) return (
    <div className="flex items-center justify-center py-20 gap-2">
      <Loader2 className="w-5 h-5 text-accent animate-spin" /><span className="text-sm text-muted">加载工作流...</span>
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">工作流</h1>
          <p className="text-muted text-sm mt-1">可视化编排多 Agent 协作流程</p>
        </div>
        <button onClick={() => { setEditTarget(null); setEditorOpen(true); }}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors">
          <Plus className="w-4 h-4" /> 新建工作流
        </button>
      </div>

      {error && (
        <div className="flex flex-col items-center gap-3 py-12">
          <AlertTriangle className="w-8 h-8 text-warning" />
          <p className="text-sm text-muted">{error}</p>
          <button onClick={load} className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm"><RefreshCw className="w-3.5 h-3.5" />重试</button>
        </div>
      )}

      {!error && workflows.length === 0 && (
        <div className="flex flex-col items-center gap-3 py-20">
          <GitBranch className="w-12 h-12 text-muted" />
          <p className="text-white font-semibold">暂无工作流模板</p>
          <p className="text-sm text-muted mt-1">创建第一个可视化工作流，编排多 Agent 协作</p>
          <button onClick={() => { setEditTarget(null); setEditorOpen(true); }}
            className="mt-4 inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors">
            <Plus className="w-4 h-4" /> 创建工作流
          </button>
        </div>
      )}

      {!error && workflows.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {workflows.map(w => (
            <div key={w.name} onClick={() => { setEditTarget(w.name); setEditorOpen(true); }}
              className="bg-card border border-border rounded-[20px] p-5 hover:border-accent/20 cursor-pointer transition-all group">
              <div className="flex items-start justify-between mb-3">
                <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
                  <GitBranch className="w-5 h-5 text-accent" />
                </div>
                <button onClick={e => { e.stopPropagation(); setDeleteTarget(w.name); }}
                  className="text-muted hover:text-warning opacity-0 group-hover:opacity-100 transition-all">
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
              <h3 className="text-white font-semibold text-sm">{w.name}</h3>
              <p className="text-xs text-muted mt-1 line-clamp-2">{w.description || "无描述"}</p>
              <div className="flex items-center gap-3 mt-3 pt-3 border-t border-border">
                <span className="text-[10px] text-muted flex items-center gap-1"><Zap className="w-3 h-3" />{w.node_count} 节点</span>
                {w.workspace && <span className="text-[10px] text-muted">{w.workspace}</span>}
              </div>
            </div>
          ))}
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog title="删除工作流" message={`确定要删除 "${deleteTarget}" 吗？`}
          confirmLabel="删除" onConfirm={() => remove(deleteTarget)} onCancel={() => setDeleteTarget(null)} />
      )}
    </div>
  );
}

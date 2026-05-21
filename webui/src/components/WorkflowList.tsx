import { useEffect, useState, useCallback } from "react";
import { GitBranch, ArrowRight, Shield, AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import { api } from "../lib/api";
import type { WorkflowTemplate } from "../lib/types";

export function WorkflowList() {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selected, setSelected] = useState<WorkflowTemplate | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listWorkflows();
      setWorkflows(data);
      if (data.length > 0) {
        setDetailLoading(true);
        try {
          const first = await api.getWorkflow(data[0].name);
          setSelected(first);
        } catch { /* selected stays null */ }
        finally { setDetailLoading(false); }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const selectWorkflow = async (name: string) => {
    setDetailLoading(true);
    try {
      const wf = await api.getWorkflow(name);
      setSelected(wf);
    } catch (err) {
      setSelected(null);
    } finally {
      setDetailLoading(false);
    }
  };

  // ── Loading ──
  if (loading) {
    return (
      <div className="space-y-6">
        <div><div className="h-8 w-24 bg-card rounded animate-pulse" /></div>
        <div className="grid grid-cols-5 gap-4">
          <div className="col-span-2 space-y-2">{[1,2,3,4].map(i => <div key={i} className="h-20 bg-card rounded-[16px] border border-border animate-pulse" />)}</div>
          <div className="col-span-3 bg-card rounded-[20px] border border-border animate-pulse min-h-[300px]" />
        </div>
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl font-black tracking-tight text-white">工作流</h1></div>
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

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-white">工作流</h1>
        <p className="text-muted text-sm mt-1">DAG 工作流模板与执行</p>
      </div>

      {workflows.length === 0 ? (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
            <GitBranch className="w-7 h-7 text-muted" />
          </div>
          <p className="text-white font-semibold">暂无工作流模板</p>
          <p className="text-sm text-muted">内置工作流模板尚未加载</p>
        </div>
      ) : (
        <div className="grid grid-cols-5 gap-4 max-lg:grid-cols-1">
          {/* Workflow list */}
          <div className="col-span-2 space-y-2">
            {workflows.map(wf => (
              <button
                key={wf.name}
                onClick={() => selectWorkflow(wf.name)}
                className={`w-full text-left p-4 rounded-[16px] border transition-all ${
                  selected?.name === wf.name
                    ? "bg-accent/10 border-accent/30"
                    : "bg-card border-border hover:bg-card-hover"
                }`}
              >
                <div className="flex items-center gap-2.5">
                  <GitBranch className={`w-4 h-4 ${selected?.name === wf.name ? "text-accent" : "text-muted"}`} />
                  <span className="text-sm font-semibold text-white">{wf.name}</span>
                  <span className="text-[10px] text-muted bg-surface px-1.5 py-0.5 rounded">{wf.source}</span>
                </div>
                <p className="text-xs text-muted mt-1.5 ml-7">{wf.description}</p>
              </button>
            ))}
          </div>

          {/* Workflow detail */}
          <div className="col-span-3 bg-card border border-border rounded-[20px] p-6 min-h-[300px]">
            {detailLoading ? (
              <div className="h-full flex items-center justify-center gap-2">
                <Loader2 className="w-5 h-5 text-accent animate-spin" />
                <span className="text-sm text-muted">加载中...</span>
              </div>
            ) : selected ? (
              <div className="space-y-6">
                <div>
                  <h2 className="text-lg font-bold text-white">{selected.name}</h2>
                  <p className="text-sm text-muted mt-1">{selected.description}</p>
                </div>

                {selected.stages && (
                  <div className="space-y-3">
                    <span className="text-[10px] uppercase tracking-widest text-muted font-medium">执行阶段</span>
                    {selected.stages.map((stage, i) => (
                      <div key={stage.id} className="flex items-center gap-3">
                        <div className="flex items-center gap-3 bg-surface border border-border rounded-xl px-4 py-3 flex-1">
                          <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">{i + 1}</div>
                          <div>
                            <div className="flex items-center gap-2 flex-wrap">
                              <span className="text-sm font-medium text-white">{stage.id}</span>
                              <span className="text-[10px] text-muted bg-surface px-1.5 py-0.5 rounded">{stage.agent}</span>
                              {stage.gate && (
                                <span className="flex items-center gap-1 text-[10px] text-warning">
                                  <Shield className="w-3 h-3" /> gate
                                </span>
                              )}
                            </div>
                            <p className="text-xs text-muted mt-0.5">{stage.action}</p>
                          </div>
                          <span className="text-[10px] text-info bg-info/10 px-2 py-0.5 rounded ml-auto">{stage.output}</span>
                        </div>
                        {i < (selected.stages?.length || 0) - 1 && (
                          <ArrowRight className="w-4 h-4 text-muted shrink-0" />
                        )}
                      </div>
                    ))}
                  </div>
                )}

                {selected.stages?.some(s => s.depends_on?.length) && (
                  <div>
                    <span className="text-[10px] uppercase tracking-widest text-muted font-medium">依赖关系</span>
                    <div className="mt-2 flex flex-wrap gap-2">
                      {selected.stages.filter(s => s.depends_on?.length).map(s =>
                        s.depends_on?.map(dep => (
                          <span key={`${s.id}-${dep}`} className="text-[10px] px-2 py-1 bg-surface border border-border rounded-lg text-muted">
                            {s.id} ← {dep}
                          </span>
                        ))
                      )}
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div className="h-full flex items-center justify-center text-muted text-sm">
                选择一个工作流查看详情
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

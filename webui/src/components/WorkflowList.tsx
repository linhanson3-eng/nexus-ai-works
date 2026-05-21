import { useEffect, useState } from "react";
import { GitBranch, ArrowRight, Shield } from "lucide-react";
import { api } from "../lib/api";
import type { WorkflowTemplate } from "../lib/types";

export function WorkflowList() {
  const [workflows, setWorkflows] = useState<WorkflowTemplate[]>([]);
  const [selected, setSelected] = useState<WorkflowTemplate | null>(null);

  useEffect(() => {
    api.listWorkflows().then(setWorkflows);
    api.listWorkflows().then(ws => {
      if (ws.length > 0) {
        api.getWorkflow(ws[0].name).then(setSelected);
      }
    });
  }, []);

  const selectWorkflow = async (name: string) => {
    const wf = await api.getWorkflow(name);
    setSelected(wf);
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-white">工作流</h1>
        <p className="text-muted text-sm mt-1">DAG 工作流模板与执行</p>
      </div>

      <div className="grid grid-cols-5 gap-4">
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
          {selected ? (
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
                      {/* Stage node */}
                      <div className="flex items-center gap-3 bg-surface border border-border rounded-xl px-4 py-3 flex-1">
                        <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center text-xs font-bold text-accent">
                          {i + 1}
                        </div>
                        <div>
                          <div className="flex items-center gap-2">
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

                      {/* Arrow to next stage */}
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
    </div>
  );
}

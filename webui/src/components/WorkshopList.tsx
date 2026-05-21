import { useEffect, useState } from "react";
import { Plus, Trash2, Play } from "lucide-react";
import { api } from "../lib/api";
import type { Workshop, WorkflowResult } from "../lib/types";

export function WorkshopList() {
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [selected, setSelected] = useState<Workshop | null>(null);
  const [task, setTask] = useState("");
  const [result, setResult] = useState<WorkflowResult | null>(null);

  const refresh = () => api.listWorkshops().then(setWorkshops);

  useEffect(() => { refresh(); }, []);

  const create = async () => {
    if (!name) return;
    await api.createWorkshop(name);
    setName("");
    setShowCreate(false);
    refresh();
  };

  const remove = async (name: string) => {
    await api.deleteWorkshop(name);
    refresh();
    if (selected?.name === name) setSelected(null);
  };

  const run = async () => {
    if (!selected || !task) return;
    const r = await api.runWorkflow(selected.name, selected.workflow_name, task);
    setResult(r);
    setTask("");
  };

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
            onKeyDown={e => e.key === "Enter" && create()}
            placeholder="车间名称"
            className="flex-1 bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
          />
          <button onClick={create} className="px-5 py-2 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors">
            创建
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
                  onClick={e => { e.stopPropagation(); remove(w.name); }}
                  className="text-muted hover:text-warning transition-colors"
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
                      {Object.entries(w.kanban_stats).map(([name, count]) => (
                        <div key={name} className="text-center">
                          <div className="text-xl font-bold text-white">{count}</div>
                          <div className="text-[10px] text-muted">{name}</div>
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
                      onKeyDown={e => e.key === "Enter" && run()}
                      placeholder="输入任务描述..."
                      className="flex-1 bg-surface border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
                    />
                    <button onClick={run} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
                      <Play className="w-3.5 h-3.5" /> 执行
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
    </div>
  );
}

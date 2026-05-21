import { useEffect, useState } from "react";
import { Blocks, Bug, CheckCircle2, Users } from "lucide-react";
import { api } from "../lib/api";
import type { OrgStatus, Workshop } from "../lib/types";

export function Dashboard() {
  const [org, setOrg] = useState<OrgStatus | null>(null);
  const [workshops, setWorkshops] = useState<Workshop[]>([]);

  useEffect(() => {
    api.orgStatus().then(setOrg);
    api.listWorkshops().then(setWorkshops);
  }, []);

  const totalAgents = org?.total_agents ?? 0;
  const superAgents = org?.super_agents ?? 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-white">总览</h1>
        <p className="text-muted text-sm mt-1">工厂实时状态监控</p>
      </div>

      {/* Bento Grid */}
      <div className="grid grid-cols-4 gap-4 auto-rows-[140px]">
        {/* Hero stat — total agents */}
        <div className="col-span-2 row-span-2 bg-card rounded-[20px] border border-border p-6 flex flex-col justify-between relative overflow-hidden group hover:bg-card-hover transition-colors">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent/40 via-accent/20 to-transparent" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-accent" />
            </div>
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">活跃 Agent</span>
          </div>
          <div>
            <div className="text-5xl font-black text-white tracking-tight tabular-nums">{totalAgents}</div>
            <p className="text-sm text-muted mt-1">{superAgents} 个超级 Agent · {workshops.length} 个车间</p>
          </div>
        </div>

        {/* Running status */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">系统状态</span>
          </div>
          <div className="text-2xl font-bold text-success tracking-tight">在线</div>
          <p className="text-xs text-muted">Gateway v0.7</p>
        </div>

        {/* Workshops */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <Blocks className="w-4 h-4 text-info" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">车间</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">{workshops.length}</div>
          <p className="text-xs text-muted">
            {workshops.filter(w => w.has_kanban).length} 个已绑定看板
          </p>
        </div>

        {/* Kanban stats */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <Bug className="w-4 h-4 text-warning" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">看板任务</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">
            {workshops.reduce((sum, w) => {
              const stats: number[] = Object.values(w.kanban_stats || {}) as number[];
              return sum + stats.reduce((a: number, b: number) => a + b, 0);
            }, 0)}
          </div>
          <p className="text-xs text-muted">全部看板卡片总数</p>
        </div>

        {/* Workshop list */}
        <div className="col-span-2 bg-card rounded-[20px] border border-border p-5 flex flex-col hover:bg-card-hover transition-colors overflow-hidden">
          <span className="text-[11px] uppercase tracking-widest text-muted font-medium mb-3">车间列表</span>
          <div className="flex-1 space-y-2 overflow-auto">
            {workshops.map(w => (
              <a
                key={w.name}
                href={`/workshops/${w.name}`}
                className="flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 transition-colors group"
              >
                <div className="flex items-center gap-2.5">
                  <div className={`w-2 h-2 rounded-full ${w.workflow_name !== "simple" ? "bg-info" : "bg-muted"}`} />
                  <span className="text-sm text-white group-hover:text-accent transition-colors">{w.name}</span>
                </div>
                <span className="text-[11px] text-muted">{w.agent_count} agents</span>
              </a>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}

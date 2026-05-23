import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Blocks, Bug, CheckCircle2, Users, AlertTriangle, RefreshCw, Activity } from "lucide-react";
import { api } from "../lib/api";
import type { OrgStatus, Workshop } from "../lib/types";

export function Dashboard() {
  const [org, setOrg] = useState<OrgStatus | null>(null);
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const navigate = useNavigate();

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [orgData, wsData] = await Promise.all([api.orgStatus(), api.listWorkshops()]);
      setOrg(orgData);
      setWorkshops(wsData);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const totalAgents = org?.total_agents ?? 0;
  const totalCards = workshops.reduce((sum, w) => {
    const stats: number[] = Object.values(w.kanban_stats || {}) as number[];
    return sum + stats.reduce((a: number, b: number) => a + b, 0);
  }, 0);

  // ── Loading state ──
  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <div className="h-8 w-24 bg-card rounded animate-pulse" />
          <div className="h-4 w-48 bg-card rounded animate-pulse mt-2" />
        </div>
        <div className="grid grid-cols-4 gap-4">
          <div className="col-span-2 row-span-2 bg-card rounded-[20px] border border-border animate-pulse" />
          <div className="bg-card rounded-[20px] border border-border animate-pulse" />
          <div className="bg-card rounded-[20px] border border-border animate-pulse" />
          <div className="bg-card rounded-[20px] border border-border animate-pulse" />
          <div className="col-span-2 bg-card rounded-[20px] border border-border animate-pulse" />
        </div>
      </div>
    );
  }

  // ── Error state ──
  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">总览</h1>
          <p className="text-muted text-sm mt-1">工厂实时状态监控</p>
        </div>
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-warning/10 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-warning" />
          </div>
          <div className="text-center">
            <p className="text-white font-semibold">加载失败</p>
            <p className="text-sm text-muted mt-1">{error}</p>
          </div>
          <button
            onClick={load}
            className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      </div>
    );
  }

  // ── Content ──
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-white">总览</h1>
        <p className="text-muted text-sm mt-1">工厂实时状态监控</p>
      </div>

      <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-md:grid-cols-1">
        {/* Hero stat */}
        <div className="col-span-2 row-span-2 bg-card rounded-[20px] border border-border p-6 flex flex-col justify-between relative overflow-hidden group hover:bg-card-hover transition-colors max-lg:col-span-2">
          <div className="absolute top-0 left-0 w-full h-1 bg-gradient-to-r from-accent/40 via-accent/20 to-transparent" />
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-accent/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-accent" />
            </div>
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">活跃 Agent</span>
          </div>
          <div>
            <div className="text-5xl font-black text-white tracking-tight tabular-nums">{totalAgents}</div>
            <p className="text-sm text-muted mt-1">{totalAgents} 个 Agent · {workshops.length} 个项目</p>
          </div>
        </div>

        {/* System status */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">系统状态</span>
          </div>
          <div className="text-2xl font-bold text-success tracking-tight">在线</div>
          <p className="text-xs text-muted">Gateway v1.0</p>
        </div>

        {/* Workshops count */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <Blocks className="w-4 h-4 text-info" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">项目</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">{workshops.length}</div>
          <p className="text-xs text-muted">{workshops.filter(w => w.has_kanban).length} 个已绑定看板</p>
        </div>

        {/* Card count */}
        <div className="bg-card rounded-[20px] border border-border p-5 flex flex-col justify-between hover:bg-card-hover transition-colors">
          <div className="flex items-center gap-2.5">
            <Bug className="w-4 h-4 text-warning" />
            <span className="text-[11px] uppercase tracking-widest text-muted font-medium">看板任务</span>
          </div>
          <div className="text-2xl font-bold text-white tracking-tight">{totalCards}</div>
          <p className="text-xs text-muted">全部看板卡片总数</p>
        </div>

        {/* Workshop list */}
        <div className="col-span-2 bg-card rounded-[20px] border border-border p-5 flex flex-col hover:bg-card-hover transition-colors overflow-hidden max-lg:col-span-2">
          <span className="text-[11px] uppercase tracking-widest text-muted font-medium mb-3">项目列表</span>
          {workshops.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3">
              <Activity className="w-8 h-8 text-muted" />
              <p className="text-sm text-muted">暂无项目</p>
              <button
                onClick={() => navigate("/workshops")}
                className="px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors"
              >
                创建第一个项目
              </button>
            </div>
          ) : (
            <div className="flex-1 space-y-2 overflow-auto">
              {workshops.map(w => (
                <button
                  key={w.name}
                  onClick={() => navigate(`/workshops?detail=${w.name}`)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-lg hover:bg-white/5 transition-colors group text-left"
                >
                  <div className="flex items-center gap-2.5">
                    <div className={`w-2 h-2 rounded-full ${w.workflow_name !== "simple" ? "bg-info" : "bg-muted"}`} />
                    <span className="text-sm text-white group-hover:text-accent transition-colors">{w.name}</span>
                  </div>
                  <span className="text-[11px] text-muted">{w.agent_count} agents</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

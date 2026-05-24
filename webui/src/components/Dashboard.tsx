import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Blocks, Bug, CheckCircle2, Users, AlertTriangle, RefreshCw, Activity, ArrowRight } from "lucide-react";
import { api } from "../lib/api";
import type { OrgStatus, Workshop } from "../lib/types";
import { Skeleton } from "@/components/ui/skeleton";
import { Badge } from "@/components/ui/badge";

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

  if (loading) {
    return (
      <div className="space-y-6">
        <div>
          <Skeleton className="h-8 w-24" />
          <Skeleton className="h-4 w-48 mt-2" />
        </div>
        <div className="grid grid-cols-4 gap-4">
          <Skeleton className="col-span-2 row-span-2 h-48 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="h-28 rounded-xl" />
          <Skeleton className="col-span-2 h-40 rounded-xl" />
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">总览</h1>
          <p className="text-muted-foreground text-sm mt-1">工厂实时状态监控</p>
        </div>
        <div className="flex flex-col items-center justify-center min-h-[400px] gap-4">
          <div className="w-14 h-14 rounded-xl bg-destructive/10 flex items-center justify-center">
            <AlertTriangle className="w-7 h-7 text-destructive" />
          </div>
          <p className="font-semibold">加载失败</p>
          <p className="text-sm text-muted-foreground">{error}</p>
          <button
            onClick={load}
            className="inline-flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-sm hover:bg-primary/20 transition-colors"
          >
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">总览</h1>
        <p className="text-muted-foreground text-sm mt-1">工厂实时状态监控</p>
      </div>

      <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-md:grid-cols-1">
        {/* Hero stat */}
        <div className="col-span-2 row-span-2 bg-card rounded-xl border border-border p-6 flex flex-col justify-between group hover:shadow-md transition-shadow max-lg:col-span-2">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
              <Users className="w-5 h-5 text-primary" />
            </div>
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">活跃 Agent</span>
          </div>
          <div>
            <div className="text-5xl font-semibold tracking-tight tabular-nums">{totalAgents}</div>
            <p className="text-sm text-muted-foreground mt-1">{totalAgents} 个 Agent · {workshops.length} 个项目</p>
          </div>
        </div>

        {/* System status */}
        <div className="bg-card rounded-xl border border-border p-5 flex flex-col justify-between hover:shadow-sm transition-shadow">
          <div className="flex items-center gap-2.5">
            <CheckCircle2 className="w-4 h-4 text-success" />
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">系统状态</span>
          </div>
          <div className="text-2xl font-semibold text-success tracking-tight">在线</div>
          <p className="text-xs text-muted-foreground">Gateway v1.0</p>
        </div>

        {/* Workshops count */}
        <div className="bg-card rounded-xl border border-border p-5 flex flex-col justify-between hover:shadow-sm transition-shadow">
          <div className="flex items-center gap-2.5">
            <Blocks className="w-4 h-4 text-primary" />
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">项目</span>
          </div>
          <div className="text-2xl font-semibold tracking-tight">{workshops.length}</div>
          <p className="text-xs text-muted-foreground">{workshops.filter((w) => w.has_kanban).length} 个已绑定看板</p>
        </div>

        {/* Card count */}
        <div className="bg-card rounded-xl border border-border p-5 flex flex-col justify-between hover:shadow-sm transition-shadow">
          <div className="flex items-center gap-2.5">
            <Bug className="w-4 h-4 text-warning" />
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">看板任务</span>
          </div>
          <div className="text-2xl font-semibold tracking-tight">{totalCards}</div>
          <p className="text-xs text-muted-foreground">全部看板卡片总数</p>
        </div>

        {/* Workshop list */}
        <div className="col-span-2 bg-card rounded-xl border border-border p-5 flex flex-col overflow-hidden max-lg:col-span-2">
          <div className="flex items-center justify-between mb-3">
            <span className="text-[11px] uppercase tracking-wider text-muted-foreground font-medium">项目列表</span>
            <button
              onClick={() => navigate("/workshops")}
              className="text-xs text-primary hover:underline flex items-center gap-1"
            >
              查看全部 <ArrowRight className="w-3 h-3" />
            </button>
          </div>
          {workshops.length === 0 ? (
            <div className="flex-1 flex flex-col items-center justify-center gap-3 py-8">
              <Activity className="w-8 h-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">暂无项目</p>
              <button
                onClick={() => navigate("/workshops")}
                className="px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-sm hover:bg-primary/20 transition-colors"
              >
                创建第一个项目
              </button>
            </div>
          ) : (
            <div className="flex-1 space-y-1 overflow-auto">
              {workshops.map((w) => (
                <button
                  key={w.name}
                  onClick={() => navigate(`/workshops?detail=${w.name}`)}
                  className="w-full flex items-center justify-between px-3 py-2 rounded-md hover:bg-accent transition-colors group text-left"
                >
                  <div className="flex items-center gap-2.5 min-w-0">
                    <div className={`w-2 h-2 rounded-full shrink-0 ${w.workflow_name !== "simple" ? "bg-primary" : "bg-muted-foreground/30"}`} />
                    <span className="text-sm truncate group-hover:text-primary transition-colors">{w.name}</span>
                    {w.has_kanban && <Badge variant="outline" className="text-[9px] px-1 py-0">看板</Badge>}
                  </div>
                  <span className="text-[11px] text-muted-foreground shrink-0 ml-2">{w.agent_count} agents</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

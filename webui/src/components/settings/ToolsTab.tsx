import { useEffect, useState, useCallback } from "react";
import { Wrench, RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";

export function ToolsTab({ toast }: { toast: ToastFn }) {
  const [servers, setServers] = useState<{ name: string; description: string; category: string; install_command?: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setServers(await api.listTools()); }
    catch (err) { setError(err instanceof Error ? err.message : "加载失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try { const result = await api.syncTools(); toast.success(`发现 ${result.count} 个工具`); load(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "同步失败"); }
    finally { setSyncing(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-12 gap-2">
      <Loader2 className="w-5 h-5 text-primary animate-spin" /><span className="text-sm text-muted">加载工具列表...</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center gap-3 py-12">
      <AlertTriangle className="w-8 h-8 text-destructive" /><p className="text-sm text-muted">{error}</p>
      <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-xl text-sm"><RefreshCw className="w-3.5 h-3.5" />重试</button>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">MCP 工具市场。安装 MCP 服务端为 Agent 提供文件、搜索、数据库等能力。</p>
        <button onClick={sync} disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-xl text-sm hover:bg-primary/20 transition-colors disabled:opacity-50 shrink-0">
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />同步市场
        </button>
      </div>

      {servers.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <Wrench className="w-10 h-10 text-muted" />
          <p className="text-sm text-muted">暂无 MCP 工具</p>
          <p className="text-xs text-muted">点击「同步市场」发现可用的 MCP 服务端</p>
        </div>
      ) : (
        <div className="space-y-2">
          {servers.map(s => (
            <div key={s.name} className="flex items-center justify-between bg-background border border-border rounded-xl px-4 py-3 hover:border-primary/10 transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
                  <Wrench className="w-4 h-4 text-info" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-foreground font-medium">{s.name}</span>
                    {s.category && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-primary/10 text-info">{s.category}</span>}
                  </div>
                  <p className="text-xs text-muted mt-0.5 truncate">{s.description}</p>
                </div>
              </div>
              {s.install_command && (
                <code className="text-[10px] text-muted bg-background px-2 py-1 rounded font-mono shrink-0 ml-2 truncate max-w-[200px]">{s.install_command}</code>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

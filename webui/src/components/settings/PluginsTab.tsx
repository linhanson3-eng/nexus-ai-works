import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2, Loader2, AlertTriangle, Blocks, Shield, RefreshCw } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";
import { ConfirmDialog } from "../ConfirmDialog";
import type { PluginEntry } from "../../lib/types";

export function PluginsTab({ toast }: { toast: ToastFn }) {
  const [plugins, setPlugins] = useState<Record<string, PluginEntry>>({});
  const [loading, setLoading] = useState(true);
  const [addingPlugin, setAddingPlugin] = useState(false);
  const [newPluginName, setNewPluginName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setPlugins(await api.listPlugins());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const toggle = async (name: string, enabled: boolean) => {
    try {
      await api.savePlugin(name, { enabled });
      toast.success(`"${name}" ${enabled ? "已启用" : "已禁用"}`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "切换失败");
    }
  };

  const remove = async (name: string) => {
    try {
      await api.deletePlugin(name);
      toast.success(`"${name}" 已删除`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2">
        <Loader2 className="w-5 h-5 text-primary animate-spin" />
        <span className="text-sm text-muted-foreground">加载插件列表...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <AlertTriangle className="w-8 h-8 text-destructive" />
        <p className="text-sm text-muted-foreground">{error}</p>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-xl text-sm hover:bg-primary/20 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  const entries = Object.values(plugins);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">Channel 适配器和平台插件。让 Nexus AI Works 接入微信、飞书、钉钉等外部平台。</p>
        {addingPlugin ? (
          <div className="flex items-center gap-2 shrink-0">
            <input
              autoFocus
              value={newPluginName}
              onChange={e => setNewPluginName(e.target.value)}
              onKeyDown={e => {
                if (e.key === "Enter" && newPluginName.trim()) {
                  api.savePlugin(newPluginName.trim(), { enabled: true }).then(() => load()).catch(e2 => toast.error(e2.message));
                  setNewPluginName(""); setAddingPlugin(false);
                }
                if (e.key === "Escape") { setNewPluginName(""); setAddingPlugin(false); }
              }}
              placeholder="插件名称..."
              className="w-40 bg-transparent border border-border/60 rounded-lg px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground/40 outline-none focus:border-primary/50"
            />
            <button onClick={() => {
              if (newPluginName.trim()) {
                api.savePlugin(newPluginName.trim(), { enabled: true }).then(() => load()).catch(e2 => toast.error(e2.message));
                setNewPluginName(""); setAddingPlugin(false);
              }
            }} className="px-3 py-2 text-xs bg-primary/10 text-primary rounded-lg hover:bg-primary/20">确认</button>
            <button onClick={() => { setNewPluginName(""); setAddingPlugin(false); }} className="px-3 py-2 text-xs text-muted-foreground/50 hover:text-foreground">取消</button>
          </div>
        ) : (
          <button
            onClick={() => setAddingPlugin(true)}
            className="flex items-center gap-2 px-4 py-2 bg-primary/10 text-primary border border-primary/20 rounded-xl text-sm hover:bg-primary/20 transition-colors shrink-0"
          >
            <Plus className="w-4 h-4" /> 安装插件
          </button>
        )}
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <Blocks className="w-10 h-10 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">尚未安装任何插件</p>
          <p className="text-xs text-muted-foreground">安装插件以接入外部平台</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(p => (
            <div key={p.name} className="flex items-center justify-between bg-background border border-border rounded-xl px-4 py-3">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${p.healthy ? "bg-success/10" : "bg-destructive/10"}`}>
                  <Shield className={`w-4 h-4 ${p.healthy ? "text-success" : "text-destructive"}`} />
                </div>
                <div>
                  <span className="text-sm text-foreground font-medium">{p.name}</span>
                  <p className="text-xs text-muted-foreground mt-0.5">{p.healthy ? "运行中" : "未连接"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <button
                  onClick={() => toggle(p.name, !p.enabled)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${p.enabled ? "bg-success/30" : "bg-muted"}`}
                >
                  <div className={`absolute w-4 h-4 bg-background rounded-full top-0.5 transition-all ${p.enabled ? "left-5" : "left-0.5"}`} />
                </button>
                <button
                  onClick={() => setDeleteTarget(p.name)}
                  className="text-muted-foreground hover:text-destructive transition-colors"
                  title="卸载插件"
                >
                  <Trash2 className="w-3.5 h-3.5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {deleteTarget && (
        <ConfirmDialog
          title="卸载插件"
          message={`确定要卸载插件 "${deleteTarget}" 吗？关联的 Channel 将停止工作。`}
          confirmLabel="卸载"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

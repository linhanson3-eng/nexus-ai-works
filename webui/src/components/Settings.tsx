import { useEffect, useState, useCallback } from "react";
import { Key, Puzzle, Wrench, Blocks, Plus, Trash2, Eye, EyeOff, RefreshCw, Loader2, AlertTriangle, Zap, Shield } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { PluginEntry } from "../lib/types";

type TabId = "providers" | "skills" | "tools" | "plugins";

const tabs: { id: TabId; label: string; icon: typeof Key }[] = [
  { id: "providers", label: "LLM Key", icon: Key },
  { id: "skills", label: "技能库", icon: Puzzle },
  { id: "tools", label: "工具箱", icon: Wrench },
  { id: "plugins", label: "插件", icon: Blocks },
];

const PRESET_PROVIDERS = ["anthropic", "deepseek", "moonshot", "openai", "kimi", "custom"];

export function Settings() {
  const [tab, setTab] = useState<TabId>("providers");
  const toast = useToast();

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-black tracking-tight text-white">设置</h1>
        <p className="text-muted text-sm mt-1">LLM、技能、工具与插件管理</p>
      </div>

      {/* Tab bar */}
      <div className="flex gap-1 bg-card border border-border rounded-2xl p-1.5 w-fit">
        {tabs.map(({ id, label, icon: Icon }) => (
          <button
            key={id}
            onClick={() => setTab(id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-all ${
              tab === id
                ? "bg-accent/10 text-accent border border-accent/20 shadow-sm"
                : "text-muted hover:text-white"
            }`}
          >
            <Icon className="w-4 h-4" />
            {label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="bg-card border border-border rounded-[20px] p-6">
        {tab === "providers" && <ProvidersTab toast={toast} />}
        {tab === "skills" && <SkillsTab toast={toast} />}
        {tab === "tools" && <ToolsTab toast={toast} />}
        {tab === "plugins" && <PluginsTab toast={toast} />}
      </div>
    </div>
  );
}

// ── Tab: LLM Key ─────────────────────────────────────────

function ProvidersTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [providers, setProviders] = useState<Record<string, { provider_type: string; base_url: string; api_key: string }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ base_url: "", api_key: "", show_key: false });
  const [saving, setSaving] = useState(false);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setProviders(await api.listProviders());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const startEdit = (name: string) => {
    const p = providers[name];
    setEditing(name);
    setForm({ base_url: p?.base_url || "", api_key: p?.api_key || "", show_key: false });
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await api.saveProvider(editing, { base_url: form.base_url, api_key: form.api_key });
      toast.success(`Provider "${editing}" 已保存`);
      setEditing(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const remove = async (name: string) => {
    try {
      await api.deleteProvider(name);
      toast.success(`Provider "${name}" 已删除`);
      setDeleteTarget(null);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "删除失败");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
        <span className="text-sm text-muted">加载中...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <AlertTriangle className="w-8 h-8 text-warning" />
        <p className="text-sm text-muted">{error}</p>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  const providerNames = [...new Set([...PRESET_PROVIDERS, ...Object.keys(providers)])];

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">配置 LLM 提供商的 API Key，添加后即可在车间中使用对应模型。</p>
        <button
          onClick={() => { setEditing("new"); setForm({ base_url: "", api_key: "", show_key: false }); }}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors shrink-0"
        >
          <Plus className="w-4 h-4" /> 添加 Provider
        </button>
      </div>

      {/* Existing providers */}
      <div className="space-y-2">
        {providerNames.map(name => {
          const p = providers[name];
          const isExisting = !!p;
          const isEditing = editing === name;
          const isNew = editing === "new";

          // Only show configured providers or presets
          if (!isExisting && !PRESET_PROVIDERS.includes(name)) return null;

          if (isEditing || (isNew && name === "custom")) {
            return (
              <div key={name} className="bg-surface border border-accent/20 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-accent">{name}</span>
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted">Base URL</label>
                  <input
                    value={form.base_url}
                    onChange={e => setForm(f => ({ ...f, base_url: e.target.value }))}
                    placeholder="https://api.example.com/v1"
                    className="w-full bg-card border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted">API Key</label>
                  <div className="flex gap-2 mt-1">
                    <div className="relative flex-1">
                      <input
                        type={form.show_key ? "text" : "password"}
                        value={form.api_key}
                        onChange={e => setForm(f => ({ ...f, api_key: e.target.value }))}
                        placeholder="sk-..."
                        className="w-full bg-card border border-border rounded-xl px-3 py-2 pr-10 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 font-mono"
                      />
                      <button
                        type="button"
                        onClick={() => setForm(f => ({ ...f, show_key: !f.show_key }))}
                        className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white transition-colors"
                      >
                        {form.show_key ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                      </button>
                    </div>
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={save} disabled={saving} className="flex items-center gap-1.5 px-4 py-2 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-30">
                    {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />} 保存
                  </button>
                  <button onClick={() => setEditing(null)} className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">
                    取消
                  </button>
                </div>
              </div>
            );
          }

          // Display mode
          return (
            <div
              key={name}
              onClick={() => isExisting ? startEdit(name) : setEditing(name)}
              className={`flex items-center justify-between px-4 py-3 rounded-xl border transition-all cursor-pointer ${
                isExisting
                  ? "bg-surface border-border hover:border-accent/20"
                  : "bg-surface/50 border-dashed border-border hover:border-accent/30"
              }`}
            >
              <div className="flex items-center gap-3">
                <div className={`w-2 h-2 rounded-full ${isExisting && p.api_key ? "bg-success" : "bg-muted"}`} />
                <div>
                  <span className="text-sm text-white">{name}</span>
                  <span className="text-[10px] text-muted ml-2">{p?.base_url || "未配置"}</span>
                </div>
              </div>
              <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                {p?.api_key && (
                  <span className="text-[10px] text-success bg-success/10 px-2 py-0.5 rounded">已配置 Key</span>
                )}
                {isExisting && (
                  <button
                    onClick={() => setDeleteTarget(name)}
                    className="text-muted hover:text-warning transition-colors"
                    title="删除"
                  >
                    <Trash2 className="w-3.5 h-3.5" />
                  </button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title="删除 Provider"
          message={`确定要删除 "${deleteTarget}" 的配置吗？使用该 provider 的车间将无法调用模型。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

// ── Tab: Skills ───────────────────────────────────────────

function SkillsTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [skills, setSkills] = useState<{ name: string; description: string; version: string }[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setSkills(await api.listSkills());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try {
      const result = await api.syncSkills();
      toast.success(`已同步 ${result.count} 个技能`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
        <span className="text-sm text-muted">加载技能库...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <AlertTriangle className="w-8 h-8 text-warning" />
        <p className="text-sm text-muted">{error}</p>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">管理 AI 工厂的技能模块。技能为 Agent 提供专业能力，如代码审查、文件操作等。</p>
        <button
          onClick={sync}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          同步
        </button>
      </div>

      {skills.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <Puzzle className="w-10 h-10 text-muted" />
          <p className="text-sm text-muted">尚未发现任何技能文件</p>
          <p className="text-xs text-muted">在 skills/ 目录中放入 Skill.md 文件，然后点击同步</p>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map(s => (
            <div key={s.name} className="flex items-center justify-between bg-surface border border-border rounded-xl px-4 py-3 hover:border-accent/10 transition-colors">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center">
                  <Zap className="w-4 h-4 text-accent" />
                </div>
                <div>
                  <span className="text-sm text-white font-medium">{s.name}</span>
                  <p className="text-xs text-muted mt-0.5">{s.description}</p>
                </div>
              </div>
              <span className="text-[10px] text-muted bg-surface px-2 py-0.5 rounded-full border border-border">v{s.version}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Tools ────────────────────────────────────────────

function ToolsTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [tools, setTools] = useState<{ mcp_servers: unknown[]; profiles: Record<string, unknown> }>({ mcp_servers: [], profiles: {} });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setTools(await api.listTools());
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try {
      const result = await api.syncTools();
      toast.success(`已同步 ${result.count} 个工具`);
      load();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "同步失败");
    } finally {
      setSyncing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2">
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
        <span className="text-sm text-muted">加载工具列表...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <AlertTriangle className="w-8 h-8 text-warning" />
        <p className="text-sm text-muted">{error}</p>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">配置 MCP 服务端和工具 Profile。Agent 通过这些工具获得文件系统、网络搜索、数据库等能力。</p>
        <button
          onClick={sync}
          disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors disabled:opacity-50 shrink-0"
        >
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />
          同步
        </button>
      </div>

      {/* MCP Servers */}
      <div>
        <h3 className="text-sm font-semibold text-white mb-3">MCP 服务端</h3>
        {tools.mcp_servers.length === 0 ? (
          <p className="text-xs text-muted py-6 text-center">暂无 MCP 服务端 — 在 config/mcp_servers.yaml 配置或点击同步</p>
        ) : (
          <div className="space-y-2">
            {tools.mcp_servers.map((s: unknown, i: number) => {
              const server = s as Record<string, unknown>;
              return (
                <div key={i} className="flex items-center justify-between bg-surface border border-border rounded-xl px-4 py-3">
                  <div className="flex items-center gap-3">
                    <Wrench className="w-4 h-4 text-info" />
                    <div>
                      <span className="text-sm text-white">{String(server.name || "未命名")}</span>
                      <p className="text-xs text-muted mt-0.5">{String(server.description || "")}</p>
                    </div>
                  </div>
                  <span className="text-[10px] text-info bg-info/10 px-2 py-0.5 rounded-full">
                    {String(server.transport || "stdio")}
                  </span>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Tab: Plugins ──────────────────────────────────────────

function PluginsTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [plugins, setPlugins] = useState<Record<string, PluginEntry>>({});
  const [loading, setLoading] = useState(true);
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
        <Loader2 className="w-5 h-5 text-accent animate-spin" />
        <span className="text-sm text-muted">加载插件列表...</span>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex flex-col items-center gap-3 py-12">
        <AlertTriangle className="w-8 h-8 text-warning" />
        <p className="text-sm text-muted">{error}</p>
        <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  const entries = Object.values(plugins);

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">Channel 适配器和平台插件。让 AI 工厂接入微信、飞书、钉钉等外部平台。</p>
        <button
          onClick={() => {
            const name = window.prompt("插件名称:");
            if (name) api.savePlugin(name, { enabled: true }).then(() => load()).catch(e => toast.error(e.message));
          }}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors shrink-0"
        >
          <Plus className="w-4 h-4" /> 安装插件
        </button>
      </div>

      {entries.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <Blocks className="w-10 h-10 text-muted" />
          <p className="text-sm text-muted">尚未安装任何插件</p>
          <p className="text-xs text-muted">安装插件以接入外部平台</p>
        </div>
      ) : (
        <div className="space-y-2">
          {entries.map(p => (
            <div key={p.name} className="flex items-center justify-between bg-surface border border-border rounded-xl px-4 py-3">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center ${p.healthy ? "bg-success/10" : "bg-warning/10"}`}>
                  <Shield className={`w-4 h-4 ${p.healthy ? "text-success" : "text-warning"}`} />
                </div>
                <div>
                  <span className="text-sm text-white font-medium">{p.name}</span>
                  <p className="text-xs text-muted mt-0.5">{p.healthy ? "运行中" : "未连接"}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                {/* Toggle */}
                <button
                  onClick={() => toggle(p.name, !p.enabled)}
                  className={`relative w-10 h-5 rounded-full transition-colors ${p.enabled ? "bg-success/30" : "bg-border"}`}
                >
                  <div className={`absolute w-4 h-4 bg-white rounded-full top-0.5 transition-all ${p.enabled ? "left-5" : "left-0.5"}`} />
                </button>
                <button
                  onClick={() => setDeleteTarget(p.name)}
                  className="text-muted hover:text-warning transition-colors"
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

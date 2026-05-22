import { useEffect, useState, useCallback } from "react";
import { Key, Puzzle, Wrench, Blocks, Search, Plus, Trash2, Eye, EyeOff, RefreshCw, Loader2, AlertTriangle, Zap, Shield } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { PluginEntry, SearchConfig } from "../lib/types";

type TabId = "providers" | "search" | "skills" | "tools" | "plugins";

const tabs: { id: TabId; label: string; icon: typeof Key }[] = [
  { id: "providers", label: "LLM Key", icon: Key },
  { id: "search", label: "Web Search", icon: Search },
  { id: "skills", label: "技能库", icon: Puzzle },
  { id: "tools", label: "工具箱", icon: Wrench },
  { id: "plugins", label: "插件", icon: Blocks },
];

const PRESET_PROVIDERS = ["anthropic", "deepseek", "siliconflow", "moonshot", "openai", "custom"];

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
        {tab === "search" && <SearchTab toast={toast} />}
        {tab === "skills" && <SkillsTab toast={toast} />}
        {tab === "tools" && <ToolsTab toast={toast} />}
        {tab === "plugins" && <PluginsTab toast={toast} />}
      </div>
    </div>
  );
}

// ── Tab: LLM Key ─────────────────────────────────────────

function ProvidersTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [providers, setProviders] = useState<Record<string, { provider_type: string; base_url: string; api_key: string; models: string[] }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ base_url: "", api_key: "", show_key: false, models: [] as string[], new_model: "" });
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
    setForm({ base_url: p?.base_url || "", api_key: p?.api_key || "", show_key: false, models: p?.models || [], new_model: "" });
  };

  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      await api.saveProvider(editing, { base_url: form.base_url, api_key: form.api_key, models: form.models });
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
        <p className="text-sm text-muted">配置 LLM 提供商的 API Key，添加后即可在工作区中使用对应模型。</p>
        <button
          onClick={() => { setEditing("new"); setForm({ base_url: "", api_key: "", show_key: false, models: [], new_model: "" }); }}
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
                {/* Model list */}
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted">模型列表</label>
                  <div className="flex flex-wrap gap-1.5 mt-1 mb-2">
                    {form.models.map((m, i) => (
                      <span key={i} className="flex items-center gap-1 px-2 py-0.5 bg-accent/10 text-accent border border-accent/20 rounded-lg text-xs">
                        {m}
                        <button
                          onClick={() => setForm(f => ({ ...f, models: f.models.filter((_, j) => j !== i) }))}
                          className="text-muted hover:text-warning transition-colors"
                        >&times;</button>
                      </span>
                    ))}
                  </div>
                  <div className="flex gap-2">
                    <input
                      value={form.new_model}
                      onChange={e => setForm(f => ({ ...f, new_model: e.target.value }))}
                      onKeyDown={e => {
                        if (e.key === "Enter" && form.new_model.trim()) {
                          setForm(f => ({ ...f, models: [...f.models, f.new_model.trim()], new_model: "" }));
                          e.preventDefault();
                        }
                      }}
                      placeholder="输入模型名或从建议中选择"
                      list={`model-suggestions-${editing}`}
                      className="flex-1 bg-card border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
                    />
                    <datalist id={`model-suggestions-${editing}`}>
                      {_modelSuggestions(editing || "").map(m => <option key={m} value={m} />)}
                    </datalist>
                    <button
                      onClick={() => { if (form.new_model.trim()) setForm(f => ({ ...f, models: [...f.models, f.new_model.trim()], new_model: "" })); }}
                      className="px-3 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors"
                    ><Plus className="w-4 h-4" /></button>
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
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white">{name}</span>
                    <span className="text-[10px] text-muted">{p?.base_url || "未配置"}</span>
                  </div>
                  {p?.models && p.models.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {p.models.map(m => (
                        <span key={m} className="text-[10px] px-1.5 py-0.5 bg-accent/5 text-muted border border-border rounded">{m}</span>
                      ))}
                    </div>
                  )}
                </div>
              </div>
              <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                {p?.api_key && (
                  <span className="text-[10px] text-success bg-success/10 px-2 py-0.5 rounded">已配置 Key</span>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title="删除 Provider"
          message={`确定要删除 "${deleteTarget}" 的配置吗？使用该 provider 的工作区将无法调用模型。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

const PROVIDER_MODEL_SUGGESTIONS: Record<string, string[]> = {
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
  deepseek: ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro", "deepseek-v3"],
  siliconflow: ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen3-235B-A22B", "Qwen/Qwen3-30B-A3B", "Qwen/QwQ-32B", "Pro/zai-org/GLM-4.5"],
  moonshot: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
  openai: ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"],
};

function _modelSuggestions(providerName: string): string[] {
  return PROVIDER_MODEL_SUGGESTIONS[providerName] || [];
}

// ── Tab: Web Search ──────────────────────────────────────

function SearchTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [config, setConfig] = useState<SearchConfig>({
    tavily_api_key: "", brave_api_key: "", searxng_base_url: "",
    active_provider: "tavily", deep_search_enabled: false, max_results: 5,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.getSearchConfig().then(setConfig).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const result = await api.saveSearchConfig(config);
      setConfig(result);
      toast.success("搜索配置已保存");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally { setSaving(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-12 gap-2">
      <Loader2 className="w-5 h-5 text-accent animate-spin" />
      <span className="text-sm text-muted">加载搜索配置...</span>
    </div>
  );

  return (
    <div className="space-y-4">
      <p className="text-sm text-muted">配置 Web 搜索后端。Agent 通过 web_search 工具获取实时信息。</p>

      {/* Provider selector */}
      <div>
        <label className="text-[10px] uppercase tracking-widest text-muted">搜索后端</label>
        <select
          value={config.active_provider}
          onChange={e => setConfig(c => ({ ...c, active_provider: e.target.value }))}
          className="w-full bg-card border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 mt-1"
        >
          <option value="tavily">Tavily</option>
          <option value="brave">Brave Search</option>
          <option value="searxng">SearXNG (自建)</option>
        </select>
      </div>

      {/* Tavily */}
      {config.active_provider === "tavily" && (
        <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2"><Search className="w-4 h-4 text-accent" /><span className="text-sm font-semibold text-white">Tavily Search API</span></div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted">API Key</label>
            <div className="flex gap-2 mt-1">
              <div className="relative flex-1">
                <input
                  type={showKeys["tavily"] ? "text" : "password"}
                  value={config.tavily_api_key}
                  onChange={e => setConfig(c => ({ ...c, tavily_api_key: e.target.value }))}
                  placeholder="tvly-..."
                  className="w-full bg-card border border-border rounded-xl px-3 py-2 pr-10 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 font-mono"
                />
                <button
                  onClick={() => setShowKeys(k => ({ ...k, tavily: !k["tavily"] }))}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white"
                >
                  {showKeys["tavily"] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Brave */}
      {config.active_provider === "brave" && (
        <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2"><Search className="w-4 h-4 text-info" /><span className="text-sm font-semibold text-white">Brave Search API</span></div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted">API Key</label>
            <div className="flex gap-2 mt-1">
              <div className="relative flex-1">
                <input
                  type={showKeys["brave"] ? "text" : "password"}
                  value={config.brave_api_key}
                  onChange={e => setConfig(c => ({ ...c, brave_api_key: e.target.value }))}
                  placeholder="BSA..."
                  className="w-full bg-card border border-border rounded-xl px-3 py-2 pr-10 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 font-mono"
                />
                <button
                  onClick={() => setShowKeys(k => ({ ...k, brave: !k["brave"] }))}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-white"
                >
                  {showKeys["brave"] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* SearXNG */}
      {config.active_provider === "searxng" && (
        <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
          <div className="flex items-center gap-2"><Search className="w-4 h-4 text-warning" /><span className="text-sm font-semibold text-white">SearXNG 自建实例</span></div>
          <div>
            <label className="text-[10px] uppercase tracking-widest text-muted">Base URL</label>
            <input
              value={config.searxng_base_url}
              onChange={e => setConfig(c => ({ ...c, searxng_base_url: e.target.value }))}
              placeholder="http://127.0.0.1:8080"
              className="w-full bg-card border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1"
            />
          </div>
        </div>
      )}

      {/* Common settings */}
      <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm text-white font-medium">深度搜索</span>
            <p className="text-xs text-muted mt-0.5">启用后，Agent 搜索时会同时抓取页面正文进行深度分析</p>
          </div>
          <button
            onClick={() => setConfig(c => ({ ...c, deep_search_enabled: !c.deep_search_enabled }))}
            className={`relative w-10 h-5 rounded-full transition-colors ${config.deep_search_enabled ? "bg-accent/40" : "bg-border"}`}
          >
            <div className={`absolute w-4 h-4 bg-white rounded-full top-0.5 transition-all ${config.deep_search_enabled ? "left-5" : "left-0.5"}`} />
          </button>
        </div>
        <div>
          <label className="text-[10px] uppercase tracking-widest text-muted">单次搜索结果数</label>
          <input
            type="number" min={1} max={20}
            value={config.max_results}
            onChange={e => setConfig(c => ({ ...c, max_results: Math.min(20, Math.max(1, parseInt(e.target.value) || 5)) }))}
            className="w-24 bg-card border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 mt-1"
          />
        </div>
      </div>

      <button onClick={save} disabled={saving}
        className="flex items-center gap-1.5 px-5 py-2.5 bg-accent text-black rounded-xl text-sm font-semibold hover:bg-amber-400 transition-colors disabled:opacity-30"
      >
        {saving && <Loader2 className="w-3.5 h-3.5 animate-spin" />}
        保存配置
      </button>
    </div>
  );
}

// ── Tab: Skills ───────────────────────────────────────────

function SkillsTab({ toast }: { toast: ReturnType<typeof useToast> }) {
  const [skills, setSkills] = useState<import("../lib/types").SkillEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<import("../lib/types").SkillDetail | null>(null);
  const [detailLoading, setDetailLoading] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try { setSkills(await api.listSkills()); }
    catch (err) { setError(err instanceof Error ? err.message : "加载失败"); }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const sync = async () => {
    setSyncing(true);
    try { const result = await api.syncSkills(); toast.success(`发现 ${result.count} 个技能`); load(); }
    catch (err) { toast.error(err instanceof Error ? err.message : "同步失败"); }
    finally { setSyncing(false); }
  };

  const toggleDetail = async (name: string) => {
    if (expanded === name) { setExpanded(null); setDetail(null); return; }
    setExpanded(name); setDetailLoading(true);
    try { setDetail(await api.getSkillDetail(name)); }
    catch { setDetail(null); }
    finally { setDetailLoading(false); }
  };

  if (loading) return (
    <div className="flex items-center justify-center py-12 gap-2">
      <Loader2 className="w-5 h-5 text-accent animate-spin" /><span className="text-sm text-muted">加载技能库...</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center gap-3 py-12">
      <AlertTriangle className="w-8 h-8 text-warning" /><p className="text-sm text-muted">{error}</p>
      <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm"><RefreshCw className="w-3.5 h-3.5" />重试</button>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">从 Anthropic 市场同步 Skill 插件。Agent 通过 Skill 工具调用专业技能。</p>
        <button onClick={sync} disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors disabled:opacity-50 shrink-0">
          <RefreshCw className={`w-4 h-4 ${syncing ? "animate-spin" : ""}`} />同步市场
        </button>
      </div>

      {skills.length === 0 ? (
        <div className="flex flex-col items-center gap-3 py-12">
          <Puzzle className="w-10 h-10 text-muted" />
          <p className="text-sm text-muted">尚未发现任何技能</p>
          <p className="text-xs text-muted">安装 Claude Code 插件后点击「同步市场」</p>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map(s => (
            <div key={s.name}>
              <div onClick={() => toggleDetail(s.name)}
                className={`flex items-center justify-between bg-surface border rounded-xl px-4 py-3 cursor-pointer transition-all hover:border-accent/20 ${expanded === s.name ? "border-accent/30" : "border-border"}`}>
                <div className="flex items-center gap-3 min-w-0">
                  <div className="w-8 h-8 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                    <Zap className="w-4 h-4 text-accent" />
                  </div>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2">
                      <span className="text-sm text-white font-medium truncate">{s.name}</span>
                      <span className={`text-[10px] px-1.5 py-0.5 rounded-full shrink-0 ${s.source === "plugin" ? "bg-info/10 text-info" : "bg-success/10 text-success"}`}>
                        {s.source === "plugin" ? "市场" : "项目"}
                      </span>
                    </div>
                    <p className="text-xs text-muted mt-0.5 truncate">{s.description}</p>
                  </div>
                </div>
                <span className="text-[10px] text-muted shrink-0 ml-2">{s.plugin}</span>
              </div>

              {/* Expanded detail */}
              {expanded === s.name && (
                <div className="bg-card border border-accent/20 border-t-0 rounded-b-xl px-5 py-4 space-y-3">
                  {detailLoading ? (
                    <div className="flex items-center gap-2 py-2"><Loader2 className="w-4 h-4 text-accent animate-spin" /><span className="text-xs text-muted">加载详情...</span></div>
                  ) : detail ? (
                    <>
                      <div className="grid grid-cols-2 gap-2 text-xs">
                        <div><span className="text-muted">全名:</span> <span className="text-white">{detail.full_name}</span></div>
                        <div><span className="text-muted">插件:</span> <span className="text-white">{detail.plugin}</span></div>
                        <div><span className="text-muted">来源:</span> <span className="text-white">{detail.source === "plugin" ? "Anthropic 市场" : "项目本地"}</span></div>
                        {detail.file_path && <div className="col-span-2"><span className="text-muted">路径:</span> <span className="text-white text-[10px] font-mono">{detail.file_path}</span></div>}
                      </div>
                      {detail.body && (
                        <div>
                          <span className="text-[10px] uppercase tracking-widest text-muted">内容</span>
                          <pre className="mt-1 text-xs text-muted bg-surface rounded-xl p-3 max-h-48 overflow-y-auto whitespace-pre-wrap">{detail.body}</pre>
                        </div>
                      )}
                    </>
                  ) : <p className="text-xs text-muted">无法加载详情</p>}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Tab: Tools ────────────────────────────────────────────

function ToolsTab({ toast }: { toast: ReturnType<typeof useToast> }) {
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
      <Loader2 className="w-5 h-5 text-accent animate-spin" /><span className="text-sm text-muted">加载工具列表...</span>
    </div>
  );

  if (error) return (
    <div className="flex flex-col items-center gap-3 py-12">
      <AlertTriangle className="w-8 h-8 text-warning" /><p className="text-sm text-muted">{error}</p>
      <button onClick={load} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm"><RefreshCw className="w-3.5 h-3.5" />重试</button>
    </div>
  );

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">MCP 工具市场。安装 MCP 服务端为 Agent 提供文件、搜索、数据库等能力。</p>
        <button onClick={sync} disabled={syncing}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors disabled:opacity-50 shrink-0">
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
            <div key={s.name} className="flex items-center justify-between bg-surface border border-border rounded-xl px-4 py-3 hover:border-accent/10 transition-colors">
              <div className="flex items-center gap-3 min-w-0">
                <div className="w-8 h-8 rounded-lg bg-info/10 flex items-center justify-center shrink-0">
                  <Wrench className="w-4 h-4 text-info" />
                </div>
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white font-medium">{s.name}</span>
                    {s.category && <span className="text-[10px] px-1.5 py-0.5 rounded-full bg-info/10 text-info">{s.category}</span>}
                  </div>
                  <p className="text-xs text-muted mt-0.5 truncate">{s.description}</p>
                </div>
              </div>
              {s.install_command && (
                <code className="text-[10px] text-muted bg-surface px-2 py-1 rounded font-mono shrink-0 ml-2 truncate max-w-[200px]">{s.install_command}</code>
              )}
            </div>
          ))}
        </div>
      )}
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
        <p className="text-sm text-muted">Channel 适配器和平台插件。让 Nexus AI Works 接入微信、飞书、钉钉等外部平台。</p>
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

import { useEffect, useState, useCallback } from "react";
import { Plus, Eye, EyeOff, RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";
import { ConfirmDialog } from "../ConfirmDialog";

const PRESET_PROVIDERS = ["anthropic", "deepseek", "siliconflow", "moonshot", "openai", "custom"];

const PROVIDER_MODEL_SUGGESTIONS: Record<string, string[]> = {
  anthropic: ["claude-sonnet-4-6", "claude-opus-4-7", "claude-haiku-4-5"],
  deepseek: ["deepseek-chat", "deepseek-reasoner", "deepseek-v4-pro", "deepseek-v3"],
  siliconflow: ["deepseek-ai/DeepSeek-V3", "deepseek-ai/DeepSeek-R1", "deepseek-ai/DeepSeek-V3-0324", "Qwen/Qwen3-235B-A22B", "Qwen/Qwen3-30B-A3B", "Qwen/QwQ-32B", "Pro/zai-org/GLM-4.5"],
  moonshot: ["moonshot-v1-8k", "moonshot-v1-32k", "moonshot-v1-128k"],
  openai: ["gpt-5", "gpt-5-mini", "gpt-4o", "gpt-4o-mini"],
};

function modelSuggestions(providerName: string): string[] {
  return PROVIDER_MODEL_SUGGESTIONS[providerName] || [];
}

export function ProvidersTab({ toast }: { toast: ToastFn }) {
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

      <div className="space-y-2">
        {providerNames.map(name => {
          const p = providers[name];
          const isExisting = !!p;
          const isEditing = editing === name;
          const isNew = editing === "new";

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
                      {modelSuggestions(editing || "").map(m => <option key={m} value={m} />)}
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

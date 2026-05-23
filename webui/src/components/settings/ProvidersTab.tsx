import { useEffect, useState, useCallback } from "react";
import { Plus, Eye, EyeOff, RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";
import { ConfirmDialog } from "../ConfirmDialog";

const PRESET_PROVIDERS = ["anthropic", "deepseek", "siliconflow", "moonshot", "openai", "custom"];

function categorizeModels(models: string[]): Record<string, string[]> {
  const cats: Record<string, string[]> = {};
  for (const m of models) {
    const lower = m.toLowerCase();
    let cat = "其他";
    if (/(vl|vision|omni|image|kolors)/.test(lower)) cat = "多模态";
    else if (/(coder|code|deepseek.*v3|deepseek.*r1|qwen\d|qwen3[.\d]|glm|kimi|ling|seed|hunyuan|step|minimax)/.test(lower)) cat = "对话";
    else if (/(reranker|rerank|bge|embed)/.test(lower)) cat = "检索";
    else if (/(speech|asr|tts|cosy|sensevoice|audio)/.test(lower)) cat = "语音";
    else if (/(ocr|paddle)/.test(lower)) cat = "OCR";
    else if (/(wan|video)/.test(lower)) cat = "视频";
    (cats[cat] ??= []).push(m);
  }
  return cats;
}


export function ProvidersTab({ toast }: { toast: ToastFn }) {
  const [providers, setProviders] = useState<Record<string, { provider_type: string; base_url: string; api_key: string; models: string[] }>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [form, setForm] = useState({ name: "", provider_type: "", base_url: "", api_key: "", show_key: false, models: [] as string[], new_model: "" });
  const [keyModified, setKeyModified] = useState(false);
  const [saving, setSaving] = useState(false);
  const [syncing, setSyncing] = useState<string | null>(null);
  const [deleteTarget, setDeleteTarget] = useState<string | null>(null);
  const [expandedCats, setExpandedCats] = useState<Set<string>>(new Set(['对话', '多模态']));
  const [defaultModel, setDefaultModel] = useState("");
  const [defaultModelLoading, setDefaultModelLoading] = useState(false);

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
    setForm({ name, provider_type: p?.provider_type || name, base_url: p?.base_url || "", api_key: p?.api_key || "", show_key: false, models: p?.models || [], new_model: "" });
    setKeyModified(false);
    if (p?.api_key) syncModels(name);
  };

  const save = async () => {
    if (!editing) return;
    const name = editing === "new" ? form.name : editing;
    if (!name.trim()) { toast.error("请输入 Provider 名称"); return; }
    setSaving(true);
    try {
      const isNew = !providers[name];
      const data: Record<string, unknown> = { provider_type: form.provider_type || name, base_url: form.base_url, models: form.models };
      if (isNew || keyModified) data.api_key = form.api_key;
      await api.saveProvider(name, data);
      toast.success(`Provider "${name}" 已保存`);
      setEditing(null);
      load();
      if (isNew && form.api_key) { syncModels(name); }
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

  const syncModels = async (name: string) => {
    setSyncing(name);
    try {
      const result = await api.syncProviderModels(name);
      if (result.error) {
        toast.error(`${name}: ${result.error}`);
      } else {
        toast.success(`${name}: 已同步 ${result.updated} 个模型`);
        await load();
        if (editing === name) setForm(f => ({ ...f, models: result.models }));
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "同步失败");
    } finally {
      setSyncing(null);
    }
  };

  const loadDefaultModel = useCallback(async () => {
    try {
      const prefs = await api.getPreferences();
      setDefaultModel((prefs as Record<string, string>).default_model || "");
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { loadDefaultModel(); }, [loadDefaultModel]);

  const saveDefaultModel = async (model: string) => {
    setDefaultModelLoading(true);
    try {
      await api.savePreferences({ default_model: model });
      toast.success(model ? "默认模型已设置" : "默认模型已清除");
    } catch {
      toast.error("保存失败");
    } finally {
      setDefaultModelLoading(false);
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
      {/* Default Model Selector */}
      <div className="bg-surface border border-border rounded-xl p-4 space-y-3">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-white">默认模型</span>
          <span className="text-[10px] text-muted">创建项目/Agent 未选模型时使用</span>
        </div>
        <div className="flex items-center gap-3">
          <select
            value={defaultModel}
            onChange={e => { const v = e.target.value; setDefaultModel(v); saveDefaultModel(v); }}
            disabled={defaultModelLoading}
            className="flex-1 bg-card border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 disabled:opacity-50"
          >
            <option value="">自动选择（首个有 Key 的 Provider）</option>
            {Object.entries(providers).map(([pname, cfg]) => {
              if (!cfg.models?.length) return null;
              const chatModels = cfg.models.filter(m => {
                const lower = m.toLowerCase();
                return !/(reranker|rerank|embedding|bge|speech|asr|cosyvoice|sensevoice|ocr|paddle|kolors|wan|image-edit|image-turbo|z-image|mt-|captioner|tts|whisper|moderation|dall-e)/.test(lower);
              });
              if (!chatModels.length) return null;
              return (
                <optgroup key={pname} label={`${pname} ${cfg.api_key ? '✓' : '(未配置 Key)'}`}>
                  {chatModels.map(m => (
                    <option key={`${pname}/${m}`} value={`${pname}/${m}`}>{m.replace(/^Pro\//, '').replace(/^LoRA\//, '')}</option>
                  ))}
                </optgroup>
              );
            })}
          </select>
          {defaultModelLoading && <Loader2 className="w-4 h-4 text-accent animate-spin shrink-0" />}
          <button
            onClick={() => loadDefaultModel()}
            className="shrink-0 p-2 text-muted hover:text-accent transition-colors rounded-lg hover:bg-white/5"
            title="刷新"
          ><RefreshCw className="w-4 h-4" /></button>
        </div>
      </div>

      <div className="flex items-center justify-between">
        <p className="text-sm text-muted">配置 LLM 提供商的 API Key，添加后即可在项目中使用对应模型。</p>
        <button
          onClick={() => { setEditing("new"); setForm({ name: "", provider_type: "", base_url: "", api_key: "", show_key: false, models: [], new_model: "" }); setKeyModified(false); }}
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
            const editingName = isNew ? "新 Provider" : name;
            return (
              <div key={name} className="bg-surface border border-accent/20 rounded-xl p-4 space-y-3">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-accent">{editingName}</span>
                </div>
                {isNew && (
                  <>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted">名称</label>
                  <input
                    value={form.name}
                    onChange={e => setForm(f => ({ ...f, name: e.target.value }))}
                    placeholder="my-provider"
                    className="w-full bg-card border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1"
                  />
                </div>
                <div>
                  <label className="text-[10px] uppercase tracking-widest text-muted">类型</label>
                  <select
                    value={form.provider_type}
                    onChange={e => setForm(f => ({ ...f, provider_type: e.target.value }))}
                    className="w-full bg-card border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 mt-1"
                  >
                    <option value="">自定义 (OpenAI 兼容)</option>
                    <option value="anthropic">anthropic</option>
                    <option value="deepseek">deepseek</option>
                    <option value="siliconflow">siliconflow</option>
                    <option value="moonshot">moonshot</option>
                    <option value="openai">openai</option>
                  </select>
                </div>
                  </>
                )}
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
                        onChange={e => { setForm(f => ({ ...f, api_key: e.target.value })); setKeyModified(true); }}
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
                  <div className="flex items-center justify-between">
                    <label className="text-[10px] uppercase tracking-widest text-muted">模型列表</label>
                    <button
                      type="button"
                      onClick={() => syncModels(editing || "")}
                      disabled={syncing === (editing || "")}
                      className="flex items-center gap-1 text-[10px] text-accent hover:text-amber-300 transition-colors disabled:opacity-30"
                    >
                      <RefreshCw className={`w-3 h-3 ${syncing === (editing || "") ? "animate-spin" : ""}`} /> 从 API 同步
                    </button>
                  </div>
                  {form.models.length > 0 && (() => {
                      const cats = categorizeModels(form.models);
                      return (
                        <div className="mt-1 mb-2 space-y-1 max-h-[300px] overflow-auto">
                          {Object.entries(cats).map(([cat, items]) => {
                            const expanded = expandedCats.has(cat);
                            return (
                              <div key={cat}>
                                <button
                                  type="button"
                                  onClick={() => {
                                    setExpandedCats(prev => {
                                      const next = new Set(prev);
                                      expanded ? next.delete(cat) : next.add(cat);
                                      return next;
                                    });
                                  }}
                                  className="flex items-center gap-1 text-[10px] text-muted hover:text-white transition-colors w-full text-left py-0.5"
                                >
                                  <span className="text-[10px]">{expanded ? '▼' : '▶'}</span>
                                  {cat} ×{items.length}
                                </button>
                                {expanded && (
                                  <div className="flex flex-wrap gap-1.5 pl-4">
                                    {items.map(m => {
                                      const fi = form.models.indexOf(m);
                                      return (
                                        <span key={m} className="flex items-center gap-1 px-2 py-0.5 bg-accent/10 text-accent border border-accent/20 rounded-lg text-xs">
                                          {m.replace(/^Pro\//, '').replace(/^LoRA\//, '')}
                                          <button
                                            onClick={() => setForm(f => ({ ...f, models: f.models.filter((_, j) => j !== fi) }))}
                                            className="text-muted hover:text-warning transition-colors"
                                          >&times;</button>
                                        </span>
                                      );
                                    })}
                                  </div>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      );
                    })()}
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
                      placeholder="手动添加模型名..."
                      className="flex-1 bg-card border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
                    />
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
                  <div className="flex items-center gap-2">
                    {p?.models && p.models.length > 0 && (() => {
                      const cats = categorizeModels(p.models);
                      const catNames = Object.keys(cats);
                      const showCount = p.models.length > 8 ? 5 : p.models.length;
                      return (
                        <div className="mt-1 space-y-1">
                          <span className="text-[10px] text-muted">
                            {p.models.length} 个模型
                            {catNames.map(c => ` · ${c}×${cats[c].length}`).join('')}
                          </span>
                          <div className="flex flex-wrap gap-1">
                            {p.models.slice(0, showCount).map(m => (
                              <span key={m} className="text-[10px] px-1.5 py-0.5 bg-accent/5 text-muted border border-border rounded">{m.replace(/^Pro\//, '').replace(/^LoRA\//, '')}</span>
                            ))}
                            {p.models.length > showCount && (
                              <span className="text-[10px] px-1.5 py-0.5 text-muted">+{p.models.length - showCount} ...</span>
                            )}
                          </div>
                        </div>
                      );
                    })()}
                    {isExisting && (
                      <button
                        onClick={e => { e.stopPropagation(); syncModels(name); }}
                        disabled={syncing === name}
                        className="shrink-0 p-1 text-muted hover:text-accent transition-colors disabled:opacity-30"
                        title="从 API 同步模型列表"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${syncing === name ? "animate-spin" : ""}`} />
                      </button>
                    )}
                  </div>
                </div>
              </div>
              <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                {p?.api_key && (
                  <span className="text-[10px] text-success bg-success/10 px-2 py-0.5 rounded">已配置 Key</span>
                )}
                {isExisting && !PRESET_PROVIDERS.includes(name) && (
                  <button
                    onClick={e => { e.stopPropagation(); setDeleteTarget(name); }}
                    className="text-[10px] text-muted hover:text-warning transition-colors"
                    title="删除"
                  >删除</button>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {deleteTarget && (
        <ConfirmDialog
          title="删除 Provider"
          message={`确定要删除 "${deleteTarget}" 的配置吗？使用该 provider 的项目将无法调用模型。`}
          confirmLabel="删除"
          onConfirm={() => remove(deleteTarget)}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

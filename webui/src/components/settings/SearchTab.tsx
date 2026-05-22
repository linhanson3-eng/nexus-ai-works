import { useEffect, useState } from "react";
import { Search, Eye, EyeOff, Loader2 } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";
import type { SearchConfig } from "../../lib/types";

export function SearchTab({ toast }: { toast: ToastFn }) {
  const [config, setConfig] = useState<SearchConfig>({
    tavily_api_key: "", brave_api_key: "", searxng_base_url: "",
    active_provider: "tavily", deep_search_enabled: false, max_results: 5,
  });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [showKeys, setShowKeys] = useState<Record<string, boolean>>({});

  useEffect(() => {
    api.getSearchConfig().then((data: unknown) => setConfig(data as SearchConfig)).catch((err) => { console.warn("加载搜索配置失败", err); }).finally(() => setLoading(false));
  }, []);

  const save = async () => {
    setSaving(true);
    try {
      const result = await api.saveSearchConfig(config);
      setConfig(result as SearchConfig);
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

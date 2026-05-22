import { useEffect, useState, useCallback } from "react";
import { Puzzle, Zap, RefreshCw, Loader2, AlertTriangle } from "lucide-react";
import { api } from "../../lib/api";
import type { ToastFn } from "../Toast";
import type { SkillEntry, SkillDetail } from "../../lib/types";

export function SkillsTab({ toast }: { toast: ToastFn }) {
  const [skills, setSkills] = useState<SkillEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [syncing, setSyncing] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);
  const [detail, setDetail] = useState<SkillDetail | null>(null);
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
    catch (err) { console.warn("加载技能详情失败", err); setDetail(null); }
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

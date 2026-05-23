import { useState, useEffect, useCallback } from "react";
import { Package, Download, Upload, X, Loader2 } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { useToast } from "./Toast";
import type { Workshop } from "../lib/types";

export function ModuleFactory() {
  const toast = useToast();
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [loading, setLoading] = useState(true);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importName, setImportName] = useState("");
  const [importing, setImporting] = useState(false);

  const loadWorkshops = useCallback(async () => {
    setLoading(true);
    try { setWorkshops(await api.listWorkshops()); } catch {}
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadWorkshops(); }, [loadWorkshops]);

  const exportWorkspace = async (wsName: string) => {
    try {
      const res = await fetch(`/api/workshops/${wsName}/export`, { method: "POST", headers: { ...getAuthHeaders() }, credentials: "include" });
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${wsName}.nexus.zip`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`已导出`);
    } catch { toast.error("导出失败"); }
  };

  const removeWorkspace = async (wsName: string) => {
    try { await api.deleteWorkshop(wsName); toast.success("已卸载"); loadWorkshops(); }
    catch { toast.error("卸载失败"); }
  };

  const handleFileSelect = (file: File) => {
    setImportFile(file);
    setImportName(file.name.replace(/\.(zip|nexus)$/i, ""));
  };

  const confirmImport = async () => {
    if (!importFile || !importName.trim()) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      formData.append("name", importName.trim());
      const res = await fetch("/api/workshops/import", { method: "POST", headers: { ...getAuthHeaders() }, credentials: "include", body: formData });
      if (!res.ok) throw new Error("导入失败");
      toast.success("已导入");
      setImportFile(null);
      loadWorkshops();
    } catch { toast.error("导入失败"); }
    finally { setImporting(false); }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64 gap-2"><Loader2 className="w-5 h-5 text-accent animate-spin" /><span className="text-sm text-muted">加载中...</span></div>;
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-black tracking-tight text-white">模版仓库</h1>
          <p className="text-sm text-muted mt-1">导出 / 导入 .nexus 模块包</p>
        </div>
        <label className="flex items-center gap-2 px-4 py-2 bg-info/10 text-info border border-info/20 rounded-xl text-sm font-medium hover:bg-info/20 transition-colors cursor-pointer">
          <Upload className="w-4 h-4" /> 导入模块
          <input type="file" accept=".zip,.nexus" className="hidden"
            onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileSelect(f); e.target.value = ""; } }} />
        </label>
      </div>

      {workshops.length === 0 ? (
        <div className="flex flex-col items-center justify-center py-20 gap-4">
          <Package className="w-12 h-12 text-muted/30" />
          <p className="text-sm text-muted">暂无模块。导入 .nexus 包开始使用。</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-3 max-lg:grid-cols-1">
          {workshops.map(w => (
            <div key={w.name} className="bg-card border border-border rounded-[16px] p-4 hover:border-accent/20 transition-colors group">
              <div className="flex items-start justify-between">
                <div className="min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <Package className="w-4 h-4 text-accent shrink-0" />
                    <h3 className="text-white font-semibold truncate">{w.name}</h3>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted">
                    <span>{w.agent_count} agents</span>
                    <span>·</span>
                    <span>{w.workflow_name}</span>
                  </div>
                </div>
                <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                  <button onClick={() => exportWorkspace(w.name)} className="p-1.5 rounded-lg text-muted hover:text-info transition-colors" title="导出">
                    <Download className="w-3 h-3" />
                  </button>
                  <button onClick={() => removeWorkspace(w.name)} className="p-1.5 rounded-lg text-muted/30 hover:text-warning transition-colors" title="卸载">
                    <X className="w-3 h-3" />
                  </button>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Import dialog */}
      {importFile && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setImportFile(null)}>
          <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <h2 className="text-lg font-bold text-white">导入模块</h2>
            <p className="text-xs text-muted">{importFile.name}</p>
            <input value={importName} onChange={e => setImportName(e.target.value)}
              placeholder="项目名称"
              className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30" />
            <div className="flex justify-end gap-2">
              <button onClick={() => setImportFile(null)} className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">取消</button>
              <button onClick={confirmImport} disabled={importing || !importName.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30">
                {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : null} 确认导入
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

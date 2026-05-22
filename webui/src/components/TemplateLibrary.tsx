import { useState, useEffect } from "react";
import { api } from "../lib/api";
import type { LibraryEntry } from "../lib/types";

const TYPE_LABELS: Record<string, string> = {
  workflow: "生产方案",
  agent: "智能体配置",
  role: "岗位规格",
};

export function TemplateLibrary() {
  const [activeType, setActiveType] = useState("workflow");
  const [entries, setEntries] = useState<LibraryEntry[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState<LibraryEntry | null>(null);

  const load = async () => {
    setLoading(true);
    try {
      const data = await api.listLibrary(activeType, search);
      setEntries(data);
    } catch {
      setEntries([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, [activeType, search]);

  const handleInstall = async (entry: LibraryEntry) => {
    const workshop = prompt("目标车间名称:");
    if (!workshop) return;
    try {
      await api.installFromLibrary(entry.entry_type, entry.name, workshop);
      alert(`已安装到 ${workshop}`);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert(`安装失败: ${msg}`);
    }
  };

  const handleDelete = async (entry: LibraryEntry) => {
    if (!confirm(`确定删除「${entry.name}」?`)) return;
    try {
      await api.deleteFromLibrary(entry.entry_type, entry.name);
      if (selected?.id === entry.id) setSelected(null);
      load();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      alert(`删除失败: ${msg}`);
    }
  };

  return (
    <div className="p-6 max-w-5xl mx-auto">
      <h1 className="text-2xl font-bold mb-4">我的模板</h1>

      <div className="flex gap-2 mb-4">
        {["workflow", "agent", "role"].map((t) => (
          <button
            key={t}
            onClick={() => { setActiveType(t); setSelected(null); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              activeType === t
                ? "bg-amber-500 text-black"
                : "bg-zinc-800 text-zinc-400 hover:text-white"
            }`}
          >
            {TYPE_LABELS[t]}
          </button>
        ))}
      </div>

      <input
        type="text"
        placeholder="搜索模板..."
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        className="w-full px-4 py-2 mb-4 bg-zinc-900 border border-zinc-700 rounded-lg text-white placeholder-zinc-500 focus:outline-none focus:border-amber-500"
      />

      <div className="flex gap-6">
        <div className="flex-1 space-y-2">
          {loading ? (
            <p className="text-zinc-500">加载中...</p>
          ) : entries.length === 0 ? (
            <p className="text-zinc-500">
              暂无模板。使用 <code className="text-amber-400 bg-zinc-800 px-1 rounded">library save</code> 命令或在车间中入库。
            </p>
          ) : (
            entries.map((e) => (
              <div
                key={e.id}
                onClick={() => setSelected(e)}
                className={`p-4 rounded-lg border cursor-pointer transition-colors ${
                  selected?.id === e.id
                    ? "border-amber-500 bg-zinc-800"
                    : "border-zinc-800 bg-zinc-900 hover:border-zinc-700"
                }`}
              >
                <div className="flex items-center justify-between">
                  <span className="font-medium text-white">{e.name}</span>
                  <span className="text-xs text-zinc-500">{e.version}</span>
                </div>
                {e.description && (
                  <p className="text-sm text-zinc-400 mt-1">{e.description}</p>
                )}
                <div className="flex gap-2 mt-2">
                  <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-400">
                    {e.category}
                  </span>
                  {e.source_workshop && (
                    <span className="text-xs px-2 py-0.5 rounded bg-zinc-800 text-zinc-500">
                      {e.source_workshop}
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {selected && (
          <div className="w-80 flex-shrink-0">
            <div className="p-4 rounded-lg border border-zinc-800 bg-zinc-900 sticky top-4">
              <h2 className="text-lg font-bold text-white mb-2">{selected.name}</h2>
              <p className="text-sm text-zinc-400 mb-3">{selected.description || "无说明"}</p>
              <div className="flex flex-wrap gap-1 mb-3">
                {selected.tags.map((t) => (
                  <span key={t} className="text-xs px-2 py-0.5 rounded bg-amber-900/30 text-amber-400">
                    {t}
                  </span>
                ))}
              </div>
              <div className="text-xs text-zinc-500 space-y-1 mb-4">
                <p>分类: {selected.category}</p>
                <p>版本: {selected.version}</p>
                {selected.source_workshop && <p>来源: {selected.source_workshop}</p>}
                <p>入库: {selected.created_at}</p>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => handleInstall(selected)}
                  className="flex-1 px-3 py-2 bg-amber-500 text-black rounded-lg text-sm font-medium hover:bg-amber-400 transition-colors"
                >
                  安装
                </button>
                <button
                  onClick={() => handleDelete(selected)}
                  className="px-3 py-2 bg-red-900/30 text-red-400 rounded-lg text-sm hover:bg-red-900/50 transition-colors"
                >
                  删除
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

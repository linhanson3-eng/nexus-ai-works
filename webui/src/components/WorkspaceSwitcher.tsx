import { useState, useEffect, useCallback, useRef } from "react";
import { Folder, Plus, Check, ChevronDown } from "lucide-react";
import { api } from "../lib/api";

interface Workshop {
  name: string;
  workspace: string;
}

export function WorkspaceSwitcher({
  current,
  onChange,
}: {
  current: string;
  onChange: (name: string) => void;
}) {
  const [open, setOpen] = useState(false);
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [creating, setCreating] = useState(false);
  const [newName, setNewName] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    try {
      const list = await api.listWorkshops();
      setWorkshops(list);
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  // Close on outside click
  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open]);

  const handleCreate = useCallback(async () => {
    const name = newName.trim();
    if (!name) return;
    try {
      await api.createWorkshop(name);
      setNewName("");
      setCreating(false);
      await load();
      onChange(name);
      setOpen(false);
    } catch { /* ignore */ }
  }, [newName, load, onChange]);

  return (
    <div className="px-3 pt-3 pb-2 relative" ref={ref}>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium
          bg-bg-300 text-text-100 hover:bg-bg-400 transition-colors"
        style={{ background: "hsl(var(--bg-300))" }}
      >
        <Folder className="w-4 h-4 shrink-0 text-text-200" />
        <span className="truncate flex-1 text-left">{current}</span>
        <ChevronDown className={`w-3.5 h-3.5 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute left-3 right-3 top-full z-50 mt-1 bg-bg-000 border border-border rounded-lg shadow-lg py-1"
          style={{ background: "hsl(var(--bg-000))" }}>
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-text-300">
            项目
          </div>
          {workshops.map((w) => (
            <button
              key={w.name}
              onClick={() => { onChange(w.name); setOpen(false); }}
              className={`flex items-center gap-2 w-full px-3 py-1.5 text-sm transition-colors hover:bg-bg-200 ${
                w.name === current ? "text-text-000 font-medium" : "text-text-200"
              }`}
            >
              <Folder className="w-3.5 h-3.5 text-text-300 shrink-0" />
              <span className="truncate flex-1 text-left">{w.name}</span>
              {w.name === current && <Check className="w-3.5 h-3.5 text-accent-000 shrink-0" />}
            </button>
          ))}

          <div className="border-t border-border mt-1 pt-1">
            {creating ? (
              <div className="px-3 py-1.5 flex items-center gap-2">
                <input
                  autoFocus
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === "Enter") handleCreate();
                    if (e.key === "Escape") { setCreating(false); setNewName(""); }
                  }}
                  placeholder="项目名称..."
                  className="flex-1 bg-bg-100 border border-border rounded-md px-2 py-1 text-xs text-text-000 placeholder:text-text-300 outline-none focus:border-accent-000"
                />
                <button
                  onClick={handleCreate}
                  className="text-xs px-2 py-1 bg-accent-000 text-white rounded-md"
                  style={{ background: "hsl(var(--accent-000))" }}
                >
                  创建
                </button>
              </div>
            ) : (
              <button
                onClick={() => { setCreating(true); setNewName(""); }}
                className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-text-200 hover:bg-bg-200 transition-colors"
              >
                <Plus className="w-3.5 h-3.5" />
                新建项目
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

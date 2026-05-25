import { useState, useEffect, useRef } from "react";
import { Search, Bot, GitBranch, Braces } from "lucide-react";

interface Props {
  open: boolean;
  onClose: () => void;
  onSelect: (type: string, label: string) => void;
}

const ALL_NODES = [
  { type: "agent", label: "Agent 执行", icon: Bot, desc: "选择一个 Agent 执行任务" },
  { type: "condition", label: "条件判断", icon: GitBranch, desc: "判断条件，分流到不同分支" },
  { type: "transform", label: "代码转换", icon: Braces, desc: "执行代码或数据转换" },
];

export function NodeSearchDialog({ open, onClose, onSelect }: Props) {
  const [query, setQuery] = useState("");
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery("");
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const filtered = ALL_NODES.filter(
    (n) =>
      !query ||
      n.label.includes(query) ||
      n.type.includes(query) ||
      n.desc.includes(query)
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Escape") {
      onClose();
    } else if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === "Enter" && filtered[selectedIndex]) {
      const n = filtered[selectedIndex];
      onSelect(n.type, n.label);
      onClose();
    }
  };

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center pt-[20vh]"
      onClick={onClose}
    >
      <div
        className="w-full max-w-md bg-card border border-border rounded-xl shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Search input */}
        <div className="flex items-center gap-3 px-4 py-3 border-b border-border">
          <Search className="w-4 h-4 text-muted-foreground shrink-0" />
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="搜索节点类型..."
            className="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground/50"
          />
          <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">
            esc
          </kbd>
        </div>

        {/* Results */}
        <div className="max-h-64 overflow-auto p-2">
          {filtered.map((n, i) => (
            <button
              key={n.type}
              onClick={() => {
                onSelect(n.type, n.label);
                onClose();
              }}
              className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-left transition-colors ${
                i === selectedIndex
                  ? "bg-accent border border-ring/30"
                  : "hover:bg-muted border border-transparent"
              }`}
            >
              <n.icon
                className={`w-4 h-4 shrink-0 ${
                  i === selectedIndex
                    ? "text-primary"
                    : "text-muted-foreground"
                }`}
              />
              <div>
                <div className="text-sm font-medium">{n.label}</div>
                <div className="text-[10px] text-muted-foreground">
                  {n.desc}
                </div>
              </div>
            </button>
          ))}

          {filtered.length === 0 && (
            <p className="text-xs text-muted-foreground/40 text-center py-6">
              无匹配节点
            </p>
          )}
        </div>

        {/* Footer hint */}
        <div className="px-4 py-2 border-t border-border flex items-center gap-3 text-[10px] text-muted-foreground/50">
          <span>↑↓ 导航</span>
          <span>↵ 选择</span>
          <span>esc 关闭</span>
        </div>
      </div>
    </div>
  );
}

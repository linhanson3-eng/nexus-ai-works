import { type FormEvent, type DragEvent, useRef, useState, useEffect, useCallback } from "react";
import { Send, Square, Paperclip, ChevronDown, Brain, Search, Check } from "lucide-react";
import { Button } from "@/components/ui/button";

interface Attachment {
  name: string;
  type: string;
  dataUrl?: string;
  size: number;
}

interface ProviderGroup {
  name: string;
  hasKey: boolean;
  models: string[];
}

const REASONING_EFFORTS = ["", "low", "medium", "high", "xhigh"] as const;
const REASONING_LABELS: Record<string, string> = {
  "": "关闭推理", low: "低", medium: "中", high: "高", xhigh: "极高",
};
const REASONING_MODEL_KEYWORDS = [
  "gpt-5", "gpt-4", "o1", "o3", "o4", "claude-opus",
  "claude-sonnet-4-6", "deepseek-reasoner", "deepseek-r1",
  "gemini-thinking", "qwq", "glm-z1",
];

function supportsReasoning(model: string): boolean {
  return REASONING_MODEL_KEYWORDS.some((k) => model.toLowerCase().includes(k));
}

interface ChatInputProps {
  input: string;
  setInput: (v: string) => void;
  loading: boolean;
  workshops: { name: string }[];
  activeWs: string;
  setActiveWs: (v: string) => void;
  model: string;
  setModel: (v: string) => void;
  reasoningEffort: string;
  setReasoningEffort: (v: string) => void;
  chatProviderGroups: ProviderGroup[];
  attachments: Attachment[];
  removeAttachment: (i: number) => void;
  onSend: () => void;
  onCancel: () => void;
  onFileSelect: (files: FileList | null) => void;
}

function ModelCombobox({
  value,
  onChange,
  groups,
  onSelectEnd,
}: {
  value: string;
  onChange: (v: string) => void;
  groups: ProviderGroup[];
  onSelectEnd?: () => void;
}) {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const containerRef = useRef<HTMLDivElement>(null);

  const close = useCallback(() => {
    setOpen(false);
    setQuery("");
    onSelectEnd?.();
  }, [onSelectEnd]);

  useEffect(() => {
    if (!open) return;
    const handler = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) close();
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [open, close]);

  const q = query.toLowerCase();
  const filteredGroups = groups.map((g) => ({
    ...g,
    models: g.models.filter((m) => !q || m.toLowerCase().includes(q) || g.name.toLowerCase().includes(q)),
  })).filter((g) => g.models.length > 0);

  const hasResults = filteredGroups.length > 0;

  const displayLabel = value
    ? value.split("/").pop()?.replace(/^Pro\//, "").replace(/^LoRA\//, "") ?? "自动"
    : "自动";

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1 bg-background border border-border hover:border-ring/30 rounded-md pl-2 pr-1.5 py-1 text-[11px] text-muted-foreground transition-colors max-w-[120px] truncate"
      >
        <span className="truncate">{displayLabel}</span>
        <ChevronDown className={`w-2.5 h-2.5 text-muted-foreground/40 shrink-0 transition-transform ${open ? "rotate-180" : ""}`} />
      </button>

      {open && (
        <div className="absolute bottom-full mb-1 left-0 w-64 bg-card border border-border rounded-lg shadow-lg z-50 overflow-hidden">
          {/* Search */}
          <div className="flex items-center gap-1.5 px-3 py-2 border-b border-border">
            <Search className="w-3 h-3 text-muted-foreground/50 shrink-0" />
            <input
              autoFocus
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="搜索模型..."
              className="flex-1 bg-transparent border-none outline-none text-xs text-foreground placeholder:text-muted-foreground/50"
            />
          </div>

          {/* Options */}
          <div className="max-h-60 overflow-auto py-1">
            <button
              type="button"
              onClick={() => { onChange(""); close(); }}
              className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent transition-colors ${!value ? "text-primary" : "text-foreground/80"}`}
            >
              <Check className={`w-3 h-3 shrink-0 ${!value ? "opacity-100" : "opacity-0"}`} />
              自动选择
            </button>

            {!hasResults && <p className="px-3 py-2 text-xs text-muted-foreground">无匹配模型</p>}

            {filteredGroups.map((g) => (
              <div key={g.name}>
                <div className="px-3 py-1 text-[10px] text-muted-foreground/50 uppercase tracking-wider">
                  {g.name} {g.hasKey ? "" : "· 未配置"}
                </div>
                {g.models.map((m) => {
                  const fullValue = `${g.name}/${m}`;
                  const selected = value === fullValue;
                  return (
                    <button
                      key={fullValue}
                      type="button"
                      onClick={() => { onChange(fullValue); close(); }}
                      className={`w-full flex items-center gap-2 px-3 py-1.5 text-xs hover:bg-accent transition-colors ${selected ? "text-primary" : "text-foreground/80"}`}
                    >
                      <Check className={`w-3 h-3 shrink-0 ${selected ? "opacity-100" : "opacity-0"}`} />
                      {m.replace(/^Pro\//, "").replace(/^LoRA\//, "")}
                    </button>
                  );
                })}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}

export function ChatInput({
  input, setInput, loading, workshops, activeWs, setActiveWs,
  model, setModel, reasoningEffort, setReasoningEffort,
  chatProviderGroups, attachments, removeAttachment,
  onSend, onCancel, onFileSelect,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if ((!text && !attachments.length) || loading) return;
    onSend();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const showReasoning = supportsReasoning(model);

  return (
    <div className="shrink-0 pt-3 border-t border-border">
      {attachments.length > 0 && (
        <div className="flex gap-2 flex-wrap pb-2">
          {attachments.map((a, i) => (
            <div key={i} className="relative group bg-muted border border-border rounded-md overflow-hidden">
              {a.type === "image" && a.dataUrl ? (
                <div className="w-14 h-14"><img src={a.dataUrl} alt={a.name} className="w-full h-full object-cover" /></div>
              ) : (
                <div className="w-14 h-14 flex items-center justify-center text-[10px] text-muted-foreground px-1 text-center leading-tight">{a.name.slice(0, 20)}</div>
              )}
              <button onClick={() => removeAttachment(i)} className="absolute -top-1 -right-1 w-4 h-4 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">×</button>
            </div>
          ))}
        </div>
      )}

      <form onSubmit={submit} className="flex items-center gap-2 bg-card border border-border rounded-lg px-3 py-2 focus-within:border-primary/30 transition-colors shadow-sm">
        <input ref={fileInputRef} type="file" multiple className="hidden"
          onChange={(e) => { onFileSelect(e.target.files); e.target.value = ""; }}
          accept="image/*,.pdf,.txt,.md,.json,.csv,.yaml,.yml,.py,.ts,.tsx,.js,.jsx,.html,.css" />
        <button type="button" onClick={() => fileInputRef.current?.click()} disabled={loading}
          className="p-1.5 text-muted-foreground/50 hover:text-muted-foreground hover:bg-accent/50 rounded-md transition-colors disabled:opacity-30 shrink-0" title="上传附件">
          <Paperclip className="w-4 h-4" />
        </button>

        <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={handleKeyDown}
          placeholder={loading ? "Agent 正在工作中..." : "说你想做什么..."} disabled={loading}
          className="flex-1 bg-transparent border-none outline-none px-0 py-1 text-sm text-foreground placeholder:text-muted-foreground/50 disabled:opacity-50 min-w-0" />

        <div className="flex items-center gap-1.5 shrink-0">
          {/* Workspace */}
          <div className="relative">
            <select value={activeWs} onChange={(e) => setActiveWs(e.target.value)}
              className="appearance-none bg-background border border-border hover:border-ring/30 rounded-md pl-2 pr-5 py-1 text-[11px] text-muted-foreground outline-none cursor-pointer transition-colors max-w-[90px] truncate">
              <option value="">项目</option>
              {workshops.map((w) => <option key={w.name} value={w.name}>{w.name}</option>)}
            </select>
            <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-muted-foreground/40 pointer-events-none" />
          </div>

          {/* Model combobox */}
          <ModelCombobox
            value={model}
            onChange={(v) => { setModel(v); if (!supportsReasoning(v)) setReasoningEffort(""); }}
            groups={chatProviderGroups}
            onSelectEnd={() => { /* model saved via ChatPanel's setModel callback */ }}
          />

          {/* Reasoning */}
          {showReasoning && (
            <div className="relative">
              <select value={reasoningEffort} onChange={(e) => setReasoningEffort(e.target.value)}
                className="appearance-none bg-primary/[0.06] border border-primary/[0.15] hover:border-primary/30 rounded-md pl-2 pr-4 py-1 text-[11px] text-primary/80 outline-none cursor-pointer transition-colors">
                {REASONING_EFFORTS.map((e) => <option key={e} value={e}>{e ? REASONING_LABELS[e] : "关"}</option>)}
              </select>
              <Brain className="absolute right-0.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-primary/30 pointer-events-none" />
            </div>
          )}

          {loading ? (
            <button type="button" onClick={onCancel}
              className="p-1.5 text-destructive hover:bg-destructive/10 rounded-md transition-colors" title="停止">
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <Button type="submit" variant="outline" size="icon" disabled={!input.trim() && !attachments.length} className="h-8 w-8">
              <Send className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

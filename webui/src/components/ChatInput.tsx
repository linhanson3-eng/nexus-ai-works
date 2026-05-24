import { type FormEvent, useRef, useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Square, Paperclip, ChevronDown, Search, Check, CornerDownRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { filterCommands, getCommandsByGroup, SLASH_COMMAND_GROUPS } from "../lib/slashCommands";
import type { SlashCommand, SlashCommandGroup } from "../lib/slashCommands";

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
  onSlashSend?: (command: string) => void;
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
  onSlashSend,
}: ChatInputProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();

  const [slashOpen, setSlashOpen] = useState(false);
  const [slashQuery, setSlashQuery] = useState("");
  const [slashNavIndex, setSlashNavIndex] = useState(0);

  const handleInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const value = e.target.value;
    setInput(value);

    if (value.startsWith("/") && !value.includes(" ")) {
      setSlashOpen(true);
      setSlashQuery(value);
    } else if (slashOpen) {
      setSlashOpen(false);
      setSlashQuery("");
    }
  };

  const executeSlashCommand = (cmd: SlashCommand) => {
    setSlashOpen(false);
    setSlashQuery("");

    switch (cmd.action.type) {
      case "navigate":
        setInput("");
        navigate(cmd.action.payload ?? "/");
        break;
      case "send":
        setInput("");
        onSlashSend?.(cmd.action.payload ?? cmd.name);
        break;
      case "local":
        setInput("");
        if (cmd.name === "/theme") {
          document.dispatchEvent(new CustomEvent("nexus:cycle-theme"));
        } else if (cmd.name === "/logout") {
          document.dispatchEvent(new CustomEvent("nexus:logout"));
        }
        break;
    }
  };

  const filteredCommands = slashOpen ? filterCommands(slashQuery) : [];
  const groupedCommands = slashOpen ? getCommandsByGroup(filteredCommands) : new Map();
  const flatSlashCommands = slashOpen ? filteredCommands : [];

  // Reset nav index when commands change
  useEffect(() => {
    setSlashNavIndex(0);
  }, [slashQuery, slashOpen]);

  const submit = (e?: FormEvent) => {
    e?.preventDefault();
    if (slashOpen) return;
    const text = input.trim();
    if ((!text && !attachments.length) || loading) return;
    onSend();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (slashOpen) {
      if (e.key === "Escape") {
        setSlashOpen(false);
        setSlashQuery("");
        setSlashNavIndex(0);
        setInput("");
        e.preventDefault();
        return;
      }
      if (e.key === "ArrowDown") {
        e.preventDefault();
        setSlashNavIndex((prev) => Math.min(prev + 1, flatSlashCommands.length - 1));
        return;
      }
      if (e.key === "ArrowUp") {
        e.preventDefault();
        setSlashNavIndex((prev) => Math.max(prev - 1, 0));
        return;
      }
      if (e.key === "Enter" && flatSlashCommands.length > 0) {
        e.preventDefault();
        executeSlashCommand(flatSlashCommands[slashNavIndex]);
        return;
      }
      return;
    }
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submit(); }
  };

  const showReasoning = supportsReasoning(model);

  return (
    <div className="shrink-0 pt-3 border-t border-border relative">
      {attachments.length > 0 && (
        <div className="flex gap-2 flex-wrap pb-2">
          {attachments.map((a, i) => (
            <div key={i} className="relative group bg-muted border border-border rounded-md overflow-hidden">
              {a.type === "image" && a.dataUrl ? (
                <div className="w-14 h-14"><img src={a.dataUrl} alt={a.name} className="w-full h-full object-cover" /></div>
              ) : (
                <div className="w-14 h-14 flex items-center justify-center text-[10px] text-muted-foreground px-1 text-center leading-tight">{a.name.slice(0, 20)}</div>
              )}
              <button onClick={() => removeAttachment(i)} className="absolute -top-1 -right-1 w-4 h-4 bg-destructive text-destructive-foreground rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">&times;</button>
            </div>
          ))}
        </div>
      )}

      {/* Slash Command Panel */}
      {slashOpen && filteredCommands.length > 0 && (
        <div className="absolute bottom-full left-0 right-0 mb-1 z-50">
          <div className="bg-popover border border-border rounded-lg shadow-lg overflow-hidden max-h-72">
            <div className="px-3 py-2 border-b border-border flex items-center gap-2">
              <span className="text-xs text-muted-foreground">命令</span>
              <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground font-mono">esc</span>
              <span className="text-[10px] text-muted-foreground/50">关闭</span>
            </div>
            <div className="overflow-y-auto max-h-56">
              {[...groupedCommands.entries()].map(([group, cmds]) => {
                const groupMeta = SLASH_COMMAND_GROUPS[group as SlashCommandGroup];
                return (
                  <div key={group}>
                    <div className="px-3 py-1.5 text-[10px] text-muted-foreground/50 uppercase tracking-wider">
                      {groupMeta?.label ?? group}
                    </div>
                    {cmds.map((cmd) => {
                        const globalIdx = flatSlashCommands.indexOf(cmd);
                        return (
                      <button
                        key={cmd.name}
                        onClick={() => executeSlashCommand(cmd)}
                        className={`w-full flex items-center gap-2.5 px-4 py-1.5 text-sm transition-colors text-left ${
                          globalIdx === slashNavIndex
                            ? "bg-accent text-foreground"
                            : "hover:bg-accent/50"
                        }`}
                      >
                        <cmd.icon className="w-3.5 h-3.5 text-muted-foreground shrink-0" />
                        <span className="font-mono text-xs text-foreground font-medium">{cmd.name}</span>
                        <span className="text-xs text-muted-foreground/70 truncate">{cmd.description}</span>
                        <CornerDownRight className="w-3 h-3 text-muted-foreground/30 ml-auto shrink-0" />
                      </button>
                        );
                    })}
                  </div>
                );
              })}
            </div>
          </div>
        </div>
      )}

      {slashOpen && filteredCommands.length === 0 && slashQuery !== "/" && (
        <div className="absolute bottom-full left-0 right-0 mb-1 z-50">
          <div className="bg-popover border border-border rounded-lg shadow-lg p-6 text-center">
            <p className="text-sm text-muted-foreground">未匹配到命令</p>
            <p className="text-xs text-muted-foreground/50 mt-1">输入 / 查看所有可用命令</p>
          </div>
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

        <input ref={inputRef}
          value={input} onChange={handleInputChange} onKeyDown={handleKeyDown}
          placeholder={loading ? "Agent 正在工作中..." : "说你想做什么... 输入 / 查看命令"} disabled={loading}
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
            
          />

          {/* Reasoning */}
          {showReasoning && (
            <div className="flex items-center bg-primary/[0.04] border border-primary/[0.15] rounded-md overflow-hidden">
              {REASONING_EFFORTS.map((e) => (
                <button
                  key={e}
                  type="button"
                  onClick={() => setReasoningEffort(e)}
                  className={`px-1.5 py-1 text-[11px] transition-colors border-r border-primary/[0.08] last:border-r-0 ${
                    reasoningEffort === e
                      ? "bg-primary/10 text-primary font-medium"
                      : "text-primary/50 hover:text-primary/70 hover:bg-primary/[0.04]"
                  }`}
                >
                  {e ? REASONING_LABELS[e] : "关"}
                </button>
              ))}
            </div>
          )}

          {loading ? (
            <button type="button" onClick={onCancel}
              className="p-1.5 text-destructive hover:bg-destructive/10 rounded-md transition-colors" title="停止">
              <Square className="w-4 h-4" />
            </button>
          ) : (
            <Button type="submit" variant="outline" size="icon" disabled={(!input.trim() && !attachments.length) || slashOpen} className="h-8 w-8">
              <Send className="w-3.5 h-3.5" />
            </Button>
          )}
        </div>
      </form>
    </div>
  );
}

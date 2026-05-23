import { useState, useRef, useEffect, useCallback, type FormEvent, type DragEvent } from "react";
import { Send, User, Loader2, AlertTriangle, RefreshCw, Wrench, ChevronDown, ChevronRight, Bot, Square, Paperclip, X, ImageIcon, FileIcon, Cpu, Brain, Lightbulb } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { useToast } from "./Toast";

// ── Types ────────────────────────────────────────────────────

interface Attachment { name: string; type: string; dataUrl?: string; size: number; }

interface ToolCall { id: string; name: string; args: string; result?: string; status: "pending" | "done" | "error"; }

interface ChatMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;
  timestamp: number;
  model?: string;
  turns?: number; cost?: number;
  toolsUsed?: string[];
  toolCalls?: ToolCall[];
  sessionId?: string;
  isStreaming?: boolean;
  error?: string;
  attachments?: Attachment[];
  planSteps?: string[];
}

// ── SSE Events ──────────────────────────────────────────────

type SSEEvent =
  | { type: "status"; event: string; task?: string; workshop?: string }
  | { type: "message_start"; session_id: string; prompt: string }
  | { type: "message_delta"; text: string }
  | { type: "content_delta"; text: string; turn?: number; model?: string }
  | { type: "reasoning_delta"; text: string }
  | { type: "thinking"; text: string }
  | { type: "tool_call_delta"; tool_id: string; tool_name: string; tool_input: string }
  | { type: "tool_start"; tool_id: string; tool_name: string }
  | { type: "tool_delta"; tool_id: string; delta: string }
  | { type: "tool_result"; tool_id: string; content: string; is_error?: boolean }
  | { type: "tool_match"; tools: string[] }
  | { type: "command_match"; commands: string[] }
  | { type: "message_stop" }
  | { type: "usage"; input_tokens?: number; output_tokens?: number }
  | { type: "runtime_summary"; turns?: number; model?: string; total_cost?: number; tools_used?: string[] }
  | { type: "completed"; reply: string; turns: number; cost_usd: number; tools_used: string[]; session_id: string; model: string }
  | { type: "error"; message: string }
  | { type: "done" };

// ── Helpers ──────────────────────────────────────────────────

const REASONING_EFFORTS = ["", "low", "medium", "high", "xhigh"] as const;
const REASONING_LABELS: Record<string, string> = { "": "关闭推理", low: "低", medium: "中", high: "高", xhigh: "极高" };
const REASONING_MODEL_KEYWORDS = ["gpt-5", "gpt-4", "o1", "o3", "o4", "claude-opus", "claude-sonnet-4-6", "deepseek-reasoner", "deepseek-r1", "gemini-thinking", "qwq", "glm-z1"];

function supportsReasoning(model: string): boolean {
  const m = model.toLowerCase();
  return REASONING_MODEL_KEYWORDS.some(k => m.includes(k));
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}
function genId(): string { return Math.random().toString(36).slice(2, 10); }
function safeText(t: unknown): string { if (t === null || t === undefined) return ""; const s = String(t); return s === "undefined" ? "" : s; }
function formatCost(cost: number): string {
  if (cost === 0) return "";
  return cost < 0.01 ? "< $0.01" : `$${cost.toFixed(2)}`;
}

// ── Rendering ────────────────────────────────────────────────

function RenderContent({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  if (!text || text === "undefined") return null;
  const lines = text.split("\n");
  const els: React.ReactNode[] = [];
  let inCode = false, codeBuf: string[] = [];

  const flush = () => {
    if (codeBuf.length) {
      els.push(<pre key={els.length} className="bg-black/30 border border-border rounded-lg p-3 my-2 overflow-auto text-xs font-mono text-terminal"><code>{codeBuf.join("\n")}</code></pre>);
      codeBuf = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("```")) { if (inCode) { flush(); inCode = false; } else { inCode = true; } continue; }
    if (inCode) { codeBuf.push(line); continue; }
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const children = parts.map((p, j) => {
      if (p.startsWith("**") && p.endsWith("**")) return <strong key={j} className="text-white font-semibold">{p.slice(2, -2)}</strong>;
      const cp = p.split(/(`[^`]+`)/g);
      return cp.map((c, k) => {
        if (c.startsWith("`") && c.endsWith("`")) return <code key={k} className="bg-surface px-1 py-0.5 rounded text-terminal text-xs">{c.slice(1, -1)}</code>;
        return c;
      });
    });
    els.push(<p key={i} className="min-h-[1.4em] leading-relaxed">{children.length ? children : "\u00A0"}</p>);
  }
  flush();
  return <div className="space-y-0.5">{els}{isStreaming && <span className="inline-block w-1.5 h-4 bg-accent ml-0.5 animate-pulse rounded-sm align-middle" />}</div>;
}

function ToolCallCard({ tool }: { tool: ToolCall }) {
  const [open, setOpen] = useState(false);
  let args = ""; try { args = JSON.stringify(JSON.parse(tool.args), null, 2); } catch { args = tool.args; }
  return (
    <div className="mt-1.5 bg-surface/50 border border-border/50 rounded-lg overflow-hidden text-xs">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-2 px-3 py-1.5 text-muted hover:text-white transition-colors">
        <span className={`w-1.5 h-1.5 rounded-full ${tool.status === "done" ? "bg-success" : tool.status === "error" ? "bg-warning" : "bg-accent animate-pulse"}`} />
        <Wrench className="w-3 h-3 text-info" />
        <span className="text-white font-medium">{tool.name}</span>
        <span className="flex-1" />
        <span className="text-[10px] text-muted/60">{tool.status === "pending" ? "执行中" : tool.status === "error" ? "失败" : "完成"}</span>
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1.5">
          {args && args !== "{}" && <div><div className="text-[10px] text-muted mb-0.5">参数</div><pre className="text-muted whitespace-pre-wrap text-[11px] bg-black/20 rounded p-2 max-h-24 overflow-auto">{args}</pre></div>}
          {tool.result && <div><div className="text-[10px] text-muted mb-0.5">结果</div><pre className={`whitespace-pre-wrap text-[11px] bg-black/20 rounded p-2 max-h-32 overflow-auto ${tool.status === "error" ? "text-warning" : "text-terminal"}`}>{tool.result.slice(0, 2000)}</pre></div>}
        </div>
      )}
    </div>
  );
}

function AttachPreview({ attachments, onRemove }: { attachments: Attachment[]; onRemove: (i: number) => void }) {
  if (!attachments.length) return null;
  return (
    <div className="flex gap-2 flex-wrap pb-2">
      {attachments.map((a, i) => (
        <div key={i} className="relative group bg-surface border border-border rounded-lg overflow-hidden">
          {a.type === "image" && a.dataUrl ? <div className="w-14 h-14"><img src={a.dataUrl} alt={a.name} className="w-full h-full object-cover" /></div>
          : <div className="w-14 h-14 flex items-center justify-center">{a.type === "image" ? <ImageIcon className="w-5 h-5 text-muted" /> : <FileIcon className="w-5 h-5 text-muted" />}</div>}
          <button onClick={() => onRemove(i)} className="absolute -top-1 -right-1 w-4 h-4 bg-warning text-black rounded-full flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity"><X className="w-2.5 h-2.5" /></button>
        </div>
      ))}
    </div>
  );
}

// ── Main ─────────────────────────────────────────────────────

export function ChatPanel() {
  const toast = useToast();
  const [messages, setMessages] = useState<ChatMessage[]>(() => {
    // Restore messages from localStorage on mount
    try {
      const saved = localStorage.getItem("nexus_messages");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) return parsed;
      }
    } catch { /* localStorage corrupted or unavailable — non-critical */ }
    return [{
      id: "welcome", role: "assistant",
      content: "你好，我是 Nexus 助手。告诉我你想做什么，我会调用工具来完成任务。",
      timestamp: Date.now(),
    }];
  });
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workshops, setWorkshops] = useState<{ name: string }[]>([]);
  const [activeWs, setActiveWs] = useState("");
  const [dragOver, setDragOver] = useState(false);
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [thinking, setThinking] = useState(false);
  const [model, setModel] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState("");
  const [chatProviderGroups, setChatProviderGroups] = useState<{ name: string; hasKey: boolean; models: string[] }[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    api.listWorkshops().then(data => {
      setWorkshops(data as { name: string }[]);
      if (data.length && !activeWs) setActiveWs(data[0].name);
    }).catch((err) => { console.error("加载工作区列表失败", err); });
  }, []);

  useEffect(() => {
    api.listProviders().then((providers: Record<string, { models?: string[]; api_key?: string }>) => {
      const groups: { name: string; hasKey: boolean; models: string[] }[] = [];
      for (const [pname, cfg] of Object.entries(providers)) {
        if (cfg.models?.length) {
          const chatModels = cfg.models.filter((m: string) => {
            const lower = m.toLowerCase();
            return !/(reranker|rerank|embedding|bge|speech|asr|cosyvoice|sensevoice|ocr|paddle|kolors|wan|image-edit|image-turbo|z-image|mt-|captioner|tts|whisper|moderation|dall-e)/.test(lower);
          });
          if (chatModels.length) groups.push({ name: pname, hasKey: !!cfg.api_key, models: chatModels });
        }
      }
      setChatProviderGroups(groups);
    }).catch((err) => { console.error("加载模型列表失败", err); });
  }, []);

  useEffect(() => {
    api.getPreferences().then((prefs: unknown) => {
      setModel((prefs as Record<string, string>)?.default_model || "");
    }).catch((err) => { console.error("加载偏好设置失败", err); });
  }, []);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Persist messages to localStorage on every change (skip streaming)
  useEffect(() => {
    const streaming = messages.some(m => m.isStreaming);
    if (streaming || messages.length <= 1) return;
    try {
      localStorage.setItem("nexus_messages", JSON.stringify(messages.slice(-200)));
    } catch { /* localStorage full or disabled — non-critical */ }
  }, [messages]);

  // Restore session from backend (complementary to localStorage)
  useEffect(() => {
    const key = 'nexus_session_' + activeWs;
    const sid = localStorage.getItem(key);
    if (!sid || !activeWs) return;
    setSessionId(sid);
    fetch('/api/agent/session/' + encodeURIComponent(sid), { headers: getAuthHeaders(), credentials: 'include' })
      .then(r => r.json())
      .then(data => {
        if (data.messages?.length) {
          const msgs: ChatMessage[] = [];
          for (const m of data.messages) {
            if (m.role === 'user' || m.role === 'assistant') {
              msgs.push({
                id: genId(), role: m.role,
                content: m.content || '',
                timestamp: Date.now() - msgs.length * 1000,
              });
            }
          }
          if (msgs.length > 0) {
            // Merge: backend session takes precedence if it has more messages
            setMessages(prev => {
              const prevUserMsgs = prev.filter(m => m.role === 'user');
              return prevUserMsgs.length >= msgs.filter(m => m.role === 'user').length ? prev : [
                { id: "welcome", role: "assistant" as const,
                  content: "你好，我是 Nexus 助手。告诉我你想做什么，我会调用工具来完成任务。",
                  timestamp: Date.now() },
                ...msgs,
              ];
            });
          }
        }
      }).catch((err) => { console.error("加载会话记录失败", err); });
  }, [activeWs]);

  // ── SSE Streaming ──────────────────────────────────────

  const runStream = useCallback(async (task: string) => {
    setLoading(true); setThinking(true);
    abortRef.current = new AbortController();

    const assistantId = genId();
    const assistantMsg: ChatMessage = { id: assistantId, role: "assistant", content: "", reasoning: "", timestamp: Date.now(), toolCalls: [], isStreaming: true, planSteps: [], };
    setMessages(prev => [...prev, assistantMsg]);

    const update = (updater: (msg: ChatMessage) => ChatMessage) => {
      setMessages(prev => prev.map(m => m.id === assistantId ? updater({ ...m }) : m));
    };

    try {
      const body: Record<string, string> = { task, workshop: activeWs };
      if (model) body.model = model;
      if (reasoningEffort) body.reasoning_effort = reasoningEffort;

      const res = await fetch("/api/agent/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify(body),
        signal: abortRef.current.signal,
        credentials: "include",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No body");
      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";
        for (const line of lines) {
          if (line.startsWith("event: ") || !line.startsWith("data: ")) continue;
          try {
            handleSSE(JSON.parse(line.slice(6)), assistantId, update);
          } catch { /* skip */ }
        }
      }
    } catch (err: unknown) {
      if (err instanceof DOMException && err.name === "AbortError") {
        update(m => ({ ...m, isStreaming: false, content: m.content || "(已取消)" }));
      } else {
        const msg = err instanceof Error ? err.message : "Unknown";
        update(m => ({ ...m, isStreaming: false, error: msg }));
        setError(msg);
      }
    } finally {
      setLoading(false); setThinking(false);
      abortRef.current = null;
    }
  }, [activeWs, model, reasoningEffort]);

  function handleSSE(event: SSEEvent, _id: string, update: (u: (m: ChatMessage) => ChatMessage) => void) {
    switch (event.type) {
      case "status": setThinking(true); break;
      case "message_start": setThinking(false); update(m => ({ ...m, sessionId: event.session_id })); break;
      case "thinking":
      case "reasoning_delta":
        setThinking(false);
        update(m => ({ ...m, reasoning: (m.reasoning || "") + safeText((event as { text?: string; delta?: string }).text ?? (event as { delta?: string }).delta) }));
        break;
      case "message_delta":
      case "content_delta":
        setThinking(false);
        update(m => ({ ...m, content: m.content + safeText((event as { text?: string; delta?: string }).text ?? (event as { delta?: string }).delta) }));
        break;
      case "tool_match":
        update(m => ({ ...m, planSteps: [...(m.planSteps || []), ...(event as { tools: string[] }).tools.map(t => `🔧 ${t}`)] }));
        break;
      case "tool_start": {
        const ts = event as { tool_id?: string; tool_call_id?: string; tool_name: string };
        const tid = ts.tool_call_id || ts.tool_id || "";
        update(m => {
          if (!tid || m.toolCalls?.find(t => t.id === tid)) return m;
          return { ...m, toolCalls: [...(m.toolCalls || []), { id: tid, name: ts.tool_name, args: "", status: "pending" as const }] };
        });
        break;
      }
      case "tool_call_delta": {
        const tc = event as { tool_id?: string; tool_call_id?: string; tool_name: string; tool_input?: string; arguments_delta?: string };
        const tcid = tc.tool_call_id || tc.tool_id || "";
        update(m => {
          if (!tcid || m.toolCalls?.find(t => t.id === tcid)) return m;
          return { ...m, toolCalls: [...(m.toolCalls || []), { id: tcid, name: tc.tool_name, args: tc.tool_input || tc.arguments_delta || "", status: "pending" as const }] };
        });
        break;
      }
      case "tool_result": {
        const tr = event as { tool_id?: string; tool_call_id?: string; content?: string; ok?: boolean; is_error?: boolean };
        const trid = tr.tool_call_id || tr.tool_id || "";
        const isErr = tr.is_error === true || tr.ok === false;
        update(m => ({ ...m, toolCalls: m.toolCalls?.map(t => t.id === trid ? { ...t, result: tr.content ?? (isErr ? "error" : "done"), status: isErr ? "error" as const : "done" as const } : t) || [] }));
        break;
      }
      case "runtime_summary": {
        const s = event as { turns?: number; model?: string; total_cost?: number; tools_used?: string[] };
        update(m => ({ ...m, turns: s.turns, model: s.model, cost: s.total_cost, toolsUsed: s.tools_used }));
        break;
      }
      case "completed": {
        const c = event as { reply: string; turns: number; cost_usd: number; tools_used: string[]; session_id: string; model: string };
        setSessionId(c.session_id);
        try { localStorage.setItem('nexus_session_' + activeWs, c.session_id); } catch { /* localStorage full — non-critical */ }
        update(m => ({ ...m, content: m.content || c.reply || "", isStreaming: false, turns: c.turns, cost: c.cost_usd, toolsUsed: c.tools_used, model: m.model || c.model, sessionId: c.session_id }));
        break;
      }
      case "error": update(m => ({ ...m, isStreaming: false, error: (event as { message: string }).message })); break;
      case "done": case "message_stop": update(m => ({ ...m, isStreaming: false })); break;
    }
  }

  // ── Actions ────────────────────────────────────────────

  const send = useCallback((e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if ((!text && !attachments.length) || loading) return;
    let taskText = text;
    if (attachments.length) taskText = text ? `${text}\n\n[附件: ${attachments.map(a => a.name).join(", ")}]` : `分析文件: ${attachments.map(a => a.name).join(", ")}`;
    setMessages(prev => [...prev, { id: genId(), role: "user", content: text || "(文件)", timestamp: Date.now(), attachments: [...attachments] }]);
    setInput(""); setAttachments([]);
    runStream(taskText);
  }, [input, loading, attachments, runStream]);

  const cancelRun = () => abortRef.current?.abort();
  const handleKeyDown = (e: React.KeyboardEvent) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } };

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;
    const newAtt: Attachment[] = [];
    for (const f of Array.from(files)) {
      const att: Attachment = { name: f.name, type: f.type.startsWith("image/") ? "image" : "file", size: f.size };
      if (att.type === "image") { const r = new FileReader(); r.onload = () => { att.dataUrl = r.result as string; setAttachments(prev => [...prev, att]); }; r.readAsDataURL(f); }
      else newAtt.push(att);
    }
    if (newAtt.length) setAttachments(prev => [...prev, ...newAtt]);
  };

  const removeAttachment = (i: number) => setAttachments(prev => prev.filter((_, j) => j !== i));
  const handleDrag = (e: DragEvent) => { e.preventDefault(); setDragOver(e.type === "dragover" || e.type === "dragenter"); };
  const handleDrop = (e: DragEvent) => { e.preventDefault(); setDragOver(false); handleFileSelect(e.dataTransfer.files); };
  const handlePaste = (e: React.ClipboardEvent) => {
    const items = e.clipboardData?.items; if (!items) return;
    const files: File[] = [];
    for (const item of Array.from(items)) { if (item.kind === "file") { const f = item.getAsFile(); if (f) files.push(f); } }
    if (files.length) { e.preventDefault(); handleFileSelect(files as unknown as FileList); }
  };

  const showReasoningSelector = supportsReasoning(model);

  // ── Render ─────────────────────────────────────────────

  return (
    <div className="max-w-3xl mx-auto w-full flex flex-col min-h-0 flex-1" onDragOver={handleDrag} onDragLeave={handleDrag} onDrop={handleDrop}>
      {/* Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-border shrink-0">
        <div className="w-8 h-8 rounded-lg bg-accent/10 border border-accent/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-accent" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-bold text-white">Nexus 助手</h2>
          <div className="flex items-center gap-2 text-[10px] text-muted">
            {activeWs ? <span>{activeWs}</span> : <span className="text-muted/40">未选择项目</span>}
            {sessionId && <span className="text-muted/30">· {sessionId.slice(0, 8)}</span>}
          </div>
        </div>
        <button onClick={() => { setMessages([{ id: "welcome", role: "assistant", content: "你好，我是 Nexus 助手。告诉我你想做什么。", timestamp: Date.now() }]); setSessionId(""); }}
          className="p-1.5 text-muted/40 hover:text-muted transition-colors rounded-lg" title="新对话">
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-auto py-4 space-y-4 px-1">
        {messages.map(msg => {
          const isUser = msg.role === "user";
          if (msg.role === "system") return <div key={msg.id} className="flex justify-center"><span className="text-[11px] text-muted/60 bg-surface/30 px-3 py-1 rounded-full">{msg.content}</span></div>;

          return (
            <div key={msg.id} className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${isUser ? "bg-surface border border-border" : "bg-accent/10 border border-accent/20"}`}>
                {isUser ? <User className="w-3.5 h-3.5 text-muted" /> : <Bot className="w-3.5 h-3.5 text-accent" />}
              </div>

              <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
                <div className={`inline-block max-w-[85%] rounded-2xl px-4 py-2.5 text-sm ${isUser ? "bg-accent/10 border border-accent/20 text-white rounded-br-md" : "bg-card border border-border text-slate-200 rounded-bl-md"}`}>
                  {msg.attachments?.map((a, i) => (
                    <div key={i} className="flex items-center gap-1 bg-black/20 rounded px-2 py-0.5 text-[10px] text-muted mb-2">{a.type === "image" ? <ImageIcon className="w-3 h-3" /> : <FileIcon className="w-3 h-3" />}{a.name}</div>
                  ))}

                  {/* Plan / tool match preview */}
                  {msg.planSteps && msg.planSteps.length > 0 && msg.isStreaming && (
                    <div className="mb-2 bg-accent/5 border border-accent/10 rounded-lg px-3 py-2">
                      <div className="flex items-center gap-1.5 text-[10px] text-accent/70 mb-1"><Lightbulb className="w-3 h-3" /> 计划</div>
                      {msg.planSteps.filter(Boolean).map((s, i) => <div key={i} className="text-[11px] text-muted">{s}</div>)}
                    </div>
                  )}

                  {/* Reasoning / Thinking section */}
                  {msg.reasoning && (
                    <ReasoningBlock text={msg.reasoning} isStreaming={msg.isStreaming} />
                  )}

                  {/* Thinking indicator */}
                  {msg.isStreaming && thinking && !msg.content && !msg.toolCalls?.length && !msg.reasoning && (
                    <div className="flex items-center gap-2 text-muted"><Loader2 className="w-3.5 h-3.5 text-accent animate-spin" /><span className="text-xs">思考中...</span></div>
                  )}

                  {/* Content */}
                  {msg.content && <RenderContent text={msg.content} isStreaming={msg.isStreaming} />}

                  {/* Tool calls */}
                  {msg.toolCalls?.map(t => <ToolCallCard key={t.id} tool={t} />)}

                  {/* Error */}
                  {msg.error && <div className="mt-2 flex items-center gap-1.5 text-warning text-xs"><AlertTriangle className="w-3 h-3" />{msg.error}</div>}

                  {/* Footer */}
                  {(msg.model || msg.turns || msg.cost !== undefined) && (
                    <div className="mt-2 pt-1.5 border-t border-border/30 flex items-center gap-3 text-[10px] text-muted/50">
                      {msg.model && <span className="flex items-center gap-1"><Cpu className="w-2.5 h-2.5" />{msg.model}</span>}
                      {msg.turns && <span>{msg.turns} turns</span>}
                      {msg.cost !== undefined && msg.cost > 0 && <span>{formatCost(msg.cost)}</span>}
                      {msg.toolsUsed?.length ? <span className="flex items-center gap-1"><Wrench className="w-2.5 h-2.5" />{msg.toolsUsed.join(", ")}</span> : null}
                    </div>
                  )}
                </div>
                <div className={`text-[9px] text-muted/40 mt-1 ${isUser ? "text-right" : ""}`}>{formatTime(msg.timestamp)}</div>
              </div>
            </div>
          );
        })}

        {error && (
          <div className="flex items-center gap-3 bg-warning/5 border border-warning/20 rounded-xl p-3 mx-4">
            <AlertTriangle className="w-4 h-4 text-warning shrink-0" /><p className="text-xs text-warning flex-1">{error}</p>
            <button onClick={() => setError(null)} className="text-[10px] text-warning/60 hover:text-warning">关闭</button>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input Area */}
      <div className={`shrink-0 pt-3 border-t transition-colors ${dragOver ? "border-accent/30" : "border-border"}`}>
        <AttachPreview attachments={attachments} onRemove={removeAttachment} />

        <form onSubmit={send} className="flex items-center gap-2 bg-card border border-border rounded-2xl px-3 py-2 focus-within:border-accent/30 transition-colors shadow-sm">
          {/* Attach */}
          <input ref={fileInputRef} type="file" multiple className="hidden"
            onChange={e => { handleFileSelect(e.target.files); e.target.value = ""; }}
            accept="image/*,.pdf,.txt,.md,.json,.csv,.yaml,.yml,.py,.ts,.tsx,.js,.jsx,.html,.css" />
          <button type="button" onClick={() => fileInputRef.current?.click()} disabled={loading}
            className="p-1.5 text-muted/50 hover:text-muted hover:bg-white/5 rounded-lg transition-colors disabled:opacity-30 shrink-0" title="上传附件">
            <Paperclip className="w-4 h-4" />
          </button>

          {/* Text input */}
          <input ref={inputRef} value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={handleKeyDown} onPaste={handlePaste}
            placeholder={loading ? "Agent 正在工作中..." : "说你想做什么..."}
            disabled={loading}
            className="flex-1 bg-transparent border-none outline-none px-0 py-1 text-sm text-white placeholder:text-muted/50 disabled:opacity-50 min-w-0" />

          {/* Right controls group */}
          <div className="flex items-center gap-1.5 shrink-0">
            {/* Workspace pill */}
            <div className="relative">
              <select value={activeWs} onChange={e => setActiveWs(e.target.value)}
                className="appearance-none bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] rounded-lg pl-2 pr-5 py-1 text-[11px] text-muted outline-none cursor-pointer transition-colors max-w-[90px] truncate">
                <option value="">项目</option>
                {workshops.map(w => <option key={w.name} value={w.name}>{w.name}</option>)}
              </select>
              <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-muted/40 pointer-events-none" />
            </div>

            {/* Model pill */}
            <div className="relative">
              <select value={model} onChange={e => { const v = e.target.value; setModel(v); if (!supportsReasoning(v)) setReasoningEffort(""); api.savePreferences({ default_model: v }).catch(() => {}); }}
                className="appearance-none bg-white/[0.04] border border-white/[0.06] hover:border-white/[0.12] rounded-lg pl-2 pr-5 py-1 text-[11px] text-muted outline-none cursor-pointer transition-colors max-w-[120px] truncate">
                <option value="">自动</option>
                {chatProviderGroups.map(g => (
                  <optgroup key={g.name} label={g.name + (g.hasKey ? " ✓" : "")}>
                    {g.models.map(m => <option key={g.name + "/" + m} value={g.name + "/" + m}>{m.replace(/^Pro\//, "").replace(/^LoRA\//, "")}</option>)}
                  </optgroup>
                ))}
              </select>
              <ChevronDown className="absolute right-1 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-muted/40 pointer-events-none" />
            </div>

            {/* Reasoning pill */}
            {showReasoningSelector && (
              <div className="relative">
                <select value={reasoningEffort} onChange={e => setReasoningEffort(e.target.value)}
                  className="appearance-none bg-accent/[0.06] border border-accent/[0.15] hover:border-accent/30 rounded-lg pl-2 pr-4 py-1 text-[11px] text-accent/80 outline-none cursor-pointer transition-colors">
                  {REASONING_EFFORTS.map(e => <option key={e} value={e}>{e ? REASONING_LABELS[e] : "关"}</option>)}
                </select>
                <Brain className="absolute right-0.5 top-1/2 -translate-y-1/2 w-2.5 h-2.5 text-accent/30 pointer-events-none" />
              </div>
            )}

            {/* Send / Stop */}
            {loading ? (
              <button type="button" onClick={cancelRun}
                className="p-1.5 text-warning hover:bg-warning/10 rounded-lg transition-colors" title="停止">
                <Square className="w-4 h-4" />
              </button>
            ) : (
              <button type="submit" disabled={!input.trim() && !attachments.length}
                className="p-1.5 bg-accent/10 text-accent border border-accent/20 rounded-lg hover:bg-accent/20 transition-colors disabled:opacity-20 disabled:hover:bg-accent/10">
                <Send className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </form>
      </div>
    </div>
  );
}

// ── Reasoning block ──────────────────────────────────────────

function ReasoningBlock({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  const [open, setOpen] = useState(true);
  if (!text || text === "undefined") return null;
  return (
    <div className="mb-2 border border-accent/10 rounded-lg overflow-hidden">
      <button onClick={() => setOpen(!open)} className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-accent/60 hover:text-accent/80 transition-colors bg-accent/[0.02]">
        <Brain className="w-3 h-3" />
        <span>思考过程{isStreaming ? "..." : ""}</span>
        <span className="flex-1" />
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-3 pb-2 text-xs text-muted/70 whitespace-pre-wrap leading-relaxed italic max-h-48 overflow-auto">
          {text}
          {isStreaming && <span className="inline-block w-1.5 h-3.5 bg-accent/40 ml-0.5 animate-pulse rounded-sm align-middle" />}
        </div>
      )}
    </div>
  );
}

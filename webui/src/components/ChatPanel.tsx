import { useState, useRef, useEffect, useLayoutEffect, useCallback, type DragEvent } from "react";
import { Bot, RefreshCw, AlertTriangle } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { useToast } from "./Toast";
import { ChatMessage, type ChatMessageData, type ToolCall } from "./ChatMessage";
import { ChatInput } from "./ChatInput";

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

function genId(): string {
  return Math.random().toString(36).slice(2, 10);
}

function safeText(t: unknown): string {
  if (t === null || t === undefined) return "";
  const s = String(t);
  return s === "undefined" ? "" : s;
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

// ── Main ─────────────────────────────────────────────────────

export function ChatPanel() {
  const toast = useToast();
  const [messages, setMessages] = useState<ChatMessageData[]>([]);
  const [hydrated, setHydrated] = useState(false);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workshops, setWorkshops] = useState<{ name: string }[]>([]);
  const [activeWs, setActiveWs] = useState("");
  const [attachments, setAttachments] = useState<Attachment[]>([]);
  const [sessionId, setSessionId] = useState("");
  const [thinking, setThinking] = useState(false);
  const [model, setModel] = useState("");
  const [reasoningEffort, setReasoningEffort] = useState("");
  const [chatProviderGroups, setChatProviderGroups] = useState<ProviderGroup[]>([]);

  const messagesEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Hydrate messages synchronously before first paint (eliminate flash)
  useLayoutEffect(() => {
    try {
      const saved = localStorage.getItem("nexus_messages");
      if (saved) {
        const parsed = JSON.parse(saved);
        if (Array.isArray(parsed) && parsed.length > 0) {
          setMessages(parsed);
          setHydrated(true);
          return;
        }
      }
    } catch { /* corrupted */ }
    setMessages([
      {
        id: "welcome",
        role: "assistant",
        content: "你好，我是 Nexus 助手。告诉我你想做什么，我会调用工具来完成任务。",
        timestamp: Date.now(),
      },
    ]);
    setHydrated(true);
  }, []);

  useEffect(() => {
    api.listWorkshops().then((data) => {
      setWorkshops(data as { name: string }[]);
      if (data.length && !activeWs) setActiveWs(data[0].name);
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.listProviders().then((providers: Record<string, { models?: string[]; api_key?: string }>) => {
      const groups: ProviderGroup[] = [];
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
    }).catch(() => {});
  }, []);

  useEffect(() => {
    api.getPreferences().then((prefs: unknown) => {
      setModel((prefs as Record<string, string>)?.default_model || "");
    }).catch(() => {});
  }, []);

  const isFirstScroll = useRef(true);
  useEffect(() => {
    if (!hydrated) return;
    const el = messagesEndRef.current;
    if (!el) return;
    if (isFirstScroll.current) {
      // Instant scroll after hydration – no animation flash
      el.scrollIntoView({ behavior: "instant" as ScrollBehavior });
      isFirstScroll.current = false;
    } else {
      el.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, hydrated]);

  // Persist messages
  useEffect(() => {
    const streaming = messages.some((m) => m.isStreaming);
    if (streaming || messages.length <= 1) return;
    try { localStorage.setItem("nexus_messages", JSON.stringify(messages.slice(-200))); } catch {}
  }, [messages]);

  // Restore session
  useEffect(() => {
    const key = "nexus_session_" + activeWs;
    const sid = localStorage.getItem(key);
    if (!sid || !activeWs) return;
    setSessionId(sid);
    fetch("/api/agent/session/" + encodeURIComponent(sid), { headers: getAuthHeaders(), credentials: "include" })
      .then((r) => r.json())
      .then((data) => {
        if (data.messages?.length) {
          const msgs: ChatMessageData[] = [];
          for (const m of data.messages) {
            if (m.role === "user" || m.role === "assistant") {
              msgs.push({ id: genId(), role: m.role, content: m.content || "", timestamp: Date.now() - msgs.length * 1000 });
            }
          }
          if (msgs.length > 0) {
            setMessages((prev) => {
              const prevUserMsgs = prev.filter((m) => m.role === "user");
              return prevUserMsgs.length >= msgs.filter((m) => m.role === "user").length
                ? prev
                : [{ id: "welcome", role: "assistant" as const, content: "你好，我是 Nexus 助手。", timestamp: Date.now() }, ...msgs];
            });
          }
        }
      }).catch(() => {});
  }, [activeWs]);

  // ── SSE Streaming ──────────────────────────────────────

  const runStream = useCallback(
    async (task: string) => {
      setLoading(true);
      setThinking(true);
      abortRef.current = new AbortController();

      const assistantId = genId();
      const assistantMsg: ChatMessageData = {
        id: assistantId, role: "assistant", content: "", reasoning: "",
        timestamp: Date.now(), toolCalls: [], isStreaming: true, planSteps: [],
      };
      setMessages((prev) => [...prev, assistantMsg]);

      const update = (updater: (msg: ChatMessageData) => ChatMessageData) => {
        setMessages((prev) => prev.map((m) => (m.id === assistantId ? updater({ ...m }) : m)));
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
            try { handleSSE(JSON.parse(line.slice(6)), assistantId, update); } catch { /* skip */ }
          }
        }
      } catch (err: unknown) {
        if (err instanceof DOMException && err.name === "AbortError") {
          update((m) => ({ ...m, isStreaming: false, content: m.content || "(已取消)" }));
        } else {
          const msg = err instanceof Error ? err.message : "Unknown";
          update((m) => ({ ...m, isStreaming: false, error: msg }));
          setError(msg);
        }
      } finally {
        setLoading(false);
        setThinking(false);
        abortRef.current = null;
      }
    },
    [activeWs, model, reasoningEffort],
  );

  function handleSSE(
    event: SSEEvent,
    _id: string,
    update: (u: (m: ChatMessageData) => ChatMessageData) => void,
  ) {
    switch (event.type) {
      case "status": setThinking(true); break;
      case "message_start": setThinking(false); update((m) => ({ ...m, sessionId: event.session_id })); break;
      case "thinking":
      case "reasoning_delta":
        setThinking(false);
        update((m) => ({ ...m, reasoning: (m.reasoning || "") + safeText((event as { text?: string; delta?: string }).text ?? (event as { delta?: string }).delta) }));
        break;
      case "message_delta":
      case "content_delta":
        setThinking(false);
        update((m) => ({ ...m, content: m.content + safeText((event as { text?: string; delta?: string }).text ?? (event as { delta?: string }).delta) }));
        break;
      case "tool_match":
        update((m) => ({ ...m, planSteps: [...(m.planSteps || []), ...(event as { tools: string[] }).tools.map((t) => `🔧 ${t}`)] }));
        break;
      case "tool_start": {
        const ts = event as { tool_id?: string; tool_call_id?: string; tool_name: string };
        const tid = ts.tool_call_id || ts.tool_id || "";
        update((m) => {
          if (!tid || m.toolCalls?.find((t) => t.id === tid)) return m;
          return { ...m, toolCalls: [...(m.toolCalls || []), { id: tid, name: ts.tool_name, args: "", status: "pending" as const }] };
        });
        break;
      }
      case "tool_call_delta": {
        const tc = event as { tool_id?: string; tool_call_id?: string; tool_name: string; tool_input?: string; arguments_delta?: string };
        const tcid = tc.tool_call_id || tc.tool_id || "";
        update((m) => {
          if (!tcid || m.toolCalls?.find((t) => t.id === tcid)) return m;
          return { ...m, toolCalls: [...(m.toolCalls || []), { id: tcid, name: tc.tool_name, args: tc.tool_input || tc.arguments_delta || "", status: "pending" as const }] };
        });
        break;
      }
      case "tool_result": {
        const tr = event as { tool_id?: string; tool_call_id?: string; content?: string; ok?: boolean; is_error?: boolean };
        const trid = tr.tool_call_id || tr.tool_id || "";
        const isErr = tr.is_error === true || tr.ok === false;
        update((m) => ({
          ...m,
          toolCalls: m.toolCalls?.map((t) =>
            t.id === trid ? { ...t, result: tr.content ?? (isErr ? "error" : "done"), status: isErr ? ("error" as const) : ("done" as const) } : t,
          ) || [],
        }));
        break;
      }
      case "runtime_summary": {
        const s = event as { turns?: number; model?: string; total_cost?: number; tools_used?: string[] };
        update((m) => ({ ...m, turns: s.turns, model: s.model, cost: s.total_cost, toolsUsed: s.tools_used }));
        break;
      }
      case "completed": {
        const c = event as { reply: string; turns: number; cost_usd: number; tools_used: string[]; session_id: string; model: string };
        setSessionId(c.session_id);
        try { localStorage.setItem("nexus_session_" + activeWs, c.session_id); } catch {}
        update((m) => ({ ...m, content: m.content || c.reply || "", isStreaming: false, turns: c.turns, cost: c.cost_usd, toolsUsed: c.tools_used, model: m.model || c.model, sessionId: c.session_id }));
        break;
      }
      case "artifact": {
        const art = event as { id: string; name: string; type: string; content: string; node_id?: string; node_label?: string; workspace?: string };
        import("../lib/ArtifactContext").then(({ useArtifactContext }) => {
          // Dispatch custom event since we can't use hooks in SSE callback
          window.dispatchEvent(new CustomEvent("nexus:artifact", {
            detail: {
              id: art.id || `${Date.now()}-${art.name}`,
              name: art.name,
              type: art.type || "text",
              content: art.content,
              nodeId: art.node_id,
              nodeLabel: art.node_label,
              workspace: art.workspace || "",
              createdAt: new Date().toISOString(),
              size: new Blob([art.content || ""]).size,
            },
          }));
        });
        break;
      }
      case "error": update((m) => ({ ...m, isStreaming: false, error: (event as { message: string }).message })); break;
      case "done":
      case "message_stop": update((m) => ({ ...m, isStreaming: false })); break;
    }
  }

  // ── Actions ────────────────────────────────────────────

  const send = useCallback(() => {
    const text = input.trim();
    if ((!text && !attachments.length) || loading) return;
    let taskText = text;
    if (attachments.length)
      taskText = text ? `${text}\n\n[附件: ${attachments.map((a) => a.name).join(", ")}]` : `分析文件: ${attachments.map((a) => a.name).join(", ")}`;
    setMessages((prev) => [
      ...prev,
      { id: genId(), role: "user", content: text || "(文件)", timestamp: Date.now(), attachments: [...attachments] },
    ]);
    setInput("");
    setAttachments([]);
    runStream(taskText);
  }, [input, loading, attachments, runStream]);

  const cancelRun = () => abortRef.current?.abort();

  const handleFileSelect = (files: FileList | null) => {
    if (!files) return;
    const newAtt: Attachment[] = [];
    for (const f of Array.from(files)) {
      const att: Attachment = { name: f.name, type: f.type.startsWith("image/") ? "image" : "file", size: f.size };
      if (att.type === "image") {
        const r = new FileReader();
        r.onload = () => { att.dataUrl = r.result as string; setAttachments((prev) => [...prev, att]); };
        r.readAsDataURL(f);
      } else newAtt.push(att);
    }
    if (newAtt.length) setAttachments((prev) => [...prev, ...newAtt]);
  };

  const removeAttachment = (i: number) => setAttachments((prev) => prev.filter((_, j) => j !== i));

  const handleDrag = (e: DragEvent) => {
    e.preventDefault();
  };

  const handleDrop = (e: DragEvent) => {
    e.preventDefault();
    handleFileSelect(e.dataTransfer.files);
  };

  // ── Render ─────────────────────────────────────────────

  return (
    <div
      className="max-w-4xl mx-auto w-full flex flex-col min-h-0 flex-1"
      onDragOver={handleDrag}
      onDragLeave={handleDrag}
      onDrop={handleDrop}
    >
      {/* Header */}
      <div className="flex items-center gap-3 pb-3 border-b border-border shrink-0">
        <div className="w-8 h-8 rounded-md bg-primary/10 border border-primary/20 flex items-center justify-center">
          <Bot className="w-4 h-4 text-primary" />
        </div>
        <div className="flex-1 min-w-0">
          <h2 className="text-sm font-semibold">Nexus 助手</h2>
          <div className="flex items-center gap-2 text-[10px] text-muted-foreground">
            {activeWs ? <span>{activeWs}</span> : <span className="text-muted-foreground/40">未选择项目</span>}
            {sessionId && <span className="text-muted-foreground/30">· {sessionId.slice(0, 8)}</span>}
          </div>
        </div>
        <button
          onClick={() => {
            setMessages([{ id: "welcome", role: "assistant", content: "你好，我是 Nexus 助手。", timestamp: Date.now() }]);
            setSessionId("");
          }}
          className="p-1.5 text-muted-foreground/40 hover:text-muted-foreground transition-colors rounded-md"
          title="新对话"
        >
          <RefreshCw className="w-3.5 h-3.5" />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 min-h-0 overflow-auto py-4 space-y-4 px-1">
        {!hydrated ? (
          <div className="flex items-center justify-center h-full">
            <div className="flex flex-col items-center gap-3 text-muted-foreground/40">
              <div className="w-5 h-5 border-2 border-primary/20 border-t-primary/60 rounded-full animate-spin" />
              <span className="text-xs">加载对话...</span>
            </div>
          </div>
        ) : (
          <>
        {messages.map((msg) => (
          <ChatMessage key={msg.id} msg={msg} thinking={thinking} />
        ))}

        {error && (
          <div className="flex items-center gap-3 bg-destructive/5 border border-destructive/20 rounded-lg p-3 mx-4">
            <AlertTriangle className="w-4 h-4 text-destructive shrink-0" />
            <p className="text-xs text-destructive flex-1">{error}</p>
            <button onClick={() => setError(null)} className="text-[10px] text-destructive/60 hover:text-destructive">
              关闭
            </button>
          </div>
        )}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <ChatInput
        input={input}
        setInput={setInput}
        loading={loading}
        workshops={workshops}
        activeWs={activeWs}
        setActiveWs={setActiveWs}
        model={model}
        setModel={(v) => { setModel(v); api.savePreferences({ default_model: v }).catch(() => {}); }}
        reasoningEffort={reasoningEffort}
        setReasoningEffort={setReasoningEffort}
        chatProviderGroups={chatProviderGroups}
        attachments={attachments}
        removeAttachment={removeAttachment}
        onSend={send}
        onCancel={cancelRun}
        onFileSelect={handleFileSelect}
        onSlashSend={(command: string) => {
          setMessages((prev) => [
            ...prev,
            { id: genId(), role: "user", content: command, timestamp: Date.now(), attachments: [] },
          ]);
          runStream(command);
        }}
      />
    </div>
  );
}

export type { ToolCall };

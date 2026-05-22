import { useState, useRef, useEffect, useCallback, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Send, User, Loader2, AlertTriangle, RefreshCw, Wrench, ChevronDown, ChevronRight, Bot, MessageSquare } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";

interface Message {
  role: "user" | "agent";
  content: string;
  actions?: { label: string; to: string }[];
  error?: boolean;
  tools?: { name: string; id: string; args: string }[];
}

const WELCOME: Message = {
  role: "agent",
  content: "你好，我是 Nexus 助手。\n\n直接告诉我想做什么，我会调用工具来完成任务。\n\n也可以使用快捷指令：\n- **创建工作区** — 「创建一个前端开发工作区」\n- **查看看板** — 「查看看板」",
};

// ── Helpers ──────────────────────────────────────────────────

function renderLine(line: string, i: number) {
  if (line.startsWith("```")) return null;

  const parts = line.split(/(`[^`]+`)/g);
  const children = parts.map((part, j) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={j} className="bg-surface px-1 py-0.5 rounded text-terminal text-xs">{part.slice(1, -1)}</code>;
    }
    const boldParts = part.split(/(\*\*[^*]+\*\*)/g);
    return boldParts.map((bp, k) => {
      if (bp.startsWith("**") && bp.endsWith("**")) {
        return <strong key={k} className="text-white">{bp.slice(2, -2)}</strong>;
      }
      return bp;
    });
  });

  return <p key={i} className="min-h-[1.4em]">{children.length ? children : " "}</p>;
}

// ── Tool Call Card ───────────────────────────────────────────

function ToolCard({ name, args, collapsed: initialCollapsed }: { name: string; args: string; collapsed?: boolean }) {
  const [collapsed, setCollapsed] = useState(initialCollapsed ?? true);
  let displayArgs = "";
  try {
    const parsed = JSON.parse(args);
    displayArgs = JSON.stringify(parsed, null, 2);
  } catch {
    displayArgs = args;
  }

  return (
    <div className="mt-2 bg-surface border border-border rounded-xl overflow-hidden text-xs">
      <button
        onClick={() => setCollapsed(!collapsed)}
        className="w-full flex items-center gap-2 px-3 py-2 text-muted hover:text-white transition-colors"
      >
        <Wrench className="w-3 h-3 text-info" />
        <span className="text-white font-medium">{name}</span>
        <span className="flex-1" />
        {collapsed ? <ChevronRight className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
      </button>
      {!collapsed && (
        <pre className="px-3 pb-2 text-muted whitespace-pre-wrap overflow-auto max-h-32">{displayArgs || "(无参数)"}</pre>
      )}
    </div>
  );
}

// ── Question Dialog ──────────────────────────────────────────

function QuestionDialog({ question, onSubmit, onSkip }: { question: string; onSubmit: (answer: string) => void; onSkip: () => void }) {
  const [answer, setAnswer] = useState("");
  return (
    <div className="mt-3 bg-info/5 border border-info/20 rounded-xl p-4">
      <div className="flex items-center gap-2 mb-3">
        <MessageSquare className="w-4 h-4 text-info" />
        <span className="text-sm font-medium text-white">Agent 需要确认</span>
      </div>
      <p className="text-sm text-slate-300 mb-3">{question}</p>
      <div className="flex gap-2">
        <input
          value={answer}
          onChange={e => setAnswer(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && answer.trim()) onSubmit(answer.trim()); }}
          placeholder="输入你的回答..."
          className="flex-1 bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-info/30"
        />
        <button onClick={() => answer.trim() && onSubmit(answer.trim())}
          disabled={!answer.trim()}
          className="px-4 py-2 bg-info/10 text-info border border-info/20 rounded-xl text-sm font-medium hover:bg-info/20 transition-colors disabled:opacity-30">
          发送
        </button>
        <button onClick={onSkip}
          className="px-3 py-2 text-muted hover:text-white text-sm transition-colors">
          跳过
        </button>
      </div>
    </div>
  );
}

// ── Main Component ───────────────────────────────────────────

function chatStorageKey(ws: string): string { return `nexus_chat_${ws}`; }

function loadMessages(ws: string): Message[] {
  try {
    const raw = localStorage.getItem(chatStorageKey(ws));
    return raw ? JSON.parse(raw) : [WELCOME];
  } catch { return [WELCOME]; }
}

function saveMessages(ws: string, msgs: Message[]) {
  try { localStorage.setItem(chatStorageKey(ws), JSON.stringify(msgs)); } catch {}
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workspace, setWorkspace] = useState("");
  const [workshops, setWorkshops] = useState<{ name: string }[]>([]);
  const [question, setQuestion] = useState<{ text: string; requestId: string } | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Persist messages to localStorage whenever they change
  useEffect(() => {
    if (workspace && messages.length > 1) saveMessages(workspace, messages);
  }, [messages, workspace]);

  useEffect(() => {
    api.listWorkshops().then(data => {
      setWorkshops(data.map((w: { name: string }) => ({ name: w.name })));
      if (data.length > 0 && !workspace) {
        const ws = data[0].name;
        setWorkspace(ws);
        // Restore saved messages for this workspace
        const saved = loadMessages(ws);
        if (saved.length > 1 || saved[0]?.role !== WELCOME.role) {
          setMessages(saved);
        }
      }
    }).catch(() => {});
  }, []);

  // ── Quick commands (intent parser fallback) ──────────────────

  const runQuickCommand = useCallback(async (text: string): Promise<Message | null> => {
    try {
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        credentials: "include",
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) return null;
      const data = await res.json();
      return {
        role: "agent",
        content: data.reply || "收到。",
        actions: (data.actions || []).map((a: { label: string; href: string }) => ({ label: a.label, to: a.href })),
      };
    } catch {
      return null;
    }
  }, []);

  // ── SSE Agent Run ───────────────────────────────────────────

  const runAgentStream = useCallback(async (text: string): Promise<Message> => {
    const controller = new AbortController();
    abortRef.current = controller;

    const res = await fetch("/api/agent/run/stream", {
      method: "POST",
      headers: { "Content-Type": "application/json", ...getAuthHeaders() },
      credentials: "include",
      body: JSON.stringify({ task: text, workshop: workspace }),
      signal: controller.signal,
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "请求失败" }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const reader = res.body?.getReader();
    if (!reader) throw new Error("No response stream");

    const decoder = new TextDecoder();
    let buffer = "";
    let content = "";
    const tools: { name: string; id: string; args: string }[] = [];
    const seenToolIds = new Set<string>();
    let finalReply = "";
    let finalActions: { label: string; to: string }[] = [];
    let finalError = "";

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });

      const lines = buffer.split("\n");
      buffer = lines.pop() || "";

      let eventName = "";
      for (const line of lines) {
        if (line.startsWith("event: ")) {
          eventName = line.slice(7).trim();
        } else if (line.startsWith("data: ") && eventName) {
          try {
            const data = JSON.parse(line.slice(6));

            switch (eventName) {
              case "content_delta":
                content += data.delta || "";
                // Update streaming message in place
                setMessages(prev => {
                  const msgs = [...prev];
                  const last = msgs[msgs.length - 1];
                  if (last && last.role === "agent" && last.content.startsWith(" ")) {
                    msgs[msgs.length - 1] = { ...last, content: " " + content };
                  }
                  return msgs;
                });
                break;

              case "tool_call_delta":
                if (data.tool_name && data.tool_call_id && !seenToolIds.has(data.tool_call_id)) {
                  seenToolIds.add(data.tool_call_id);
                  tools.push({ name: data.tool_name, id: data.tool_call_id, args: data.arguments_delta || "" });
                  setMessages(prev => {
                    const msgs = [...prev];
                    const last = msgs[msgs.length - 1];
                    if (last && last.role === "agent") {
                      msgs[msgs.length - 1] = { ...last, tools: [...(last.tools || []), { name: data.tool_name, id: data.tool_call_id, args: data.arguments_delta || "" }] };
                    }
                    return msgs;
                  });
                } else if (data.tool_call_id && data.arguments_delta) {
                  // Append to existing tool args
                  setMessages(prev => {
                    const msgs = [...prev];
                    const last = msgs[msgs.length - 1];
                    if (last?.tools) {
                      const updated = last.tools.map(t =>
                        t.id === data.tool_call_id ? { ...t, args: t.args + data.arguments_delta } : t
                      );
                      msgs[msgs.length - 1] = { ...last, tools: updated };
                    }
                    return msgs;
                  });
                }
                break;

              case "completed":
                finalReply = data.reply || "";
                finalActions = (data.actions || []).map((a: { label: string; href: string }) => ({ label: a.label, to: a.href }));
                finalError = data.error || "";
                break;

              case "error":
                finalError = data.message || "执行出错";
                break;
            }
          } catch { /* skip malformed */ }
        }
      }
    }

    // Finalize content
    const finalContent = finalReply || content;

    return {
      role: "agent",
      content: finalError ? `执行失败: ${finalError}` : finalContent || "(无输出)",
      actions: finalActions,
      tools: tools.length > 0 ? tools : undefined,
      error: !!finalError,
    };
  }, [workspace]);

  // ── Send ────────────────────────────────────────────────────

  const send = async (e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    // Add a placeholder agent message for streaming
    setMessages(prev => [...prev, { role: "agent", content: " " }]);

    try {
      // Quick commands detection
      const quickPatterns = /^(创建|新建|删除|删掉|查看|列出|所有|帮助|help|有哪些|怎么用)/;
      if (quickPatterns.test(text) && !workspace) {
        const msg = await runQuickCommand(text);
        if (msg) {
          setMessages(prev => [...prev.slice(0, -1), msg]);
          setLoading(false);
          return;
        }
      }

      const msg = await runAgentStream(text);
      setMessages(prev => [...prev.slice(0, -1), msg]);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "网络错误";
      // Fallback to quick command
      const quickMsg = await runQuickCommand(text);
      if (quickMsg) {
        setMessages(prev => [...prev.slice(0, -1), quickMsg]);
      } else {
        setMessages(prev => [...prev.slice(0, -1), {
          role: "agent",
          content: `请求失败: ${reason}`,
          error: true,
        }]);
        setError(`请求失败: ${reason}`);
      }
    } finally {
      setLoading(false);
      abortRef.current = null;
    }
  };

  const cancelRun = () => {
    abortRef.current?.abort();
    setLoading(false);
    setMessages(prev => {
      const msgs = [...prev];
      const last = msgs[msgs.length - 1];
      if (last && last.role === "agent" && last.content.startsWith(" ")) {
        msgs[msgs.length - 1] = { ...last, content: "已取消。", error: true };
      }
      return msgs;
    });
  };

  // ── Render ──────────────────────────────────────────────────

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 pb-4 border-b border-border">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-white">Agent 对话</h1>
            <p className="text-muted text-sm mt-1">AI 驱动的任务执行与工作区管理</p>
          </div>
          {workshops.length > 0 && (
            <select value={workspace} onChange={e => setWorkspace(e.target.value)}
              className="bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30">
              {workshops.map(w => (
                <option key={w.name} value={w.name}>{w.name}</option>
              ))}
            </select>
          )}
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto py-4 space-y-4">
        {messages.map((msg, i) => {
          const isStreaming = msg.content.startsWith(" ");
          const displayContent = isStreaming ? msg.content.slice(1) : msg.content;

          return (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "agent" && (
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${msg.error ? "bg-warning/10" : "bg-accent/20"}`}>
                  {msg.error ? <AlertTriangle className="w-4 h-4 text-warning" /> : <Bot className="w-4 h-4 text-accent" />}
                </div>
              )}
              <div className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-accent/15 border border-accent/20 text-white"
                  : msg.error
                    ? "bg-warning/5 border border-warning/20 text-slate-300"
                    : "bg-card border border-border text-slate-300"
              }`}>
                {displayContent.split("\n").map(renderLine)}

                {/* Streaming cursor */}
                {isStreaming && displayContent.length > 0 && (
                  <span className="inline-block w-1.5 h-4 bg-accent ml-0.5 animate-pulse rounded-sm align-middle" />
                )}
                {isStreaming && displayContent.length === 0 && (
                  <div className="flex items-center gap-2">
                    <Loader2 className="w-4 h-4 text-accent animate-spin" />
                    <span className="text-muted">思考中...</span>
                  </div>
                )}

                {/* Tool call cards */}
                {msg.tools && msg.tools.length > 0 && (
                  <div className="space-y-1">
                    {msg.tools.map((t) => (
                      <ToolCard key={t.id} name={t.name} args={t.args} collapsed={!isStreaming} />
                    ))}
                  </div>
                )}

                {/* Action buttons */}
                {msg.actions && msg.actions.length > 0 && (
                  <div className="flex gap-2 mt-3 pt-3 border-t border-border flex-wrap">
                    {msg.actions.map((a) => (
                      <button key={a.label} onClick={() => navigate(a.to)}
                        className="px-3 py-1.5 bg-accent/10 text-accent border border-accent/20 rounded-lg text-xs hover:bg-accent/20 transition-colors">
                        {a.label} →
                      </button>
                    ))}
                  </div>
                )}

                {/* Question prompt */}
                {question && i === messages.length - 1 && (
                  <QuestionDialog
                    question={question.text}
                    onSubmit={async (answer) => {
                      setQuestion(null);
                      try {
                        await fetch("/api/agent/answer", {
                          method: "POST",
                          headers: { "Content-Type": "application/json" },
                          body: JSON.stringify({ request_id: question.requestId, answer }),
                        });
                      } catch { /* ignore */ }
                    }}
                    onSkip={() => setQuestion(null)}
                  />
                )}
              </div>
              {msg.role === "user" && (
                <div className="w-8 h-8 rounded-lg bg-surface border border-border flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-4 h-4 text-muted" />
                </div>
              )}
            </div>
          );
        })}

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-3 bg-warning/5 border border-warning/20 rounded-xl p-4">
            <AlertTriangle className="w-5 h-5 text-warning shrink-0" />
            <div className="flex-1"><p className="text-sm text-warning">{error}</p></div>
            <button onClick={() => { setError(null); setMessages([WELCOME]); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-warning/10 text-warning rounded-lg hover:bg-warning/20 transition-colors">
              <RefreshCw className="w-3 h-3" /> 清除
            </button>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={send} className="shrink-0 pt-4 border-t border-border flex gap-3">
        {loading ? (
          <button onClick={cancelRun}
            className="px-4 py-3 bg-warning/10 text-warning border border-warning/20 rounded-xl font-semibold text-sm hover:bg-warning/20 transition-colors flex items-center gap-2 shrink-0">
            <AlertTriangle className="w-4 h-4" /> 取消
          </button>
        ) : (
          <input
            value={input}
            onChange={e => setInput(e.target.value)}
            placeholder={workspace ? `在 ${workspace} 中执行任务...` : "说你想做什么..."}
            disabled={loading}
            className="flex-1 bg-card border border-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 disabled:opacity-50 transition-colors"
          />
        )}
        <button
          type="submit"
          disabled={loading || !input.trim()}
          className="px-4 py-3 bg-accent text-black rounded-xl font-semibold text-sm hover:bg-amber-400 transition-colors disabled:opacity-30 flex items-center gap-2"
        >
          <Send className="w-4 h-4" />
        </button>
      </form>
    </div>
  );
}

import { useState, useRef, useEffect, type FormEvent } from "react";
import { useNavigate } from "react-router-dom";
import { Send, Zap, User, Loader2, AlertTriangle, RefreshCw } from "lucide-react";

interface Message {
  role: "user" | "agent";
  content: string;
  actions?: { label: string; to: string }[];
  error?: boolean;
}

const WELCOME: Message = {
  role: "agent",
  content:
    "你好，我是 AI 工厂助手。\n\n可以帮你：\n- **创建车间** — 「创建一个前端开发车间」\n- **运行工作流** — 「在开发部执行 code-review」\n- **查看看板** — 「查看看板」\n\n直接告诉我想做什么。",
};

function renderLine(line: string, i: number) {
  // Code blocks
  if (line.startsWith("```") || line.startsWith("```")) return null;

  // Inline code
  const parts = line.split(/(`[^`]+`)/g);
  const children = parts.map((part, j) => {
    if (part.startsWith("`") && part.endsWith("`")) {
      return (
        <code key={j} className="bg-surface px-1 py-0.5 rounded text-terminal text-xs">
          {part.slice(1, -1)}
        </code>
      );
    }
    // Bold
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

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([WELCOME]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const navigate = useNavigate();

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const send = async (e?: FormEvent) => {
    e?.preventDefault();
    const text = input.trim();
    if (!text || loading) return;

    const userMsg: Message = { role: "user", content: text };
    setMessages((prev) => [...prev, userMsg]);
    setInput("");
    setLoading(true);
    setError(null);

    try {
      const res = await fetch("/api/agent/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: text }),
      });
      if (!res.ok) throw new Error(`${res.status}: ${res.statusText}`);
      const data = await res.json();
      setMessages((prev) => [
        ...prev,
        {
          role: "agent",
          content: data.reply || "收到。",
          actions: (data.actions || []).map((a: { label: string; href: string }) => ({
            label: a.label,
            to: a.href,
          })),
        },
      ]);
    } catch (err) {
      const reason = err instanceof Error ? err.message : "网络错误";
      setError(`请求失败: ${reason}`);
      setMessages((prev) => [
        ...prev,
        { role: "agent", content: `请求失败，请确认 Gateway 已启动。\n错误: ${reason}`, error: true },
      ]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="shrink-0 pb-4 border-b border-border">
        <h1 className="text-2xl font-black tracking-tight text-white">Agent 对话</h1>
        <p className="text-muted text-sm mt-1">用自然语言管理 AI 工厂</p>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-auto py-4 space-y-4">
        {messages.map((msg, i) => (
          <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
            {msg.role === "agent" && (
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 mt-0.5 ${msg.error ? "bg-warning/10" : "bg-accent/20"}`}>
                {msg.error ? <AlertTriangle className="w-4 h-4 text-warning" /> : <Zap className="w-4 h-4 text-accent" />}
              </div>
            )}
            <div
              className={`max-w-[80%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-accent/15 border border-accent/20 text-white"
                  : msg.error
                    ? "bg-warning/5 border border-warning/20 text-slate-300"
                    : "bg-card border border-border text-slate-300"
              }`}
            >
              {msg.content.split("\n").map(renderLine)}
              {msg.actions && msg.actions.length > 0 && (
                <div className="flex gap-2 mt-3 pt-3 border-t border-border flex-wrap">
                  {msg.actions.map((a) => (
                    <button
                      key={a.label}
                      onClick={() => navigate(a.to)}
                      className="px-3 py-1.5 bg-accent/10 text-accent border border-accent/20 rounded-lg text-xs hover:bg-accent/20 transition-colors"
                    >
                      {a.label} →
                    </button>
                  ))}
                </div>
              )}
            </div>
            {msg.role === "user" && (
              <div className="w-8 h-8 rounded-lg bg-surface border border-border flex items-center justify-center shrink-0 mt-0.5">
                <User className="w-4 h-4 text-muted" />
              </div>
            )}
          </div>
        ))}

        {/* Error banner */}
        {error && (
          <div className="flex items-center gap-3 bg-warning/5 border border-warning/20 rounded-xl p-4">
            <AlertTriangle className="w-5 h-5 text-warning shrink-0" />
            <div className="flex-1">
              <p className="text-sm text-warning">{error}</p>
            </div>
            <button
              onClick={() => { setError(null); setMessages([WELCOME]); }}
              className="flex items-center gap-1.5 px-3 py-1.5 text-xs bg-warning/10 text-warning rounded-lg hover:bg-warning/20 transition-colors"
            >
              <RefreshCw className="w-3 h-3" /> 清除
            </button>
          </div>
        )}

        {/* Loading */}
        {loading && (
          <div className="flex gap-3">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
              <Zap className="w-4 h-4 text-accent" />
            </div>
            <div className="bg-card border border-border rounded-2xl px-5 py-4 flex items-center gap-3">
              <Loader2 className="w-4 h-4 text-accent animate-spin" />
              <span className="text-sm text-muted">处理中...</span>
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* Input */}
      <form onSubmit={send} className="shrink-0 pt-4 border-t border-border flex gap-3">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="说你想做什么... 例如「创建一个开发车间」"
          disabled={loading}
          className="flex-1 bg-card border border-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 disabled:opacity-50 transition-colors"
        />
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

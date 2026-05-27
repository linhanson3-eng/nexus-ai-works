import { useState, useCallback } from "react";
import { User, Bot, Cpu, Wrench, AlertTriangle, Lightbulb, Loader2, Copy, Check } from "lucide-react";
import { ToolCallCard } from "./ToolCallCard";
import { MessageContent } from "./MessageContent";
import { ReasoningBlock } from "./ReasoningBlock";

export interface ToolCall {
  id: string;
  name: string;
  args: string;
  result?: string;
  status: "pending" | "done" | "error";
}

export interface ChatMessageData {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  reasoning?: string;
  timestamp: number;
  model?: string;
  turns?: number;
  cost?: number;
  toolsUsed?: string[];
  toolCalls?: ToolCall[];
  sessionId?: string;
  isStreaming?: boolean;
  error?: string;
  attachments?: { name: string; type: string; dataUrl?: string; size: number }[];
  planSteps?: string[];
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
}

function formatCost(cost: number): string {
  if (cost === 0) return "";
  return cost < 0.01 ? "< $0.01" : `$${cost.toFixed(2)}`;
}

function CopyAction({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handle = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button className="message-action-btn" onClick={handle} title="复制">
      {copied ? <Check className="w-3.5 h-3.5 text-success" /> : <Copy className="w-3.5 h-3.5" />}
    </button>
  );
}

export function ChatMessage({
  msg,
  thinking,
}: {
  msg: ChatMessageData;
  thinking: boolean;
}) {
  const isUser = msg.role === "user";

  if (msg.role === "system") {
    return (
      <div className="flex justify-center py-3">
        <span className="text-[11px] text-text-300 bg-bg-200 px-3 py-1 rounded-full">
          {msg.content}
        </span>
      </div>
    );
  }

  return (
    <div className={`chat-message flex gap-4 ${isUser ? "flex-row-reverse" : ""} mb-[var(--chat-turn-gap)]`}>
      {/* Avatar — Claude style: no avatar for assistant */}
      {isUser && (
        <div className="w-7 h-7 rounded-full bg-bg-300 border border-border flex items-center justify-center shrink-0 mt-1">
          <User className="w-3.5 h-3.5 text-text-200" />
        </div>
      )}

      <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
        <div className={isUser ? "max-w-[85%]" : "max-w-full"}>
          {msg.attachments?.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-1 bg-bg-200 rounded px-2 py-0.5 text-[10px] text-text-300 mb-2"
            >
              {a.name}
            </div>
          ))}

          {msg.planSteps && msg.planSteps.length > 0 && msg.isStreaming && (
            <div className="mb-2 bg-bg-200 border border-border rounded-md px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] text-text-300 mb-1">
                <Lightbulb className="w-3 h-3" /> 计划
              </div>
              {msg.planSteps.filter(Boolean).map((s, i) => (
                <div key={i} className="text-[11px] text-text-200">{s}</div>
              ))}
            </div>
          )}

          {msg.reasoning && (
            <ReasoningBlock text={msg.reasoning} isStreaming={msg.isStreaming} />
          )}

          {msg.isStreaming && thinking && !msg.content && !msg.toolCalls?.length && !msg.reasoning && (
            <div className="flex items-center gap-2 text-text-300 py-1">
              <Loader2 className="w-4 h-4 animate-spin" />
              <span className="text-xs">思考中...</span>
            </div>
          )}

          {/* User message — Claude style: bg-bg-300 card */}
          {isUser && msg.content && (
            <div
              className="font-user-message bg-bg-300 text-text-000 rounded-2xl px-4 py-2.5"
              style={{ background: "hsl(var(--bg-300))" }}
            >
              <MessageContent text={msg.content} />
            </div>
          )}

          {/* Assistant message — Claude style: plain text on bg */}
          {!isUser && msg.content && (
            <MessageContent text={msg.content} isStreaming={msg.isStreaming} />
          )}

          {msg.toolCalls?.map((t) => (
            <ToolCallCard key={t.id} tool={t} />
          ))}

          {msg.error && (
            <div className="mt-2 flex items-center gap-1.5 text-destructive text-xs">
              <AlertTriangle className="w-3 h-3" />
              {msg.error}
            </div>
          )}

          {/* Footer with model/turns/cost and message actions */}
          {!isUser && !msg.isStreaming && (
            <div className="flex items-center gap-2 mt-1.5">
              <div className="flex items-center gap-3 text-[10px] text-text-300">
                {msg.model && (
                  <span className="flex items-center gap-1"><Cpu className="w-2.5 h-2.5" />{msg.model}</span>
                )}
                {msg.turns && <span>{msg.turns} turns</span>}
                {msg.cost !== undefined && msg.cost > 0 && <span>{formatCost(msg.cost)}</span>}
                {msg.toolsUsed?.length ? (
                  <span className="flex items-center gap-1"><Wrench className="w-2.5 h-2.5" />{msg.toolsUsed.join(", ")}</span>
                ) : null}
              </div>
              <div className="message-actions">
                <CopyAction text={msg.content} />
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

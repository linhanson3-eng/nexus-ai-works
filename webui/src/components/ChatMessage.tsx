import { User, Bot, Cpu, Wrench, AlertTriangle, Lightbulb, Loader2 } from "lucide-react";
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
      <div className="flex justify-center">
        <span className="text-[11px] text-muted-foreground/60 bg-muted/30 px-3 py-1 rounded-full">
          {msg.content}
        </span>
      </div>
    );
  }

  return (
    <div className={`flex gap-3 ${isUser ? "flex-row-reverse" : ""}`}>
      {/* Avatar */}
      <div
        className={`w-7 h-7 rounded-md flex items-center justify-center shrink-0 mt-0.5 ${
          isUser
            ? "bg-muted border border-border"
            : "bg-primary/10 border border-primary/20"
        }`}
      >
        {isUser ? (
          <User className="w-3.5 h-3.5 text-muted-foreground" />
        ) : (
          <Bot className="w-3.5 h-3.5 text-primary" />
        )}
      </div>

      {/* Bubble */}
      <div className={`flex-1 min-w-0 ${isUser ? "flex justify-end" : ""}`}>
        <div
          className={`inline-block max-w-[85%] rounded-lg px-4 py-2.5 text-sm ${
            isUser
              ? "bg-primary text-primary-foreground"
              : "bg-card border border-border text-foreground"
          }`}
        >
          {msg.attachments?.map((a, i) => (
            <div
              key={i}
              className="flex items-center gap-1 bg-foreground/5 rounded px-2 py-0.5 text-[10px] text-muted-foreground mb-2"
            >
              {a.name}
            </div>
          ))}

          {/* Plan / tool match preview */}
          {msg.planSteps && msg.planSteps.length > 0 && msg.isStreaming && (
            <div className="mb-2 bg-primary/5 border border-primary/10 rounded-md px-3 py-2">
              <div className="flex items-center gap-1.5 text-[10px] text-primary/70 mb-1">
                <Lightbulb className="w-3 h-3" /> 计划
              </div>
              {msg.planSteps.filter(Boolean).map((s, i) => (
                <div key={i} className="text-[11px] text-muted-foreground">{s}</div>
              ))}
            </div>
          )}

          {/* Reasoning */}
          {msg.reasoning && <ReasoningBlock text={msg.reasoning} isStreaming={msg.isStreaming} />}

          {/* Thinking indicator */}
          {msg.isStreaming && thinking && !msg.content && !msg.toolCalls?.length && !msg.reasoning && (
            <div className="flex items-center gap-2 text-muted-foreground">
              <Loader2 className="w-3.5 h-3.5 text-primary animate-spin" />
              <span className="text-xs">思考中...</span>
            </div>
          )}

          {/* Content */}
          {msg.content && <MessageContent text={msg.content} isStreaming={msg.isStreaming} />}

          {/* Tool calls */}
          {msg.toolCalls?.map((t) => <ToolCallCard key={t.id} tool={t} />)}

          {/* Error */}
          {msg.error && (
            <div className="mt-2 flex items-center gap-1.5 text-destructive text-xs">
              <AlertTriangle className="w-3 h-3" />
              {msg.error}
            </div>
          )}

          {/* Footer */}
          {(msg.model || msg.turns || msg.cost !== undefined) && (
            <div className="mt-2 pt-1.5 border-t border-border/30 flex items-center gap-3 text-[10px] text-muted-foreground/50">
              {msg.model && (
                <span className="flex items-center gap-1"><Cpu className="w-2.5 h-2.5" />{msg.model}</span>
              )}
              {msg.turns && <span>{msg.turns} turns</span>}
              {msg.cost !== undefined && msg.cost > 0 && <span>{formatCost(msg.cost)}</span>}
              {msg.toolsUsed?.length ? (
                <span className="flex items-center gap-1"><Wrench className="w-2.5 h-2.5" />{msg.toolsUsed.join(", ")}</span>
              ) : null}
            </div>
          )}
        </div>
        <div className={`text-[9px] text-muted-foreground/40 mt-1 ${isUser ? "text-right" : ""}`}>
          {formatTime(msg.timestamp)}
        </div>
      </div>
    </div>
  );
}

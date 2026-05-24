import { useState } from "react";
import { Wrench, ChevronDown, ChevronRight } from "lucide-react";
import type { ToolCall } from "./ChatMessage";

export function ToolCallCard({ tool }: { tool: ToolCall }) {
  const [open, setOpen] = useState(false);

  let args = "";
  try { args = JSON.stringify(JSON.parse(tool.args), null, 2); } catch { args = tool.args; }

  const statusDot = {
    done: "bg-success",
    error: "bg-destructive",
    pending: "bg-primary animate-pulse",
  }[tool.status];

  return (
    <div className="mt-1.5 bg-background border border-border rounded-md overflow-hidden text-xs">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-muted-foreground hover:text-foreground transition-colors"
      >
        <span className={`w-1.5 h-1.5 rounded-full ${statusDot}`} />
        <Wrench className="w-3 h-3 text-primary" />
        <span className="text-foreground font-medium">{tool.name}</span>
        <span className="flex-1" />
        <span className="text-[10px] text-muted-foreground/60">
          {tool.status === "pending" ? "执行中" : tool.status === "error" ? "失败" : "完成"}
        </span>
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-3 pb-2 space-y-1.5">
          {args && args !== "{}" && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">参数</div>
              <pre className="text-muted-foreground whitespace-pre-wrap text-[11px] bg-muted/30 rounded p-2 max-h-24 overflow-auto">
                {args}
              </pre>
            </div>
          )}
          {tool.result && (
            <div>
              <div className="text-[10px] text-muted-foreground mb-0.5">结果</div>
              <pre
                className={`whitespace-pre-wrap text-[11px] bg-muted/30 rounded p-2 max-h-32 overflow-auto ${
                  tool.status === "error" ? "text-destructive" : "text-green-500 dark:text-green-400"
                }`}
              >
                {tool.result.slice(0, 2000)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

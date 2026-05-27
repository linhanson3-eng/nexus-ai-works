import { useState } from "react";
import type { ToolCall } from "./ChatMessage";

export function ToolCallCard({ tool }: { tool: ToolCall }) {
  const [open, setOpen] = useState(false);

  let args = "";
  try { args = JSON.stringify(JSON.parse(tool.args), null, 2); } catch { args = tool.args; }

  const dotClass = {
    done: "tool-call__dot--done",
    error: "tool-call__dot--error",
    pending: "tool-call__dot--pending",
  }[tool.status];

  const statusLabel = {
    done: "完成",
    error: "失败",
    pending: "执行中...",
  }[tool.status];

  const isRunning = tool.status === "pending";

  return (
    <div className={`tool-call mt-2 ${isRunning ? "tool-call--running" : ""}`}>
      <button className="tool-call__header w-full" onClick={() => setOpen(!open)}>
        <span className={`tool-call__dot ${dotClass}`} />
        <span className="tool-call__name">{tool.name}</span>
        <span className="flex-1" />
        <span className="text-[10px] text-text-300">{statusLabel}</span>
        <span className="text-[10px] text-text-300 ml-1">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="tool-call__body">
          {args && args !== "{}" && (
            <>
              <div className="text-[10px] text-text-300 mb-1 tracking-wider uppercase">参数</div>
              <pre className="tool-call__params">{args}</pre>
            </>
          )}
          {tool.result && (
            <>
              <div className="text-[10px] text-text-300 mt-2 mb-1 tracking-wider uppercase">结果</div>
              <pre className={`tool-call__result ${
                tool.status === "error" ? "text-destructive" : ""
              }`}>
                {tool.result.slice(0, 5000)}
              </pre>
            </>
          )}
        </div>
      )}
    </div>
  );
}

import { useState } from "react";

export function ReasoningBlock({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  const [open, setOpen] = useState(true);
  if (!text || text === "undefined") return null;

  return (
    <div className="thinking-block">
      <button className="thinking-block__header w-full" onClick={() => setOpen(!open)}>
        <div className="thinking-dots">
          <div className="thinking-dot animate-pulse-dot" />
          <div className="thinking-dot animate-pulse-dot" />
          <div className="thinking-dot animate-pulse-dot" />
        </div>
        <span>思考中{isStreaming ? "..." : ""}</span>
        <span className="text-[10px]">{open ? "▾" : "▸"}</span>
      </button>
      {open && (
        <div className="thinking-block__body">
          {text}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 bg-text-200 ml-0.5 animate-thinking-cursor rounded-sm align-middle" />
          )}
        </div>
      )}
    </div>
  );
}

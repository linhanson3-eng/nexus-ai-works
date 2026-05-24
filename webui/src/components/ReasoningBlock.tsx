import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";

export function ReasoningBlock({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  const [open, setOpen] = useState(true);
  if (!text || text === "undefined") return null;
  return (
    <div className="mb-2 border border-primary/10 rounded-md overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center gap-2 px-3 py-1.5 text-[11px] text-primary/60 hover:text-primary/80 transition-colors bg-primary/[0.02]"
      >
        <Brain className="w-3 h-3" />
        <span>思考过程{isStreaming ? "..." : ""}</span>
        <span className="flex-1" />
        {open ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
      </button>
      {open && (
        <div className="px-3 pb-2 text-xs text-muted-foreground/70 whitespace-pre-wrap leading-relaxed italic max-h-48 overflow-auto">
          {text}
          {isStreaming && (
            <span className="inline-block w-1.5 h-3.5 bg-primary/40 ml-0.5 animate-pulse rounded-sm align-middle" />
          )}
        </div>
      )}
    </div>
  );
}

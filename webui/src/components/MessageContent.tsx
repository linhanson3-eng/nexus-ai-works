export function MessageContent({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  if (!text || text === "undefined") return null;
  const lines = text.split("\n");
  const els: React.ReactNode[] = [];
  let inCode = false;
  let codeBuf: string[] = [];

  const flush = () => {
    if (codeBuf.length) {
      els.push(
        <pre
          key={els.length}
          className="bg-muted/30 border border-border rounded-md p-3 my-2 overflow-auto text-xs font-mono"
        >
          <code>{codeBuf.join("\n")}</code>
        </pre>
      );
      codeBuf = [];
    }
  };

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.startsWith("```")) {
      if (inCode) { flush(); inCode = false; } else { inCode = true; }
      continue;
    }
    if (inCode) { codeBuf.push(line); continue; }
    const parts = line.split(/(\*\*[^*]+\*\*)/g);
    const children = parts.map((p, j) => {
      if (p.startsWith("**") && p.endsWith("**"))
        return <strong key={j} className="text-foreground font-semibold">{p.slice(2, -2)}</strong>;
      const cp = p.split(/(`[^`]+`)/g);
      return cp.map((c, k) => {
        if (c.startsWith("`") && c.endsWith("`"))
          return <code key={k} className="bg-muted px-1 py-0.5 rounded text-xs font-mono">{c.slice(1, -1)}</code>;
        return c;
      });
    });
    els.push(<p key={i} className="min-h-[1.4em] leading-relaxed">{children.length ? children : " "}</p>);
  }
  flush();
  return (
    <div className="space-y-0.5">
      {els}
      {isStreaming && (
        <span className="inline-block w-1.5 h-4 bg-primary ml-0.5 animate-pulse rounded-sm align-middle" />
      )}
    </div>
  );
}

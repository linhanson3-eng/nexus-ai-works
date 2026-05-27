import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { useState, useCallback } from "react";

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    });
  }, [text]);
  return (
    <button className="code-block__copy" onClick={handleCopy}>
      {copied ? "✓ 已复制" : "复制"}
    </button>
  );
}

export function MessageContent({ text, isStreaming }: { text: string; isStreaming?: boolean }) {
  if (!text || text === "undefined") return null;

  return (
    <div className="font-claude-response-body space-y-3">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          code({ className, children, ...props }) {
            const match = /language-(\w+)/.exec(className || "");
            const codeText = String(children).replace(/\n$/, "");
            const isInline =
              !match && !codeText.includes("\n");

            if (isInline) {
              return (
                <code className="bg-bg-200 text-text-100 px-1 py-0.5 rounded text-[0.8125rem] font-mono">
                  {children}
                </code>
              );
            }

            return (
              <div className="code-block my-3">
                <div className="code-block__header">
                  <span className="code-block__lang">
                    {match ? match[1] : "text"}
                  </span>
                  <CopyButton text={codeText} />
                </div>
                <pre className="code-block__code">
                  <code className={className} {...props}>
                    {children}
                  </code>
                </pre>
              </div>
            );
          },
          h1: ({ children }) => (
            <h1 className="font-claude-response-title mt-6 mb-3">{children}</h1>
          ),
          h2: ({ children }) => (
            <h2 className="font-claude-response-heading mt-5 mb-2">{children}</h2>
          ),
          h3: ({ children }) => (
            <h3 className="text-lg font-semibold mt-4 mb-2">{children}</h3>
          ),
          p: ({ children }) => (
            <p className="min-h-[1.4em]">{children}</p>
          ),
          ul: ({ children }) => (
            <ul className="list-disc pl-5 space-y-1">{children}</ul>
          ),
          ol: ({ children }) => (
            <ol className="list-decimal pl-5 space-y-1">{children}</ol>
          ),
          blockquote: ({ children }) => (
            <blockquote className="border-l-2 border-border-200 pl-4 italic text-text-200">
              {children}
            </blockquote>
          ),
          a: ({ href, children }) => (
            <a
              href={href}
              target="_blank"
              rel="noopener noreferrer"
              className="text-accent-000 underline hover:opacity-80"
              style={{ color: "hsl(var(--accent-000))" }}
            >
              {children}
            </a>
          ),
          table: ({ children }) => (
            <div className="overflow-x-auto my-3">
              <table className="w-full border-collapse text-sm">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-border-200 bg-bg-200 px-3 py-2 text-left font-medium">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-border-200 px-3 py-2">{children}</td>
          ),
          hr: () => <hr className="border-border-200 my-4" />,
        }}
      >
        {text}
      </ReactMarkdown>
      {isStreaming && (
        <span className="inline-block w-2 h-4 bg-accent-000 ml-0.5 align-middle rounded-sm animate-thinking-cursor"
          style={{ background: "hsl(var(--accent-000))" }}
        />
      )}
    </div>
  );
}

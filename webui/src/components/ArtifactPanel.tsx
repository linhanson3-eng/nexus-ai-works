import { useEffect, useRef, useState, useCallback } from "react";
import { File, FileCode, FileText, FileJson, X, Download, Pencil, Check } from "lucide-react";
import type { Artifact } from "../lib/artifacts";

const typeIcon: Record<string, React.ComponentType<{ className?: string }>> = {
  code: FileCode,
  python: FileCode,
  javascript: FileCode,
  typescript: FileCode,
  json: FileJson,
  yaml: FileCode,
  markdown: FileText,
  text: FileText,
  html: FileCode,
  css: FileCode,
};

function getTypeFromName(name: string): string {
  const ext = name.split(".").pop()?.toLowerCase() || "";
  const map: Record<string, string> = {
    py: "python", js: "javascript", ts: "typescript", tsx: "typescript",
    json: "json", yaml: "yaml", yml: "yaml", md: "markdown",
    html: "html", css: "css", txt: "text",
  };
  return map[ext] || "code";
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatTime(ts: string): string {
  try {
    return new Date(ts).toLocaleTimeString("zh-CN", { hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function ArtifactPanel({
  artifacts,
  selected,
  selectedId,
  onSelect,
  onClose,
  onUpdate,
}: {
  artifacts: Artifact[];
  selected: Artifact | null;
  selectedId: string | null;
  onSelect: (id: string) => void;
  onClose: () => void;
  onUpdate?: (id: string, content: string) => void;
}) {
  if (artifacts.length === 0) {
    return (
      <div className="flex-1 flex flex-col items-center justify-center text-sm text-text-300 p-4 text-center gap-2">
        <File className="w-8 h-8 text-text-300/50" />
        <p>运行工作流后，产物会出现在这里</p>
        <p className="text-xs text-text-300/50">Agent 生成的代码、报告、配置文件等</p>
      </div>
    );
  }

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* File list */}
      <div className="border-b border-border">
        <div className="px-3 py-2 text-[10px] uppercase tracking-widest text-text-300">
          产物 ({artifacts.length})
        </div>
        {artifacts.map((a) => {
          const Icon = typeIcon[a.type] || FileCode;
          const isSelected = a.id === selectedId;
          return (
            <button
              key={a.id}
              onClick={() => onSelect(a.id)}
              className={`w-full flex items-center gap-2 px-3 py-2 text-left text-sm transition-colors ${
                isSelected
                  ? "bg-bg-200 text-text-000"
                  : "text-text-200 hover:bg-bg-200/50 hover:text-text-100"
              }`}
            >
              <Icon className="w-3.5 h-3.5 shrink-0 text-text-300" />
              <div className="min-w-0 flex-1">
                <div className="truncate text-xs">{a.name}</div>
                <div className="text-[10px] text-text-300">
                  {formatSize(a.size)} · {a.nodeLabel || formatTime(a.createdAt)}
                </div>
              </div>
            </button>
          );
        })}
      </div>

      {/* Editor / Viewer */}
      {selected ? (
        <ArtifactEditor artifact={selected} onUpdate={onUpdate} />
      ) : (
        <div className="flex-1 flex items-center justify-center text-xs text-text-300">
          选择一个文件查看
        </div>
      )}
    </div>
  );
}

function ArtifactEditor({
  artifact,
  onUpdate,
}: {
  artifact: Artifact;
  onUpdate?: (id: string, content: string) => void;
}) {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(artifact.content);
  const editorRef = useRef<HTMLDivElement>(null);
  const cmRef = useRef<any>(null);

  useEffect(() => {
    setContent(artifact.content);
    setEditing(false);
  }, [artifact.id, artifact.content]);

  useEffect(() => {
    if (!editing) {
      if (cmRef.current) {
        cmRef.current.destroy();
        cmRef.current = null;
      }
      return;
    }

    let cancelled = false;
    import("@codemirror/view").then(({ EditorView, keymap, lineNumbers, highlightActiveLine }) =>
      import("@codemirror/state").then(({ EditorState }) =>
        import("@codemirror/lang-javascript").then(({ javascript }) =>
          import("@codemirror/lang-python").then(({ python }) =>
            import("@codemirror/lang-json").then(({ json }) =>
              import("@codemirror/lang-yaml").then(({ yaml: yamlLang }) =>
                import("@codemirror/lang-markdown").then(({ markdown: mdLang }) =>
                  import("@codemirror/lang-html").then(({ html }) =>
                    import("@codemirror/lang-css").then(({ css }) =>
                      import("@codemirror/view").then((mod) => {
                        if (cancelled || !editorRef.current) return;
                        const { basicSetup } = mod as any;

                        const langMap: Record<string, () => any> = {
                          javascript, typescript: javascript,
                          python, json, yaml: yamlLang,
                          markdown: mdLang, html, css,
                        };

                        const lang = langMap[artifact.type]?.() || javascript();

                        const state = EditorState.create({
                          doc: content,
                          extensions: [
                            ...(basicSetup ? [basicSetup] : [lineNumbers(), highlightActiveLine()]),
                            lang,
                            EditorView.updateListener.of((update: any) => {
                              if (update.docChanged) {
                                setContent(update.state.doc.toString());
                              }
                            }),
                          ],
                        });

                        cmRef.current = new EditorView({
                          state,
                          parent: editorRef.current,
                        });
                      })
                    )
                  )
                )
              )
            )
          )
        )
      )
    );

    return () => {
      cancelled = true;
    };
  }, [editing, artifact.type]);

  const handleSave = useCallback(() => {
    onUpdate?.(artifact.id, content);
    setEditing(false);
  }, [artifact.id, content, onUpdate]);

  const handleDownload = useCallback(() => {
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = artifact.name;
    a.click();
    URL.revokeObjectURL(url);
  }, [artifact.name, content]);

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-medium text-text-100 truncate">{artifact.name}</span>
        <div className="flex items-center gap-1">
          {editing ? (
            <button
              onClick={handleSave}
              className="p-1.5 rounded text-success hover:bg-bg-200 transition-colors"
              title="保存"
            >
              <Check className="w-3.5 h-3.5" />
            </button>
          ) : (
            <>
              <button
                onClick={() => setEditing(true)}
                className="p-1.5 rounded text-text-200 hover:bg-bg-200 hover:text-text-100 transition-colors"
                title="编辑"
              >
                <Pencil className="w-3.5 h-3.5" />
              </button>
              <button
                onClick={handleDownload}
                className="p-1.5 rounded text-text-200 hover:bg-bg-200 hover:text-text-100 transition-colors"
                title="下载"
              >
                <Download className="w-3.5 h-3.5" />
              </button>
            </>
          )}
          <button
            onClick={() => {
              if (editing) setEditing(false);
            }}
            className="p-1.5 rounded text-text-200 hover:bg-bg-200 hover:text-text-100 transition-colors"
            title="关闭"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-hidden">
        {editing ? (
          <div ref={editorRef} className="h-full overflow-auto" />
        ) : (
          <pre className="h-full p-4 text-xs font-mono text-text-100 overflow-auto whitespace-pre-wrap">
            {content}
          </pre>
        )}
      </div>
    </div>
  );
}

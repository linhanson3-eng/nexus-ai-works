import { useState, useEffect, useCallback } from "react";
import { ChevronRight, Folder, FolderOpen, File, FileCode, FileText, Loader2 } from "lucide-react";
import { api } from "../lib/api";
import type { FileTreeNode } from "../lib/types";

function getFileIcon(name: string, isDir: boolean): React.ReactNode {
  if (isDir) return <Folder className="w-3.5 h-3.5 text-text-300 shrink-0" />;
  const ext = name.split(".").pop()?.toLowerCase() || "";
  if (["py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml"].includes(ext))
    return <FileCode className="w-3.5 h-3.5 text-text-300 shrink-0" />;
  if (["md", "txt", "html", "css"].includes(ext))
    return <FileText className="w-3.5 h-3.5 text-text-300 shrink-0" />;
  return <File className="w-3.5 h-3.5 text-text-300 shrink-0" />;
}

function TreeNode({
  node,
  depth,
  onSelect,
  selectedPath,
}: {
  node: FileTreeNode;
  depth: number;
  onSelect: (path: string) => void;
  selectedPath: string | null;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "directory";

  return (
    <div>
      <button
        onClick={() => {
          if (isDir) setOpen(!open);
          else onSelect(node.path);
        }}
        className={`flex items-center gap-1 w-full px-2 py-0.5 text-left text-xs transition-colors hover:bg-bg-300/50 ${
          selectedPath === node.path ? "bg-bg-300 text-text-000" : "text-text-200"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDir && (
          <ChevronRight
            className={`w-3 h-3 shrink-0 transition-transform ${open ? "rotate-90" : ""}`}
          />
        )}
        {isDir && open ? (
          <FolderOpen className="w-3.5 h-3.5 text-text-300 shrink-0" />
        ) : (
          getFileIcon(node.name, isDir)
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && open && node.children?.map((child) => (
        <TreeNode
          key={child.path}
          node={child}
          depth={depth + 1}
          onSelect={onSelect}
          selectedPath={selectedPath}
        />
      ))}
    </div>
  );
}

export function FileTree({
  workshop,
  onSelectFile,
  selectedPath,
}: {
  workshop: string;
  onSelectFile: (path: string) => void;
  selectedPath: string | null;
}) {
  const [files, setFiles] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [open, setOpen] = useState(true);

  const load = useCallback(async () => {
    try {
      const data = await api.listFiles(workshop);
      setFiles(data.files);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [workshop]);

  useEffect(() => { load(); }, [load]);

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 px-3 py-1 w-full text-[10px] uppercase tracking-widest text-text-300 hover:text-text-200 transition-colors"
      >
        <span className={`text-xs transition-transform ${open ? "rotate-90" : ""}`}>▸</span>
        文件
      </button>
      {open && (
        <div className="mt-0.5">
          {loading ? (
            <div className="flex items-center gap-2 px-3 py-2 text-xs text-text-300">
              <Loader2 className="w-3 h-3 animate-spin" />
              加载中...
            </div>
          ) : files.length === 0 ? (
            <div className="px-3 py-2 text-xs text-text-300">无文件</div>
          ) : (
            files.map((node) => (
              <TreeNode
                key={node.path}
                node={node}
                depth={0}
                onSelect={onSelectFile}
                selectedPath={selectedPath}
              />
            ))
          )}
        </div>
      )}
    </div>
  );
}

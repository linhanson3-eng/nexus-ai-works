import { useState, useEffect, useCallback, useRef } from "react";
import {
  ChevronRight, Folder, FolderOpen, File, FileCode, FileText,
  Loader2, Plus, Check, Search,
} from "lucide-react";
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
  node, depth, onSelect, selectedPath,
}: {
  node: FileTreeNode; depth: number;
  onSelect: (path: string) => void; selectedPath: string | null;
}) {
  const [open, setOpen] = useState(depth < 2);
  const isDir = node.type === "directory";

  return (
    <div>
      <button
        onClick={() => { if (isDir) setOpen(!open); else onSelect(node.path); }}
        className={`flex items-center gap-1 w-full px-2 py-0.5 text-left text-xs transition-colors hover:bg-bg-300/50 ${
          selectedPath === node.path ? "bg-bg-300 text-text-000" : "text-text-200"
        }`}
        style={{ paddingLeft: `${depth * 12 + 8}px` }}
      >
        {isDir && (
          <ChevronRight className={`w-3 h-3 shrink-0 transition-transform ${open ? "rotate-90" : ""}`} />
        )}
        {isDir && open ? (
          <FolderOpen className="w-3.5 h-3.5 text-text-300 shrink-0" />
        ) : (
          getFileIcon(node.name, isDir)
        )}
        <span className="truncate">{node.name}</span>
      </button>
      {isDir && open && node.children?.map((child) => (
        <TreeNode key={child.path} node={child} depth={depth + 1} onSelect={onSelect} selectedPath={selectedPath} />
      ))}
    </div>
  );
}

export function FileTree({
  workshop, workshops, onSwitchWorkspace,
  onSelectFile, selectedPath,
}: {
  workshop: string;
  workshops: string[];
  onSwitchWorkspace: (name: string, action?: "create") => void;
  onSelectFile: (path: string) => void;
  selectedPath: string | null;
}) {
  const [files, setFiles] = useState<FileTreeNode[]>([]);
  const [loading, setLoading] = useState(true);
  const [wsMenuOpen, setWsMenuOpen] = useState(false);
  const [addMenuOpen, setAddMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.listFiles(workshop);
      setFiles(data.files);
    } catch { /* */ }
    setLoading(false);
  }, [workshop]);

  useEffect(() => { load(); }, [load]);

  // Close menus on outside click
  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setWsMenuOpen(false);
        setAddMenuOpen(false);
      }
    };
    if (wsMenuOpen || addMenuOpen) document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, [wsMenuOpen, addMenuOpen]);

  return (
    <div className="flex-1 overflow-y-auto px-3 py-1" ref={menuRef}>
      {/* Workspace root — like Cursor/Codex folder header */}
      <div className="flex items-center gap-1 group">
        <button
          onClick={() => setWsMenuOpen(!wsMenuOpen)}
          className="flex items-center gap-1 flex-1 px-2 py-0.5 text-xs font-medium text-text-100 hover:bg-bg-300/50 rounded transition-colors"
        >
          <ChevronRight className="w-3 h-3 shrink-0 rotate-90" />
          <FolderOpen className="w-3.5 h-3.5 text-text-300 shrink-0" />
          <span className="truncate">{workshop.toUpperCase()}</span>
        </button>
        <button
          onClick={() => setAddMenuOpen(!addMenuOpen)}
          className="p-0.5 rounded opacity-0 group-hover:opacity-100 hover:bg-bg-300 text-text-200 hover:text-text-100 transition-all"
          title="新建"
        >
          <Plus className="w-3 h-3" />
        </button>
      </div>

      {/* Workspace switcher dropdown */}
      {wsMenuOpen && (
        <div className="absolute left-3 right-3 mt-1 z-50 bg-bg-000 border border-border rounded-lg shadow-lg py-1"
          style={{ top: "88px", background: "hsl(var(--bg-000))" }}>
          <div className="px-3 py-1.5 text-[10px] uppercase tracking-widest text-text-300">项目</div>
          {workshops.map((w) => (
            <button
              key={w}
              onClick={() => { onSwitchWorkspace(w); setWsMenuOpen(false); }}
              className={`flex items-center gap-2 w-full px-3 py-1.5 text-sm hover:bg-bg-200 transition-colors ${
                w === workshop ? "text-text-000 font-medium" : "text-text-200"
              }`}
            >
              <Folder className="w-3.5 h-3.5 text-text-300 shrink-0" />
              <span className="truncate flex-1 text-left">{w}</span>
              {w === workshop && <Check className="w-3.5 h-3.5 text-accent-000 shrink-0" />}
            </button>
          ))}
          <div className="border-t border-border mt-1 pt-1">
            <button
              onClick={() => { onSwitchWorkspace("", "create"); setWsMenuOpen(false); }}
              className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-text-200 hover:bg-bg-200 transition-colors"
            >
              <Plus className="w-3.5 h-3.5" />
              新建项目
            </button>
          </div>
        </div>
      )}

      {/* Add file/folder menu */}
      {addMenuOpen && (
        <div className="absolute left-3 mt-1 z-50 bg-bg-000 border border-border rounded-lg shadow-lg py-1"
          style={{ top: "110px", left: "20px", background: "hsl(var(--bg-000))" }}>
          <button
            onClick={() => {
              const name = prompt("文件名称:");
              if (name) onSwitchWorkspace(`new-file:${name}`, "create");
              setAddMenuOpen(false);
            }}
            className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-text-200 hover:bg-bg-200 transition-colors"
          >
            <File className="w-3.5 h-3.5" />
            新建文件
          </button>
          <button
            onClick={() => {
              const name = prompt("文件夹名称:");
              if (name) onSwitchWorkspace(`new-dir:${name}`, "create");
              setAddMenuOpen(false);
            }}
            className="flex items-center gap-2 w-full px-3 py-1.5 text-sm text-text-200 hover:bg-bg-200 transition-colors"
          >
            <Folder className="w-3.5 h-3.5" />
            新建文件夹
          </button>
        </div>
      )}

      {/* File tree */}
      <div className="mt-0.5">
        {loading ? (
          <div className="flex items-center gap-2 px-2 py-1 text-xs text-text-300">
            <Loader2 className="w-3 h-3 animate-spin" />
          </div>
        ) : (
          files.map((node) => (
            <TreeNode key={node.path} node={node} depth={0} onSelect={onSelectFile} selectedPath={selectedPath} />
          ))
        )}
      </div>
    </div>
  );
}

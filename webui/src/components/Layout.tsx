import { useState, useCallback, useEffect, createContext, useContext } from "react";
import { Outlet, useNavigate, useLocation } from "react-router-dom";
import {
  PanelLeftClose, PanelLeft, Sun, Moon, Monitor, Plus, Settings, MessageSquare,
} from "lucide-react";
import { getMainPanels, getAdvancedPanels } from "../lib/panels";
import { ArtifactPanel } from "./ArtifactPanel";
import { FileTree } from "./FileTree";
import { useArtifactContext } from "../lib/ArtifactContext";
import { api } from "../lib/api";
import type { SessionSummary } from "../lib/types";

// ── Sidebar State Context (shared between Layout, Sidebar, CollapsedToggle) ──

interface SidebarContextValue {
  collapsed: boolean;
  toggle: () => void;
}

const SidebarContext = createContext<SidebarContextValue>({
  collapsed: false,
  toggle: () => {},
});

function useSidebar() {
  return useContext(SidebarContext);
}

// ── Sidebar ──

function Sidebar() {
  const navigate = useNavigate();
  const location = useLocation();
  const { collapsed, toggle } = useSidebar();
  const { setRightOpen, addArtifact, setSelectedId } = useArtifactContext();
  const [advancedOpen, setAdvancedOpen] = useState(
    () => localStorage.getItem("nexus_advanced_open") !== "false"
  );
  const [sessionsOpen, setSessionsOpen] = useState(true);
  const [theme, setThemeState] = useState<"light" | "dark" | "system">(
    () => (localStorage.getItem("nexus_theme") as "light" | "dark" | "system") || "system"
  );
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [activeWorkspace, setActiveWorkspace] = useState(
    () => localStorage.getItem("nexus_active_workspace") || "demo"
  );
  const [workshops, setWorkshops] = useState<string[]>([activeWorkspace]);

  useEffect(() => {
    api.listWorkshops().then((list) => {
      setWorkshops(list.map((w: { name: string }) => w.name));
    }).catch(() => {});
  }, []);

  // Load session history
  useEffect(() => {
    api.listSessions(activeWorkspace).then(setSessions).catch(() => {});
  }, [activeWorkspace]);

  const handleWorkspaceChange = useCallback((name: string, action?: "create") => {
    if (action === "create") {
      if (name.startsWith("new-file:") || name.startsWith("new-dir:")) {
        // File/folder creation handled by FileTree
        return;
      }
      // Create new workspace
      api.createWorkspace(name).then(() => {
        setActiveWorkspace(name);
        localStorage.setItem("nexus_active_workspace", name);
        api.listWorkshops().then((list) =>
          setWorkshops(list.map((w: { name: string }) => w.name))
        ).catch(() => {});
      }).catch(() => {});
      return;
    }
    setActiveWorkspace(name);
    localStorage.setItem("nexus_active_workspace", name);
  }, []);

  const toggleAdvanced = useCallback(() => {
    setAdvancedOpen((v) => {
      localStorage.setItem("nexus_advanced_open", String(!v));
      return !v;
    });
  }, []);

  const cycleTheme = useCallback(() => {
    setThemeState((prev) => {
      const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
      const next = order[(order.indexOf(prev) + 1) % order.length];
      localStorage.setItem("nexus_theme", next);
      const root = document.documentElement;
      root.classList.remove("dark");
      if (next === "dark" || (next === "system" && window.matchMedia("(prefers-color-scheme: dark)").matches)) {
        root.classList.add("dark");
      }
      return next;
    });
  }, []);

  useEffect(() => {
    const handler = () => cycleTheme();
    window.addEventListener("nexus:cycle-theme", handler);
    return () => window.removeEventListener("nexus:cycle-theme", handler);
  }, [cycleTheme]);

  const handleFileSelect = useCallback(async (filePath: string) => {
    try {
      const resp = await fetch(`/api/workspaces/${activeWorkspace}/files/${encodeURIComponent(filePath)}`);
      if (resp.ok) {
        const data = await resp.json() as { name: string; path: string; content: string; size: number };
        const ext = filePath.split(".").pop()?.toLowerCase() || "";
        const typeMap: Record<string, string> = { py: "python", ts: "typescript", tsx: "typescript", js: "javascript", json: "json", yaml: "yaml", yml: "yaml", md: "markdown", html: "html", css: "css" };
        const artId = `file:${filePath}`;
        addArtifact({
          id: artId, name: data.name, type: typeMap[ext] || "text",
          content: data.content, workspace: activeWorkspace,
          createdAt: new Date().toISOString(), size: data.size,
        });
        setSelectedId(artId);
        setRightOpen(true);
      }
    } catch { /* ignore */ }
  }, [addArtifact, setSelectedId, setRightOpen, activeWorkspace]);

  if (collapsed) return null;

  const mainPanels = getMainPanels();
  const advancedPanels = getAdvancedPanels();
  const ThemeIcon = theme === "dark" ? Moon : theme === "light" ? Sun : Monitor;
  const isActive = (route: string) => location.pathname === route || location.pathname.startsWith(route + "/");

  return (
    <div className="app-layout__sidebar">
      {/* New chat */}
      <div className="px-3 pb-2 pt-3">
        <button
          onClick={() => {
            navigate("/chat");
            // Dispatch event to clear chat
            window.dispatchEvent(new CustomEvent("nexus:new-chat"));
          }}
          className="flex items-center gap-2 w-full px-3 py-2 rounded-lg text-sm font-medium
            bg-bg-300 text-text-100 hover:bg-bg-400 transition-colors"
          style={{ background: "hsl(var(--bg-300))" }}
        >
          <Plus className="w-4 h-4" />
          新建聊天
        </button>
      </div>

      <nav className="flex-1 overflow-y-auto px-3 py-1 space-y-0.5">
        {/* Session history */}
        {sessions.length > 0 && (
          <>
            <button
              onClick={() => setSessionsOpen(!sessionsOpen)}
              className="flex items-center gap-2 px-3 py-1 w-full text-[10px] uppercase tracking-widest text-text-300 hover:text-text-200 transition-colors"
            >
              <span className={`text-xs transition-transform ${sessionsOpen ? "rotate-90" : ""}`}>▸</span>
              最近对话
            </button>
            {sessionsOpen &&
              sessions.slice(0, 8).map((s) => (
                <button
                  key={s.id}
                  onClick={() => navigate(`/chat?session=${s.id}`)}
                  className="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-xs text-text-200 hover:bg-bg-300/50 hover:text-text-100 transition-colors"
                  title={s.first_message}
                >
                  <MessageSquare className="w-3.5 h-3.5 shrink-0" />
                  <div className="min-w-0 flex-1 text-left">
                    <div className="truncate">{s.first_message || "新对话"}</div>
                    <div className="text-[10px] text-text-300">{s.created_at}</div>
                  </div>
                </button>
              ))}
          </>
        )}

        {/* Main navigation */}
        {mainPanels.map((p) => {
          const Icon = p.icon;
          const active = isActive(p.route);
          return (
            <button
              key={p.id}
              onClick={() => navigate(p.route)}
              className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm transition-colors ${
                active
                  ? "bg-bg-300 text-text-000 font-medium"
                  : "text-text-200 hover:bg-bg-300/50 hover:text-text-100"
              }`}
              style={active ? { background: "hsl(var(--bg-300))" } : undefined}
            >
              <Icon className="w-4 h-4 shrink-0" />
              <span className="truncate">{p.label}</span>
            </button>
          );
        })}

        {/* File tree — primary project explorer (like Codex) */}
        <div className="pt-1">
          <FileTree
            workshop={activeWorkspace}
            workshops={workshops}
            onSwitchWorkspace={handleWorkspaceChange}
            onSelectFile={handleFileSelect}
            selectedPath={null}
          />
        </div>

        {/* Advanced section */}
        <div className="pt-3 pb-1">
          <button
            onClick={toggleAdvanced}
            className="flex items-center gap-2 px-3 py-1 w-full text-[10px] uppercase tracking-widest text-text-300 hover:text-text-200 transition-colors"
          >
            <span className={`text-xs transition-transform ${advancedOpen ? "rotate-90" : ""}`}>▸</span>
            高级
          </button>
        </div>

        {advancedOpen &&
          advancedPanels.map((p) => {
            const Icon = p.icon;
            const active = isActive(p.route);
            return (
              <button
                key={p.id}
                onClick={() => navigate(p.route)}
                className={`flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm transition-colors ${
                  active
                    ? "bg-bg-300 text-text-000 font-medium"
                    : "text-text-200 hover:bg-bg-300/50 hover:text-text-100"
                }`}
                style={active ? { background: "hsl(var(--bg-300))" } : undefined}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="truncate">{p.label}</span>
              </button>
            );
          })}
      </nav>

      {/* Bottom bar */}
      <div className="px-3 py-2 border-t border-border flex items-center justify-between">
        <button
          onClick={cycleTheme}
          className="p-2 rounded-lg text-text-200 hover:bg-bg-300 hover:text-text-100 transition-colors"
          title={`Theme: ${theme}`}
        >
          <ThemeIcon className="w-4 h-4" />
        </button>
        <button
          onClick={() => navigate("/settings")}
          className={`p-2 rounded-lg transition-colors ${
            location.pathname === "/settings"
              ? "bg-bg-300 text-text-000"
              : "text-text-200 hover:bg-bg-300 hover:text-text-100"
          }`}
          title="Settings"
        >
          <Settings className="w-4 h-4" />
        </button>
        <button
          onClick={toggle}
          className="p-2 rounded-lg text-text-200 hover:bg-bg-300 hover:text-text-100 transition-colors"
          title="Collapse sidebar"
        >
          <PanelLeftClose className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}

// ── Collapsed Toggle (shown in main area when sidebar hidden) ──

function CollapsedToggle() {
  const { collapsed, toggle } = useSidebar();
  if (!collapsed) return null;
  return (
    <button
      onClick={toggle}
      className="fixed left-3 top-3 z-50 p-2 rounded-lg bg-bg-000 border border-border text-text-200 hover:text-text-100 hover:bg-bg-200 transition-colors shadow-sm"
      title="展开侧栏"
    >
      <PanelLeft className="w-4 h-4" />
    </button>
  );
}

// ── Layout ──

export function Layout() {
  const [collapsed, setCollapsed] = useState(
    () => localStorage.getItem("nexus_sidebar_collapsed") === "true"
  );
  const {
    artifacts, selected, selectedId, setSelectedId,
    updateArtifact, rightOpen, setRightOpen, count,
  } = useArtifactContext();

  const toggleSidebar = useCallback(() => {
    setCollapsed((v) => {
      localStorage.setItem("nexus_sidebar_collapsed", String(!v));
      return !v;
    });
  }, []);

  return (
    <SidebarContext.Provider value={{ collapsed, toggle: toggleSidebar }}>
      <div
        className={`app-layout ${
          collapsed ? "app-layout--sidebar-collapsed" : ""
        } ${rightOpen ? "app-layout--right-open" : ""}`}
      >
        <Sidebar />
        <div className="app-layout__main">
          <CollapsedToggle />
          {/* Right panel toggle when count > 0 */}
          {count > 0 && !rightOpen && (
            <button
              onClick={() => setRightOpen(true)}
              className="fixed right-3 top-3 z-40 px-2.5 py-1.5 rounded-lg bg-bg-000 border border-border text-xs text-text-200 hover:text-text-100 hover:bg-bg-200 transition-colors shadow-sm flex items-center gap-1.5"
            >
              <span className="w-1.5 h-1.5 rounded-full bg-accent-000 animate-pulse-dot" style={{ background: "hsl(var(--accent-000))" }} />
              产物 ({count})
            </button>
          )}
          <Outlet />
        </div>
        {rightOpen && (
          <div className="app-layout__right">
            <div className="flex items-center justify-between px-4 py-3 border-b border-border">
              <span className="text-sm font-medium text-text-100">产物</span>
              <button
                onClick={() => setRightOpen(false)}
                className="p-1 rounded text-text-200 hover:text-text-100"
              >
                ✕
              </button>
            </div>
            <ArtifactPanel
              artifacts={artifacts}
              selected={selected}
              selectedId={selectedId}
              onSelect={setSelectedId}
              onClose={() => setRightOpen(false)}
              onUpdate={updateArtifact}
            />
          </div>
        )}
      </div>
    </SidebarContext.Provider>
  );
}

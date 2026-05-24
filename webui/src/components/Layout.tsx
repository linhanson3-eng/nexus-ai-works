import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Zap, Settings, Lightbulb, LogOut, User,
  Sun, Moon, Monitor, Search, ChevronRight, ChevronLeft,
} from "lucide-react";
import { useAuth } from "../lib/AuthContext";
import { useTheme } from "./ThemeProvider";

const navItems = [
  { to: "/dashboard", label: "总览", icon: Activity },
  { to: "/chat", label: "对话", icon: MessageSquare },
  { to: "/workshops", label: "项目", icon: Blocks },
  { to: "/factory", label: "模版", icon: Package },
  { to: "/kanban", label: "看板", icon: Kanban },
  { to: "/workflows", label: "工作流", icon: GitBranch },
  { to: "/market", label: "方案", icon: Lightbulb },
];

const themeIcons: Record<string, typeof Sun> = {
  light: Sun,
  dark: Moon,
  system: Monitor,
};

export function Layout() {
function loadSidebarPref(): boolean {
  const v = localStorage.getItem("nexus_sidebar_collapsed");
  if (v === null) return false; // first visit: expanded
  return v === "1";
}

  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const { theme, setTheme } = useTheme();
  const [collapsed, setCollapsed] = useState(loadSidebarPref);

  const toggleCollapsed = () => {
    const next = !collapsed;
    setCollapsed(next);
    localStorage.setItem("nexus_sidebar_collapsed", next ? "1" : "0");
  };

  const handleLogout = () => {
    logout();
    navigate("/auth", { replace: true });
  };

  const cycleTheme = () => {
    const order: Array<"light" | "dark" | "system"> = ["light", "dark", "system"];
    const idx = order.indexOf(theme);
    setTheme(order[(idx + 1) % order.length]);
  };

  const ThemeIcon = themeIcons[theme];

  return (
    <div className="flex h-screen bg-background">
      {/* Left sidebar */}
      <aside
        className={`shrink-0 bg-card border-r border-border flex flex-col transition-all duration-200 max-md:hidden ${
          collapsed ? "w-14" : "w-56"
        }`}
      >
        {/* Logo */}
        <button
          onClick={toggleCollapsed}
          className="h-12 flex items-center gap-2.5 px-3 border-b border-border hover:bg-accent/50 transition-colors"
        >
          <div className="w-7 h-7 rounded-md bg-primary/10 flex items-center justify-center shrink-0">
            <Zap className="w-3.5 h-3.5 text-primary" />
          </div>
          {!collapsed && (
            <span className="font-semibold text-sm tracking-tight">Nexus AI</span>
          )}
        </button>

        {/* User ping */}
        {user && !collapsed && (
          <div className="px-3 py-2.5 border-b border-border flex items-center gap-2">
            <div className="w-5 h-5 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
              <User className="w-2.5 h-2.5 text-primary" />
            </div>
            <span className="text-xs text-muted-foreground truncate">{user.username}</span>
            <span className="w-1.5 h-1.5 rounded-full bg-success shrink-0 ml-auto" />
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors ${
                  isActive
                    ? "bg-primary/10 text-primary"
                    : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
                }`
              }
              title={collapsed ? label : undefined}
            >
              <Icon className="w-4.5 h-4.5 shrink-0" />
              {!collapsed && <span className="text-sm">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-2 border-t border-border space-y-0.5">
          <NavLink
            to="/settings"
            className={({ isActive }) =>
              `flex items-center gap-2.5 px-2.5 py-2 rounded-md transition-colors ${
                isActive
                  ? "bg-primary/10 text-primary"
                  : "text-muted-foreground hover:text-foreground hover:bg-accent/50"
              }`
            }
            title={collapsed ? "设置" : undefined}
          >
            <Settings className="w-4.5 h-4.5 shrink-0" />
            {!collapsed && <span className="text-sm">设置</span>}
          </NavLink>
          <button
            onClick={handleLogout}
            className="flex items-center gap-2.5 px-2.5 py-2 rounded-md w-full text-muted-foreground hover:text-destructive hover:bg-destructive/5 transition-colors"
          >
            <LogOut className="w-4.5 h-4.5 shrink-0" />
            {!collapsed && <span className="text-sm">退出</span>}
          </button>
        </div>
      </aside>

      {/* Main area */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Top bar */}
        <header className="h-12 border-b border-border bg-card/50 backdrop-blur-sm flex items-center px-4 gap-3 shrink-0">
          <button
            onClick={toggleCollapsed}
            className="p-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md max-md:hidden"
          >
            {collapsed ? <ChevronRight className="w-4 h-4" /> : <ChevronLeft className="w-4 h-4" />}
          </button>

          <div className="flex-1" />

          {/* Search trigger — decorative for now */}
          <button
            onClick={() => console.log("[Search] global search triggered")}
            className="hidden sm:flex items-center gap-2 px-3 py-1.5 text-xs text-muted-foreground bg-accent/50 border border-border rounded-md hover:border-ring/30 transition-colors"
          >
            <Search className="w-3.5 h-3.5" />
            <span className="w-32 text-left">搜索...</span>
            <kbd className="text-[10px] px-1 py-0.5 rounded bg-muted text-muted-foreground font-mono">⌘K</kbd>
          </button>

          {/* Theme toggle */}
          <button
            onClick={cycleTheme}
            className="p-1.5 text-muted-foreground hover:text-foreground transition-colors rounded-md"
            title={`主题: ${theme}`}
          >
            <ThemeIcon className="w-4 h-4" />
          </button>
        </header>

        {/* Content */}
        <main className="flex-1 overflow-auto p-6 max-md:pb-20">
          <Outlet />
        </main>
      </div>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/90 backdrop-blur-xl border-t border-border z-40 flex justify-around py-2">
        {[...navItems, { to: "/settings", label: "设置", icon: Settings }].map(
          ({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] transition-colors ${
                  isActive ? "text-primary" : "text-muted-foreground"
                }`
              }
            >
              <Icon className="w-5 h-5" />
              {label}
            </NavLink>
          ),
        )}
      </nav>
    </div>
  );
}

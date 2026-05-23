import { useState } from "react";
import { NavLink, Outlet, useNavigate } from "react-router-dom";
import {
  MessageSquare, Activity, Blocks, Kanban, GitBranch,
  Package, Zap, Settings, Lightbulb, LogOut, User,
} from "lucide-react";
import { useAuth } from "../lib/AuthContext";

const navItems = [
  { to: "/dashboard", label: "总览", icon: Activity },
  { to: "/chat", label: "对话", icon: MessageSquare },
  { to: "/workshops", label: "我的项目", icon: Blocks },
  { to: "/factory", label: "模版仓库", icon: Package },
  { to: "/kanban", label: "时时看板", icon: Kanban },
  { to: "/workflows", label: "工作流", icon: GitBranch },
  { to: "/market", label: "解决方案", icon: Lightbulb },
];

export function Layout() {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [sidebarExpanded, setSidebarExpanded] = useState(false);

  const handleLogout = () => {
    logout();
    navigate("/auth", { replace: true });
  };

  const sidebarWidth = sidebarExpanded ? "w-52" : "w-14";

  return (
    <div className="flex h-screen bg-surface">
      {/* Left sidebar */}
      <aside className={`${sidebarWidth} border-r border-border bg-card/60 backdrop-blur-xl flex flex-col shrink-0 transition-all duration-200 max-md:hidden z-30`}>
        {/* Logo */}
        <button
          onClick={() => setSidebarExpanded(!sidebarExpanded)}
          className="p-3 border-b border-border flex items-center gap-2.5 hover:bg-white/5 transition-colors"
        >
          <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center shrink-0">
            <Zap className="w-4 h-4 text-accent" />
          </div>
          {sidebarExpanded && (
            <div className="min-w-0 text-left">
              <span className="font-semibold text-sm tracking-tight text-white block">Nexus</span>
              <p className="text-[9px] text-muted uppercase tracking-widest">v1.0</p>
            </div>
          )}
        </button>

        {/* User */}
        {user && sidebarExpanded && (
          <div className="px-3 py-2.5 border-b border-border">
            <div className="flex items-center gap-2">
              <div className="w-6 h-6 rounded-lg bg-accent/10 flex items-center justify-center shrink-0">
                <User className="w-3 h-3 text-accent" />
              </div>
              <span className="text-xs text-white truncate">{user.username}</span>
            </div>
          </div>
        )}

        {/* Nav */}
        <nav className="flex-1 p-2 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `flex items-center gap-3 px-2.5 py-2.5 rounded-lg transition-all duration-150 ${
                  isActive
                    ? "bg-accent/10 text-accent border border-accent/20"
                    : "text-slate-400 hover:text-white hover:bg-white/5"
                }`
              }
              title={label}
            >
              <Icon className="w-5 h-5 shrink-0" />
              {sidebarExpanded && <span className="text-sm whitespace-nowrap">{label}</span>}
            </NavLink>
          ))}
        </nav>

        {/* Bottom */}
        <div className="p-2 border-t border-border space-y-0.5">
          <NavLink to="/settings" className={({ isActive }) =>
            `flex items-center gap-3 px-2.5 py-2.5 rounded-lg transition-all duration-150 ${
              isActive ? "bg-accent/10 text-accent border border-accent/20" : "text-slate-400 hover:text-white hover:bg-white/5"
            }`
          } title="设置">
            <Settings className="w-5 h-5 shrink-0" />
            {sidebarExpanded && <span className="text-sm">设置</span>}
          </NavLink>
          <button onClick={handleLogout}
            className="flex items-center gap-3 px-2.5 py-2.5 rounded-lg w-full text-slate-400 hover:text-warning hover:bg-white/5 transition-colors">
            <LogOut className="w-5 h-5 shrink-0" />
            {sidebarExpanded && <span className="text-sm">退出</span>}
          </button>
        </div>

      </aside>

      {/* Main content */}
      <main className="flex-1 flex flex-col overflow-hidden min-w-0">
        <div className="flex-1 overflow-auto p-6 max-md:pb-20">
          <Outlet />
        </div>
      </main>

      {/* Mobile bottom nav */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/90 backdrop-blur-xl border-t border-border z-40 flex justify-around py-2">
        {[...navItems, { to: "/settings", label: "设置", icon: Settings }].map(({ to, label, icon: Icon }) => (
          <NavLink key={to} to={to} className={({ isActive }) =>
            `flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] transition-colors ${isActive ? "text-accent" : "text-muted"}`
          }>
            <Icon className="w-5 h-5" />
            {label}
          </NavLink>
        ))}
      </nav>
    </div>
  );
}

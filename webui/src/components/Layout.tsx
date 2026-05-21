import { NavLink, Outlet } from "react-router-dom";
import { MessageSquare, Activity, Blocks, Kanban, GitBranch, Zap, Settings } from "lucide-react";

const navItems = [
  { to: "/chat", label: "对话", icon: MessageSquare },
  { to: "/dashboard", label: "总览", icon: Activity },
  { to: "/workshops", label: "车间", icon: Blocks },
  { to: "/kanban", label: "看板", icon: Kanban },
  { to: "/workflows", label: "工作流", icon: GitBranch },
];

const navLinkClass = ({ isActive }: { isActive: boolean }) =>
  `flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
    isActive
      ? "bg-accent/10 text-accent border border-accent/20"
      : "text-slate-400 hover:text-white hover:bg-white/5"
  }`;

export function Layout() {
  return (
    <div className="flex h-screen bg-surface">
      {/* Sidebar */}
      <aside className="w-56 border-r border-border bg-card/40 backdrop-blur-xl flex flex-col shrink-0 max-md:hidden">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
              <Zap className="w-4 h-4 text-accent" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">AI 工厂</span>
          </div>
          <p className="text-[10px] text-muted mt-1.5 uppercase tracking-widest font-medium">管理控制台 v1.0</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map(({ to, label, icon: Icon }) => (
            <NavLink key={to} to={to} className={navLinkClass}>
              <Icon className="w-4 h-4" />
              {label}
            </NavLink>
          ))}
        </nav>
        {/* Settings at bottom */}
        <div className="p-3 border-t border-border">
          <NavLink to="/settings" className={navLinkClass}>
            <Settings className="w-4 h-4" />
            设置
          </NavLink>
        </div>
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-[11px] text-muted">系统运行中</span>
          </div>
        </div>
      </aside>

      {/* Mobile nav bar */}
      <nav className="md:hidden fixed bottom-0 left-0 right-0 bg-card/90 backdrop-blur-xl border-t border-border z-40 flex justify-around py-2">
        {[...navItems, { to: "/settings", label: "设置", icon: Settings }].map(({ to, label, icon: Icon }) => (
          <NavLink
            key={to}
            to={to}
            className={({ isActive }) =>
              `flex flex-col items-center gap-0.5 px-2 py-1 text-[10px] transition-colors ${isActive ? "text-accent" : "text-muted"}`
            }
          >
            <Icon className="w-5 h-5" />
            {label}
          </NavLink>
        ))}
      </nav>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6 max-md:pb-20">
        <Outlet />
      </main>
    </div>
  );
}

import { type ReactNode } from "react";
import { Activity, Blocks, GitBranch, Kanban, Zap } from "lucide-react";

const navItems = [
  { href: "/", label: "总览", icon: Activity },
  { href: "/workshops", label: "车间", icon: Blocks },
  { href: "/kanban", label: "看板", icon: Kanban },
  { href: "/workflows", label: "工作流", icon: GitBranch },
];

export function Layout({ children, active }: { children: ReactNode; active: string }) {
  return (
    <div className="flex h-screen bg-surface">
      {/* Sidebar */}
      <aside className="w-56 border-r border-border bg-card/40 backdrop-blur-xl flex flex-col shrink-0">
        <div className="p-5 border-b border-border">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-accent/20 flex items-center justify-center">
              <Zap className="w-4 h-4 text-accent" />
            </div>
            <span className="font-semibold text-sm tracking-tight text-white">AI 工厂</span>
          </div>
          <p className="text-[10px] text-muted mt-1.5 uppercase tracking-widest font-medium">管理控制台 v0.7</p>
        </div>
        <nav className="flex-1 p-3 space-y-0.5">
          {navItems.map(({ href, label, icon: Icon }) => (
            <a
              key={href}
              href={href}
              className={`flex items-center gap-2.5 px-3 py-2 rounded-lg text-sm transition-all duration-150 ${
                active === href
                  ? "bg-accent/10 text-accent border border-accent/20"
                  : "text-slate-400 hover:text-white hover:bg-white/5"
              }`}
            >
              <Icon className="w-4 h-4" />
              {label}
            </a>
          ))}
        </nav>
        <div className="p-4 border-t border-border">
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 rounded-full bg-success animate-pulse shadow-[0_0_8px_rgba(16,185,129,0.5)]" />
            <span className="text-[11px] text-muted">系统运行中</span>
          </div>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto p-6">{children}</main>
    </div>
  );
}

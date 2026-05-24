import { Bot, ChevronRight } from "lucide-react";

export function MyAssistant() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">我的助手</h1>
        <p className="text-muted-foreground text-sm mt-1">管理和配置你的 AI 助手</p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="bg-card border border-border rounded-xl p-6 hover:border-ring/30 transition-colors cursor-pointer">
          <div className="w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center mb-3">
            <Bot className="w-5 h-5 text-primary" />
          </div>
          <h3 className="text-sm font-medium">默认助手</h3>
          <p className="text-xs text-muted-foreground mt-1">通用 AI 助手，处理日常任务和对话</p>
          <div className="flex items-center gap-1 mt-3 text-xs text-primary">
            配置 <ChevronRight className="w-3 h-3" />
          </div>
        </div>

        <div className="bg-card border border-border rounded-xl p-6 border-dashed hover:border-ring/30 transition-colors cursor-pointer flex flex-col items-center justify-center text-center min-h-[140px]">
          <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center mb-3">
            <span className="text-muted-foreground text-lg">+</span>
          </div>
          <h3 className="text-sm font-medium text-muted-foreground">添加新助手</h3>
          <p className="text-xs text-muted-foreground/70 mt-1">从模板库创建专属助手</p>
        </div>
      </div>
    </div>
  );
}

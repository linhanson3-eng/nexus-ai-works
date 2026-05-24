import { Link, ArrowRight } from "lucide-react";

export function CollaborationChain() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold tracking-tight">协作链</h1>
        <p className="text-muted-foreground text-sm mt-1">串联多个 Agent，按步骤协作完成任务</p>
      </div>

      <div className="bg-card border border-border rounded-xl p-6 text-center">
        <Link className="w-8 h-8 mx-auto mb-3 opacity-30" />
        <p className="text-sm text-muted-foreground">暂无协作链</p>
        <p className="text-xs text-muted-foreground/70 mt-1">
          将多个 Agent 串联成链：前一个 Agent 的输出自动成为下一个的输入
        </p>
      </div>

      <div className="bg-card border border-border rounded-xl p-6">
        <h3 className="text-sm font-medium mb-3">建议模板</h3>
        <div className="grid gap-3 md:grid-cols-3">
          {[
            { title: "调研 → 编码 → 审查", desc: "先搜索资料，再写代码，最后代码审查" },
            { title: "生成 → 翻译 → 发布", desc: "生成内容，自动翻译，发布到多平台" },
            { title: "分析 → 总结 → 通知", desc: "分析数据，生成摘要，发送通知" },
          ].map((tpl) => (
            <button
              key={tpl.title}
              className="flex flex-col items-start gap-2 p-4 bg-background border border-border rounded-lg hover:border-ring/30 transition-colors text-left"
            >
              <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                {tpl.title.split(" → ").map((step, i) => (
                  <span key={i} className="flex items-center gap-1">
                    {i > 0 && <ArrowRight className="w-2.5 h-2.5 opacity-40" />}
                    <span className="px-1.5 py-0.5 rounded bg-muted text-[10px] font-mono">{step}</span>
                  </span>
                ))}
              </div>
              <p className="text-xs text-muted-foreground">{tpl.desc}</p>
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

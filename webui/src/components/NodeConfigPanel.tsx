import { useState } from "react";
import { X, Trash2, Play, ChevronDown } from "lucide-react";

interface Props {
  nodeId: string;
  label: string;
  nodeType: "agent" | "condition" | "transform";
  agentName: string;
  prompt: string;
  timeoutSeconds: number;
  notes: string;
  retryOnFail: boolean;
  continueOnFail: boolean;
  agents: { name: string; type: string; model: string }[];
  lastOutput?: string;
  lastStatus?: string;
  onChange: (field: string, value: string | number | boolean) => void;
  onDelete: () => void;
  onExecuteNode?: () => void;
  executing?: boolean;
}

type Tab = "params" | "settings" | "output";

export function NodeConfigPanel({
  nodeId,
  label,
  nodeType,
  agentName,
  prompt,
  timeoutSeconds,
  notes,
  retryOnFail,
  continueOnFail,
  agents,
  lastOutput,
  lastStatus,
  onChange,
  onDelete,
  onExecuteNode,
  executing,
}: Props) {
  const [tab, setTab] = useState<Tab>("params");

  const tabs: { key: Tab; label: string }[] = [
    { key: "params", label: "参数" },
    { key: "settings", label: "设置" },
    { key: "output", label: "输出" },
  ];

  const typeLabel =
    nodeType === "agent"
      ? "Agent 执行"
      : nodeType === "condition"
      ? "条件判断"
      : "代码转换";

  return (
    <div className="w-72 shrink-0 bg-card border border-border rounded-xl flex flex-col h-full">
      {/* Header with type badge */}
      <div className="p-4 pb-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] px-2 py-0.5 rounded-full bg-primary/10 text-primary font-medium">
            {typeLabel}
          </span>
          <button
            onClick={onDelete}
            className="p-1 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors"
          >
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        </div>
        <input
          value={label}
          onChange={(e) => onChange("label", e.target.value)}
          placeholder="节点名称"
          className="w-full bg-transparent text-sm font-semibold placeholder:text-muted-foreground/40 focus:outline-none border-b border-transparent focus:border-ring/30"
        />
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border">
        {tabs.map((t) => (
          <button
            key={t.key}
            onClick={() => setTab(t.key)}
            className={`flex-1 py-2 text-xs font-medium transition-colors ${
              tab === t.key
                ? "text-foreground border-b-2 border-primary"
                : "text-muted-foreground hover:text-foreground/70"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-auto p-4">
        {tab === "params" && (
          <div className="space-y-4">
            {/* Agent selector (agent node only) */}
            {nodeType === "agent" && (
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">
                  Agent
                </label>
                <div className="relative">
                  <select
                    value={agentName}
                    onChange={(e) => onChange("agent_name", e.target.value)}
                    className="w-full h-9 bg-background border border-border rounded-md px-3 py-2 text-sm appearance-none focus:outline-none focus:border-ring/50"
                  >
                    <option value="">选择 Agent...</option>
                    {agents.map((a) => (
                      <option key={a.name} value={a.name}>
                        {a.name}
                      </option>
                    ))}
                  </select>
                  <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
                </div>
              </div>
            )}

            {/* Prompt / Condition / Code */}
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">
                {nodeType === "condition"
                  ? "判断条件"
                  : nodeType === "transform"
                  ? "代码"
                  : "任务 Prompt"}
              </label>
              <textarea
                value={prompt}
                onChange={(e) => onChange("prompt", e.target.value)}
                placeholder={
                  nodeType === "condition"
                    ? "描述判断条件，例如：输出是否包含错误信息"
                    : nodeType === "transform"
                    ? "输入要执行的代码或数据转换指令"
                    : "描述 Agent 要执行的任务..."
                }
                rows={nodeType === "transform" ? 6 : 4}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-xs placeholder:text-muted-foreground/50 focus:outline-none focus:border-ring/50 resize-none font-mono"
              />
            </div>

            {/* Timeout */}
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">
                超时 (秒)
              </label>
              <input
                type="number"
                min={0}
                max={3600}
                value={timeoutSeconds}
                onChange={(e) =>
                  onChange("timeout_seconds", parseInt(e.target.value) || 300)
                }
                className="w-20 h-9 bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-ring/50"
              />
            </div>
          </div>
        )}

        {tab === "settings" && (
          <div className="space-y-4">
            {/* Notes */}
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">
                备注
              </label>
              <textarea
                value={notes}
                onChange={(e) => onChange("notes", e.target.value)}
                placeholder="节点说明（可选）..."
                rows={3}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-xs placeholder:text-muted-foreground/50 focus:outline-none focus:border-ring/50 resize-none"
              />
            </div>

            {/* Retry on Fail */}
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <div className="text-xs font-medium">失败时重试</div>
                <div className="text-[10px] text-muted-foreground">
                  最多重试 3 次
                </div>
              </div>
              <div className="relative">
                <input
                  type="checkbox"
                  checked={retryOnFail}
                  onChange={(e) =>
                    onChange("retry_on_fail", e.target.checked)
                  }
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-muted rounded-full peer-checked:bg-primary transition-colors" />
                <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
              </div>
            </label>

            {/* Continue on Fail */}
            <label className="flex items-center justify-between cursor-pointer">
              <div>
                <div className="text-xs font-medium">失败后继续执行</div>
                <div className="text-[10px] text-muted-foreground">
                  跳过此节点，继续下游
                </div>
              </div>
              <div className="relative">
                <input
                  type="checkbox"
                  checked={continueOnFail}
                  onChange={(e) =>
                    onChange("continue_on_fail", e.target.checked)
                  }
                  className="sr-only peer"
                />
                <div className="w-9 h-5 bg-muted rounded-full peer-checked:bg-primary transition-colors" />
                <div className="absolute left-0.5 top-0.5 w-4 h-4 bg-white rounded-full shadow peer-checked:translate-x-4 transition-transform" />
              </div>
            </label>
          </div>
        )}

        {tab === "output" && (
          <div className="space-y-3">
            {onExecuteNode && (
              <button
                onClick={onExecuteNode}
                disabled={executing}
                className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-xs font-medium hover:bg-primary/20 transition-colors disabled:opacity-50"
              >
                <Play className="w-3 h-3" />
                {executing ? "执行中..." : "执行此节点"}
              </button>
            )}

            {lastStatus && (
              <div className="flex items-center gap-1.5">
                <span
                  className={`inline-block w-2 h-2 rounded-full ${
                    lastStatus === "passed"
                      ? "bg-emerald-500/60"
                      : lastStatus === "failed"
                      ? "bg-red-400/40"
                      : "bg-muted-foreground/30"
                  }`}
                />
                <span className="text-[10px] text-muted-foreground">
                  {lastStatus === "passed"
                    ? "执行成功"
                    : lastStatus === "failed"
                    ? "执行失败"
                    : lastStatus}
                </span>
              </div>
            )}

            {lastOutput ? (
              <div className="p-3 bg-background border border-border rounded-lg">
                <pre className="text-[10px] text-muted-foreground whitespace-pre-wrap font-mono leading-relaxed max-h-48 overflow-auto">
                  {lastOutput.slice(0, 2000)}
                </pre>
              </div>
            ) : (
              <p className="text-[10px] text-muted-foreground/40 text-center py-6">
                暂无执行结果
              </p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

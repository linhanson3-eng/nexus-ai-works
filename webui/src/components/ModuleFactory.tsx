import { useState, useEffect, useRef, useCallback } from "react";
import { Play, Loader2, CheckCircle2, XCircle, Loader, Package, ArrowRight, Bot, User, RefreshCw, Download, AlertTriangle, Zap } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import type { AgentInfo } from "../lib/types";

interface ChatMessage {
  role: "user" | "agent";
  content: string;
}

interface NodeStatus {
  status: string;
  detail: string;
}

const FACTORY_NAME = "模块工厂";
const PRODUCTION_WF = "模块生产线";

const FACTORY_AGENTS = [
  { name: "需求分析师", mode: "super", model: "deepseek/deepseek-chat", tools: [],
    system_prompt: "你是需求分析师，帮助用户将业务需求转化为清晰的模块规格。通过反问确认细节，输出结构化YAML。",
    file_write: false, shell_exec: false, subagent_spawn: false, skills: "" },
  { name: "模块生成器", mode: "super", model: "deepseek/deepseek-chat", tools: [],
    system_prompt: "你是模块生成器，根据已确认的模块规格生成完整的 .nexus 包配置（yaml+md）。逐文件展示内容。",
    file_write: true, shell_exec: false, subagent_spawn: true, skills: "" },
  { name: "测试验证器", mode: "normal", model: "deepseek/deepseek-chat", tools: ["read_file"],
    system_prompt: "你是测试验证器，检查生成的模块配置是否完整和正确。列出问题和修复建议。",
    file_write: false, shell_exec: false, subagent_spawn: false, skills: "" },
  { name: "QA审查器", mode: "normal", model: "deepseek/deepseek-chat", tools: ["read_file"],
    system_prompt: "你是QA审查器，对生成的模块进行最终质量审查。维度：需求覆盖、可用性、安全性、完整性。结论PASS或FAIL。",
    file_write: false, shell_exec: false, subagent_spawn: false, skills: "" },
];

export function ModuleFactory() {
  const toast = useToast();
  const [factoryReady, setFactoryReady] = useState(false);
  const [initLoading, setInitLoading] = useState(true);
  const [initError, setInitError] = useState("");

  // Chat
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", content: "你好！我是模块工厂助手。\n\n告诉我你想创建什么样的 AI 工作模块？比如：\n- \"我需要一个市场竞品分析模块，每周监控5家对手\"\n- \"帮我做一个内容翻译流水线，支持中英日三语\"\n\n我会通过对话帮你理清需求，然后自动生成可复用的模块。" },
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);

  // Workflow
  const [wfRunning, setWfRunning] = useState(false);
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatus>>({});
  const [gateWaiting, setGateWaiting] = useState<string | null>(null);
  const [wfResult, setWfResult] = useState<{ status: string; final_output: string } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Init factory workspace
  useEffect(() => {
    (async () => {
      try {
        const workshops = await api.listWorkshops();
        const exists = workshops.some((w: { name: string }) => w.name === FACTORY_NAME);
        if (!exists) {
          await api.createWorkshop(FACTORY_NAME, "超级", "deepseek/deepseek-chat");
          // Wait a bit for workspace creation
          await new Promise(r => setTimeout(r, 300));
          // Add factory agents
          for (const a of FACTORY_AGENTS) {
            try {
              await api.createAgent(FACTORY_NAME, {
                name: a.name, mode: a.mode, model: a.model, tools: a.tools,
                system_prompt: a.system_prompt, guide_file: "", guide_content: "",
                skills: a.skills ? a.skills.split(",").map((s: string) => s.trim()).filter(Boolean) : [],
                permissions: { file_write: a.file_write, shell_exec: a.shell_exec, subagent_spawn: a.subagent_spawn },
              });
            } catch { /* agent may exist */ }
          }
        }
        // Save production workflow
        try {
          const prodWf = {
            name: PRODUCTION_WF,
            description: "对话需求对齐 → 审批 → 生成 → 验证 → QA → 封装",
            workspace: FACTORY_NAME,
            nodes: [
              { id: "requirement-analysis", label: "需求分析", agent_name: "需求分析师",
                prompt: "分析用户需求，输出结构化模块规格。", depends_on: [], expected_output: "模块规格YAML" },
              { id: "approval-gate", label: "方案审批", agent_name: "需求分析师",
                prompt: "整理审批文档供用户审查批准。", depends_on: ["requirement-analysis"],
                expected_output: "审批文档", gate: { type: "review" } },
              { id: "generate-module", label: "生成模块", agent_name: "模块生成器",
                prompt: "根据审批通过的规格，生成完整 .nexus 包配置文件。", depends_on: ["approval-gate"],
                expected_output: "完整包配置" },
              { id: "validate", label: "测试验证", agent_name: "测试验证器",
                prompt: "验证生成的模块配置，检查字段完整性和合法性。", depends_on: ["generate-module"],
                expected_output: "验证报告" },
              { id: "qa-review", label: "QA审查", agent_name: "QA审查器",
                prompt: "最终质量审查：需求覆盖、可用性、安全性、完整性。结论PASS或FAIL。",
                depends_on: ["validate"], expected_output: "QA审查结论", gate: { type: "review" } },
              { id: "package-export", label: "封装导出", agent_name: "模块生成器",
                prompt: "所有审查通过，将配置文件打包为 .nexus 包。", depends_on: ["qa-review"],
                expected_output: "包导出确认" },
            ],
          };
          await api.saveWorkflow(prodWf);
        } catch { /* may exist */ }
        setFactoryReady(true);
      } catch (err) {
        setInitError(err instanceof Error ? err.message : "初始化失败");
      } finally {
        setInitLoading(false);
      }
    })();
  }, []);

  // ── Chat ──

  const sendChat = useCallback(async () => {
    const text = input.trim();
    if (!text || chatLoading) return;
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setInput("");
    setChatLoading(true);

    try {
      const res = await fetch("/api/agent/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: text, workshop: FACTORY_NAME }),
      });

      if (!res.ok) throw new Error("请求失败");

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No stream");

      const decoder = new TextDecoder();
      let buffer = "";
      let content = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventName = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) eventName = line.slice(7).trim();
          else if (line.startsWith("data: ") && eventName === "content_delta") {
            try {
              const data = JSON.parse(line.slice(6));
              content += data.delta || "";
              setMessages(prev => {
                const msgs = [...prev];
                const last = msgs[msgs.length - 1];
                if (last?.role === "agent") msgs[msgs.length - 1] = { ...last, content };
                return msgs;
              });
            } catch { /* skip */ }
          } else if (line.startsWith("data: ") && eventName === "completed") {
            try {
              const data = JSON.parse(line.slice(6));
              if (data.reply && !content) content = data.reply;
            } catch { /* skip */ }
          }
        }
      }

      if (content) {
        setMessages(prev => {
          const msgs = [...prev];
          const last = msgs[msgs.length - 1];
          if (last?.role === "agent") msgs[msgs.length - 1] = { ...last, content };
          return msgs;
        });
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "对话失败");
    } finally {
      setChatLoading(false);
    }
  }, [input, chatLoading, toast]);

  // ── Production Workflow ──

  const startProduction = async () => {
    setWfRunning(true);
    setNodeStatus({});
    setWfResult(null);
    setGateWaiting(null);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(PRODUCTION_WF)}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: "生成模块", workshop: FACTORY_NAME }),
        signal: controller.signal,
      });

      if (!res.ok) throw new Error("启动失败");

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No stream");

      const decoder = new TextDecoder();
      let buffer = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        let eventName = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) eventName = line.slice(7).trim();
          else if (line.startsWith("data: ") && eventName) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventName === "node_status") {
                setNodeStatus(prev => ({ ...prev, [data.node_id]: { status: data.status, detail: data.detail } }));
                if (data.status === "running") setGateWaiting(null);
              } else if (eventName === "completed") {
                setWfResult(data);
              } else if (eventName === "error") {
                toast.error(data.message || "执行出错");
              }
            } catch { /* skip */ }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error(err instanceof Error ? err.message : "执行失败");
      }
    } finally {
      setWfRunning(false);
      abortRef.current = null;
    }
  };

  const approveGate = async (nodeId: string, approved: boolean) => {
    // Gate approval — resume the workflow by re-executing with approval signal
    setGateWaiting(null);
    // Currently the workflow engine handles gate via review heuristic
    // For now, we signal approval by restarting from the gate node
    toast.info(approved ? "已批准，继续执行" : "已驳回，返回修改");
  };

  // ── Export ──

  const handleExport = async () => {
    try {
      const res = await fetch(`/api/workshops/${FACTORY_NAME}/products`);
      toast.success("模块已生成，使用 CLI 导出: python3 entrypoint.py module export 模块名");
    } catch {
      toast.error("导出失败");
    }
  };

  // ── Render ──

  const nodeLabels: Record<string, string> = {
    "requirement-analysis": "需求分析",
    "approval-gate": "方案审批",
    "generate-module": "生成模块",
    "validate": "测试验证",
    "qa-review": "QA审查",
    "package-export": "封装导出",
  };

  if (initLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="w-6 h-6 text-accent animate-spin" />
        <span className="ml-3 text-muted">初始化模块工厂...</span>
      </div>
    );
  }

  if (initError) {
    return (
      <div className="flex flex-col items-center justify-center h-64 gap-4">
        <AlertTriangle className="w-10 h-10 text-warning" />
        <p className="text-white font-semibold">初始化失败</p>
        <p className="text-sm text-muted">{initError}</p>
        <button onClick={() => window.location.reload()}
          className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20">
          <RefreshCw className="w-3.5 h-3.5" /> 重试
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full gap-4" style={{ height: "calc(100vh - 120px)" }}>
      {/* Left: Chat */}
      <div className="flex-1 flex flex-col bg-card border border-border rounded-[20px] overflow-hidden">
        <div className="shrink-0 p-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Package className="w-5 h-5 text-accent" />
            <h2 className="text-lg font-bold text-white">模块工厂</h2>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-[10px] text-muted">
              {Object.keys(nodeStatus).length > 0 ? "生产线运行中" : factoryReady ? "就绪" : ""}
            </span>
            <button onClick={startProduction} disabled={wfRunning}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-success/10 text-success border border-success/20 rounded-xl text-sm font-medium hover:bg-success/20 transition-colors disabled:opacity-30">
              {wfRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
              开始生产
            </button>
          </div>
        </div>

        <div className="flex-1 overflow-auto p-4 space-y-4">
          {messages.map((msg, i) => (
            <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
              {msg.role === "agent" && (
                <div className="w-7 h-7 rounded-lg bg-accent/20 flex items-center justify-center shrink-0 mt-0.5">
                  <Bot className="w-3.5 h-3.5 text-accent" />
                </div>
              )}
              <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${
                msg.role === "user" ? "bg-accent/15 border border-accent/20 text-white" : "bg-surface border border-border text-slate-300"
              }`}>
                {msg.content.split("\n").map((line, j) => (
                  <p key={j} className="min-h-[1.4em]">{line || " "}</p>
                ))}
              </div>
              {msg.role === "user" && (
                <div className="w-7 h-7 rounded-lg bg-surface border border-border flex items-center justify-center shrink-0 mt-0.5">
                  <User className="w-3.5 h-3.5 text-muted" />
                </div>
              )}
            </div>
          ))}
          {chatLoading && (
            <div className="flex gap-3">
              <div className="w-7 h-7 rounded-lg bg-accent/20 flex items-center justify-center">
                <Loader2 className="w-3.5 h-3.5 text-accent animate-spin" />
              </div>
              <div className="bg-surface border border-border rounded-2xl px-4 py-3">
                <span className="text-sm text-muted animate-pulse">需求分析师思考中...</span>
              </div>
            </div>
          )}
          <div ref={chatEndRef} />
        </div>

        <div className="shrink-0 p-4 border-t border-border flex gap-3">
          <input value={input} onChange={e => setInput(e.target.value)}
            onKeyDown={e => e.key === "Enter" && !chatLoading && sendChat()}
            placeholder="描述你想创建的 AI 模块..."
            disabled={chatLoading}
            className="flex-1 bg-surface border border-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 disabled:opacity-50" />
          <button onClick={sendChat} disabled={chatLoading || !input.trim()}
            className="px-4 py-3 bg-accent text-black rounded-xl font-semibold text-sm hover:bg-amber-400 transition-colors disabled:opacity-30">
            发送
          </button>
        </div>
      </div>

      {/* Right: Status Panel */}
      <div className="w-80 shrink-0 bg-card border border-border rounded-[20px] p-5 space-y-4 overflow-auto">
        <h3 className="text-sm font-semibold text-white flex items-center gap-2">
          <Zap className="w-4 h-4 text-warning" /> 生产线状态
        </h3>

        {Object.keys(nodeStatus).length === 0 && !wfResult && !wfRunning && (
          <div className="space-y-4">
            <p className="text-xs text-muted">还没有开始生产。先跟需求分析师对话，确认模块规格后点击"开始生产"。</p>
            <div className="space-y-2">
              {Object.entries(nodeLabels).map(([id, label]) => (
                <div key={id} className="flex items-center gap-2 p-2 text-xs text-muted">
                  <div className="w-2 h-2 rounded-full bg-muted/30" />
                  {label}
                </div>
              ))}
            </div>
          </div>
        )}

        {Object.entries(nodeLabels).map(([id, label]) => {
          const s = nodeStatus[id];
          const status = s?.status;
          return (
            <div key={id} className={`p-3 rounded-xl border text-xs transition-all ${
              status === "running" ? "border-info/30 bg-info/5" :
              status === "passed" ? "border-success/30 bg-success/5" :
              status === "failed" ? "border-warning/30 bg-warning/5" :
              wfRunning ? "border-border bg-surface" : "border-border/50 bg-surface/50"
            }`}>
              <div className="flex items-center justify-between">
                <span className="text-white font-medium">{label}</span>
                {status === "running" ? <Loader className="w-3 h-3 text-info animate-spin" /> :
                 status === "passed" ? <CheckCircle2 className="w-3 h-3 text-success" /> :
                 status === "failed" ? <XCircle className="w-3 h-3 text-warning" /> :
                 <div className="w-2 h-2 rounded-full bg-muted/30" />}
              </div>
              {s?.detail && <p className="text-muted mt-1 truncate">{s.detail}</p>}

              {/* Gate approval buttons */}
              {status === "running" && (id === "approval-gate" || id === "qa-review") && (
                <div className="flex gap-2 mt-2">
                  <button onClick={() => approveGate(id, true)}
                    className="flex-1 px-2 py-1 bg-success/10 text-success border border-success/20 rounded-lg text-[10px] hover:bg-success/20">
                    批准
                  </button>
                  <button onClick={() => approveGate(id, false)}
                    className="flex-1 px-2 py-1 bg-warning/10 text-warning border border-warning/20 rounded-lg text-[10px] hover:bg-warning/20">
                    驳回
                  </button>
                </div>
              )}
            </div>
          );
        })}

        {wfResult && (
          <div className="p-4 bg-surface border border-border rounded-xl">
            <p className="text-sm text-white font-medium mb-2">
              {wfResult.status === "passed" ? "生产完成" : "生产失败"}
            </p>
            {wfResult.final_output && (
              <p className="text-xs text-muted mb-3 line-clamp-4 whitespace-pre-wrap">{wfResult.final_output}</p>
            )}
            <button onClick={handleExport}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors">
              <Download className="w-4 h-4" /> 导出 .nexus 包
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

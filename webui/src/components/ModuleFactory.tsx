import { useState, useEffect, useRef, useCallback } from "react";
import { Play, Loader2, CheckCircle2, XCircle, Loader, Package, Bot, User, Download, AlertTriangle, Zap, Upload, Store, Factory, Tag } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import type { Workshop } from "../lib/types";

const FACTORY_NAME = "模块工厂";
const PRODUCTION_WF = "模块生产线";
const CATEGORIES = ["全部", "市场分析", "内容创作", "代码工具", "数据处理", "法务合规", "营销推广", "客服支持", "项目管理", "金融分析", "教育培训", "医疗健康", "其他"];

interface ChatMessage { role: "user" | "agent"; content: string; }
interface NodeStatus { status: string; detail: string; }

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
    system_prompt: "你是QA审查器，对生成的模块进行最终质量审查。结论PASS或FAIL。",
    file_write: false, shell_exec: false, subagent_spawn: false, skills: "" },
];

const nodeLabels: Record<string, string> = {
  "requirement-analysis": "需求分析", "approval-gate": "方案审批",
  "generate-module": "生成模块", "validate": "测试验证",
  "qa-review": "QA审查", "package-export": "封装导出",
};

export function ModuleFactory() {
  const toast = useToast();
  const [tab, setTab] = useState<"store" | "factory">("store");
  const [initLoading, setInitLoading] = useState(true);
  const [initError, setInitError] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Store state
  const [workshops, setWorkshops] = useState<Workshop[]>([]);
  const [activeCategory, setActiveCategory] = useState("全部");
  const [importing, setImporting] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importName, setImportName] = useState("");
  // Factory state
  const [, setFactoryReady] = useState(false);
  const [, setImportDesc] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    { role: "agent", content: "你好！我是模块工厂助手。\n\n告诉我你想创建什么样的 AI 工作模块？比如：\n- \"我需要一个市场竞品分析模块，每周监控5家对手\"\n- \"帮我做一个内容翻译流水线，支持中英日三语\"\n\n我会通过对话帮你理清需求，然后自动生成可复用的模块。" },
  ]);
  const [input, setInput] = useState("");
  const [chatLoading, setChatLoading] = useState(false);
  const [wfRunning, setWfRunning] = useState(false);
  const [nodeStatus, setNodeStatus] = useState<Record<string, NodeStatus>>({});
  const [wfResult, setWfResult] = useState<{ status: string; final_output: string } | null>(null);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Scroll chat
  useEffect(() => { chatEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  // Load workshops for store
  const loadWorkshops = useCallback(async () => {
    try { setWorkshops(await api.listWorkshops()); } catch (err) { console.warn("加载车间列表失败", err); }
  }, []);

  // Init
  useEffect(() => {
    (async () => {
      try {
        await loadWorkshops();
        void (workshops.some(w => w.name === FACTORY_NAME) || true); // check after load
        const ws = await api.listWorkshops();
        const factoryExists = ws.some((w: { name: string }) => w.name === FACTORY_NAME);
        if (!factoryExists) {
          await api.createWorkshop(FACTORY_NAME, "超级", "deepseek/deepseek-chat");
          await new Promise(r => setTimeout(r, 300));
          for (const a of FACTORY_AGENTS) {
            try {
              await api.createAgent(FACTORY_NAME, {
                name: a.name, mode: a.mode, model: a.model, tools: a.tools,
                system_prompt: a.system_prompt, guide_file: "", guide_content: "",
                skills: a.skills ? a.skills.split(",").map((s: string) => s.trim()).filter(Boolean) : [],
                permissions: { file_write: a.file_write, shell_exec: a.shell_exec, subagent_spawn: a.subagent_spawn },
              });
            } catch (err) { console.warn("创建 Agent 失败（可能已存在）", err); }
          }
        }
        try {
          await api.saveWorkflow({
            name: PRODUCTION_WF, description: "生产线", workspace: FACTORY_NAME,
            nodes: [
              { id: "requirement-analysis", label: "需求分析", agent_name: "需求分析师", prompt: "分析需求，输出模块规格。", depends_on: [], expected_output: "" },
              { id: "approval-gate", label: "方案审批", agent_name: "需求分析师", prompt: "整理审批文档。", depends_on: ["requirement-analysis"], expected_output: "", gate: { type: "review" } },
              { id: "generate-module", label: "生成模块", agent_name: "模块生成器", prompt: "生成完整配置。", depends_on: ["approval-gate"], expected_output: "" },
              { id: "validate", label: "测试验证", agent_name: "测试验证器", prompt: "验证配置。", depends_on: ["generate-module"], expected_output: "" },
              { id: "qa-review", label: "QA审查", agent_name: "QA审查器", prompt: "最终审查。", depends_on: ["validate"], expected_output: "", gate: { type: "review" } },
              { id: "package-export", label: "封装导出", agent_name: "模块生成器", prompt: "打包。", depends_on: ["qa-review"], expected_output: "" },
            ],
          });
        } catch { /* */ }
        setFactoryReady(true);
      } catch (err) {
        setInitError(err instanceof Error ? err.message : "初始化失败");
      } finally {
        setInitLoading(false);
      }
    })();
  }, []);

  // ── Store: Export / Import / Remove ──

  const exportWorkspace = async (wsName: string) => {
    try {
      const res = await fetch(`/api/workshops/${wsName}/export`, { method: "POST" });
      if (!res.ok) throw new Error("导出失败");
      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = `${wsName}.nexus.zip`; a.click();
      URL.revokeObjectURL(url);
      toast.success(`"${wsName}" 已导出`);
    } catch { toast.error("导出失败"); }
  };

  const handleFileSelect = (file: File) => {
    const baseName = file.name.replace(/\.(zip|nexus)$/i, "");
    setImportFile(file);
    setImportName(baseName);
    setImportDesc("");
  };

  const confirmImport = async () => {
    if (!importFile || !importName.trim()) return;
    setImporting(true);
    try {
      const formData = new FormData();
      formData.append("file", importFile);
      formData.append("name", importName.trim());
      const res = await fetch("/api/workshops/import", { method: "POST", body: formData });
      if (!res.ok) { const e = await res.json().catch(() => ({ detail: "导入失败" })); throw new Error(e.detail); }
      toast.success(`"${importName.trim()}" 已导入`);
      setImportFile(null);
      loadWorkshops();
    } catch (err) { toast.error(err instanceof Error ? err.message : "导入失败"); }
    finally { setImporting(false); }
  };

  const removeWorkspace = async (wsName: string) => {
    try {
      await api.deleteWorkshop(wsName);
      toast.success(`"${wsName}" 已卸载`);
      loadWorkshops();
    } catch { toast.error("卸载失败"); }
  };

  // ── Factory: Chat ──

  const sendChat = useCallback(async () => {
    const text = input.trim();
    if (!text || chatLoading) return;
    setMessages(prev => [...prev, { role: "user", content: text }]);
    setInput(""); setChatLoading(true);
    try {
      const res = await fetch("/api/agent/run/stream", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: text, workshop: FACTORY_NAME }),
      });
      if (!res.ok) throw new Error("请求失败");
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No stream");
      const decoder = new TextDecoder(); let buffer = "", content = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop() || "";
        let ev = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) ev = line.slice(7).trim();
          else if (line.startsWith("data: ") && ev === "content_delta") {
            try { content += JSON.parse(line.slice(6)).delta || ""; }
            catch { /* */ }
            setMessages(prev => { const m = [...prev]; const l = m[m.length-1]; if (l?.role==="agent") m[m.length-1]={...l,content}; return m; });
          } else if (line.startsWith("data: ") && ev === "completed") {
            try { const d = JSON.parse(line.slice(6)); if (d.reply && !content) content = d.reply; } catch { /* */ }
          }
        }
      }
      if (content) setMessages(prev => { const m=[...prev]; const l=m[m.length-1]; if(l?.role==="agent") m[m.length-1]={...l,content}; return m; });
    } catch (err) { toast.error(err instanceof Error ? err.message : "对话失败"); }
    finally { setChatLoading(false); }
  }, [input, chatLoading, toast]);

  // ── Factory: Production ──

  const startProduction = async () => {
    setWfRunning(true); setNodeStatus({}); setWfResult(null);
    const ctrl = new AbortController(); abortRef.current = ctrl;
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(PRODUCTION_WF)}/execute`, {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: "生成模块", workshop: FACTORY_NAME }), signal: ctrl.signal,
      });
      if (!res.ok) throw new Error("启动失败");
      const reader = res.body?.getReader();
      if (!reader) throw new Error("No stream");
      const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop() || "";
        let ev = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) ev = line.slice(7).trim();
          else if (line.startsWith("data: ") && ev) {
            try {
              const d = JSON.parse(line.slice(6));
              if (ev === "node_status") setNodeStatus(p => ({ ...p, [d.node_id]: { status: d.status, detail: d.detail } }));
              else if (ev === "completed") setWfResult(d);
              else if (ev === "error") toast.error(d.message || "出错");
            } catch { /* */ }
          }
        }
      }
    } catch (err) { if ((err as Error).name !== "AbortError") toast.error((err as Error).message); }
    finally { setWfRunning(false); abortRef.current = null; }
  };

  // ── Filtered modules ──

  const moduleWorkshops = workshops.filter(w => w.name !== FACTORY_NAME);
  const filtered = activeCategory === "全部" ? moduleWorkshops : moduleWorkshops;

  if (initLoading) {
    return <div className="flex items-center justify-center h-64"><Loader2 className="w-6 h-6 text-accent animate-spin" /><span className="ml-3 text-muted">加载中...</span></div>;
  }
  if (initError) {
    return <div className="flex flex-col items-center justify-center h-64 gap-4"><AlertTriangle className="w-10 h-10 text-warning" /><p className="text-white font-semibold">加载失败</p><p className="text-sm text-muted">{initError}</p></div>;
  }

  return (
    <div className="flex flex-col h-full gap-4" style={{ height: "calc(100vh - 120px)" }}>
      {/* Tab bar */}
      <div className="flex items-center justify-between shrink-0">
        <div className="flex items-center gap-1 bg-card border border-border rounded-xl p-1">
          <button onClick={() => setTab("store")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "store" ? "bg-accent/15 text-accent" : "text-muted hover:text-white"}`}>
            <Store className="w-4 h-4" /> 模块仓库
          </button>
          <button onClick={() => setTab("factory")}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors ${tab === "factory" ? "bg-accent/15 text-accent" : "text-muted hover:text-white"}`}>
            <Factory className="w-4 h-4" /> 模块工厂
          </button>
        </div>
      </div>

      {tab === "store" ? (
        <div className="flex-1 flex gap-4 overflow-hidden">
          <div className="flex-1 overflow-auto">
            {/* Import + categories */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex gap-1.5 flex-wrap">
              {CATEGORIES.map(c => (
                <button key={c} onClick={() => setActiveCategory(c)}
                  className={`px-3 py-1.5 rounded-lg text-xs font-medium border transition-colors ${
                    activeCategory === c ? "bg-accent/15 text-accent border-accent/30" : "bg-surface border-border text-muted hover:text-white hover:border-accent/20"
                  }`}>
                  {c === "全部" ? <Tag className="w-3 h-3 inline mr-1" /> : null}{c}
                </button>
              ))}
              </div>
              <input type="file" ref={fileInputRef} accept=".zip,.nexus" onChange={e => { const f = e.target.files?.[0]; if (f) { handleFileSelect(f); e.target.value = ""; } }} className="hidden" />
              <button onClick={() => fileInputRef.current?.click()} disabled={importing}
                className="flex items-center gap-1.5 px-3 py-2 bg-info/10 text-info border border-info/20 rounded-xl text-sm font-medium hover:bg-info/20 disabled:opacity-30 shrink-0">
                {importing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />} 导入
              </button>
            </div>

            {filtered.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-20 gap-4">
                <Package className="w-12 h-12 text-muted/40" />
                <div className="text-center">
                  <p className="text-white font-semibold">暂无模块</p>
                  <p className="text-sm text-muted mt-1">点击「导入」上传 .nexus 包，或切换到「模块工厂」创建新模块</p>
                </div>
              </div>
            ) : (
              <div className="grid grid-cols-2 gap-3 max-lg:grid-cols-1">
                {filtered.map(w => (
                  <div key={w.name} className="bg-card border border-border rounded-[16px] p-4 hover:border-accent/10 transition-colors group">
                    <div className="flex items-start justify-between">
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <Package className="w-4 h-4 text-accent shrink-0" />
                          <h3 className="text-white font-semibold truncate">{w.name}</h3>
                        </div>
                        <div className="flex items-center gap-2 text-[10px] text-muted">
                          <span>{w.agent_count} agents</span>
                          <span>·</span>
                          <span>{w.workflow_name}</span>
                          {w.has_kanban && <span className="text-success">· 已绑看板</span>}
                        </div>
                      </div>
                      <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        <button onClick={() => exportWorkspace(w.name)} className="p-1.5 rounded-lg text-muted hover:text-info transition-colors" title="导出">
                          <Download className="w-3 h-3" />
                        </button>
                        <button onClick={() => removeWorkspace(w.name)} className="p-1.5 rounded-lg text-muted/30 hover:text-warning transition-colors" title="卸载">
                          <XCircle className="w-3 h-3" />
                        </button>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
            {/* Import dialog */}
            {importFile && (
              <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setImportFile(null)}>
                <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
                  <h2 className="text-lg font-bold text-white">导入模块</h2>
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-muted">模块文件</label>
                    <p className="text-sm text-white mt-1">{importFile.name}</p>
                  </div>
                  <div>
                    <label className="text-[10px] uppercase tracking-widest text-muted">工作区名称</label>
                    <input value={importName} onChange={e => setImportName(e.target.value)}
                      placeholder="自定义名称，或使用默认名称"
                      className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
                    <p className="text-[10px] text-muted mt-1">修改不会影响模块原本的名称</p>
                  </div>
                  <div className="flex justify-end gap-2">
                    <button onClick={() => setImportFile(null)}
                      className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">取消</button>
                    <button onClick={confirmImport} disabled={importing || !importName.trim()}
                      className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30">
                      {importing ? <Loader2 className="w-4 h-4 animate-spin" /> : null} 确认导入
                    </button>
                  </div>
                </div>
              </div>
            )}
          </div>
        </div>

      ) : (
        <div className="flex-1 flex gap-4 overflow-hidden">
          {/* Chat */}
          <div className="flex-1 flex flex-col bg-card border border-border rounded-[20px] overflow-hidden">
            <div className="shrink-0 p-4 border-b border-border flex items-center justify-between">
              <div className="flex items-center gap-2">
                <Factory className="w-5 h-5 text-accent" />
                <h2 className="text-lg font-bold text-white">模块工厂</h2>
              </div>
              <button onClick={startProduction} disabled={wfRunning}
                className="flex items-center gap-1.5 px-3 py-1.5 bg-success/10 text-success border border-success/20 rounded-xl text-sm font-medium hover:bg-success/20 transition-colors disabled:opacity-30">
                {wfRunning ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
                开始生产
              </button>
            </div>
            <div className="flex-1 overflow-auto p-4 space-y-4">
              {messages.map((msg, i) => (
                <div key={i} className={`flex gap-3 ${msg.role === "user" ? "justify-end" : ""}`}>
                  {msg.role === "agent" && <div className="w-7 h-7 rounded-lg bg-accent/20 flex items-center justify-center shrink-0 mt-0.5"><Bot className="w-3.5 h-3.5 text-accent" /></div>}
                  <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed ${msg.role === "user" ? "bg-accent/15 border border-accent/20 text-white" : "bg-surface border border-border text-slate-300"}`}>
                    {msg.content.split("\n").map((l, j) => <p key={j} className="min-h-[1.4em]">{l || " "}</p>)}
                  </div>
                  {msg.role === "user" && <div className="w-7 h-7 rounded-lg bg-surface border border-border flex items-center justify-center shrink-0 mt-0.5"><User className="w-3.5 h-3.5 text-muted" /></div>}
                </div>
              ))}
              {chatLoading && <div className="flex gap-3"><div className="w-7 h-7 rounded-lg bg-accent/20 flex items-center justify-center"><Loader2 className="w-3.5 h-3.5 text-accent animate-spin" /></div><div className="bg-surface border border-border rounded-2xl px-4 py-3"><span className="text-sm text-muted animate-pulse">思考中...</span></div></div>}
              <div ref={chatEndRef} />
            </div>
            <div className="shrink-0 p-4 border-t border-border flex gap-3">
              <input value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === "Enter" && !chatLoading && sendChat()} placeholder="描述你想创建的 AI 模块..." disabled={chatLoading}
                className="flex-1 bg-surface border border-border rounded-xl px-4 py-3 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 disabled:opacity-50" />
              <button onClick={sendChat} disabled={chatLoading || !input.trim()}
                className="px-4 py-3 bg-accent text-black rounded-xl font-semibold text-sm hover:bg-amber-400 transition-colors disabled:opacity-30">发送</button>
            </div>
          </div>

          {/* Production status */}
          <div className="w-80 shrink-0 bg-card border border-border rounded-[20px] p-5 space-y-3 overflow-auto">
            <h3 className="text-sm font-semibold text-white flex items-center gap-2"><Zap className="w-4 h-4 text-warning" /> 生产线</h3>
            {Object.keys(nodeStatus).length === 0 && !wfResult && !wfRunning && (
              <p className="text-xs text-muted">先跟需求分析师对话，确认模块规格后点击「开始生产」。</p>
            )}
            {Object.entries(nodeLabels).map(([id, label]) => {
              const s = nodeStatus[id]; const status = s?.status;
              return (
                <div key={id} className={`p-2.5 rounded-xl border text-xs ${status === "running" ? "border-info/30 bg-info/5" : status === "passed" ? "border-success/30 bg-success/5" : status === "failed" ? "border-warning/30 bg-warning/5" : "border-border/50"}`}>
                  <div className="flex items-center justify-between">
                    <span className="text-white font-medium">{label}</span>
                    {status === "running" ? <Loader className="w-3 h-3 text-info animate-spin" /> : status === "passed" ? <CheckCircle2 className="w-3 h-3 text-success" /> : status === "failed" ? <XCircle className="w-3 h-3 text-warning" /> : <div className="w-1.5 h-1.5 rounded-full bg-muted/30" />}
                  </div>
                </div>
              );
            })}
            {wfResult && (
              <div className="p-4 bg-surface border border-border rounded-xl">
                <p className="text-sm text-white font-medium mb-2">{wfResult.status === "passed" ? "生产完成" : "生产失败"}</p>
                <button onClick={() => { loadWorkshops(); setTab("store"); }}
                  className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors">
                  <Store className="w-4 h-4" /> 去模块仓库查看
                </button>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

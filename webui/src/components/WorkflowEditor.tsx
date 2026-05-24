import { useState, useEffect, useCallback, useRef } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, Panel, addEdge,
  useNodesState, useEdgesState, type Node, type Edge,
  BackgroundVariant, MarkerType, Handle, Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, Play, Plus, Trash2, Loader2, ArrowLeft, X, CheckCircle2, XCircle, Circle, Loader, Bot, Blocks } from "lucide-react";
import { api, getAuthHeaders } from "../lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "./Toast";
import type { WorkflowTemplate } from "../lib/types";

// ── Custom Agent Node ──────────────────────────────────────────

function AgentNode({ data, selected }: { data: { label: string; agent_name: string; status?: string }; selected: boolean }) {
  const running = data.status === "running";
  const passed = data.status === "passed";
  const failed = data.status === "failed";
  return (
    <div className={`px-4 py-3 rounded-lg border-2 min-w-[180px] transition-all ${
      running ? "border-primary/50 bg-primary/5" :
      passed ? "border-success/50 bg-success/5" :
      failed ? "border-destructive/50 bg-destructive/5" :
      selected ? "border-primary bg-background shadow-lg shadow-primary/10" : "border-border bg-card"
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-muted-foreground" />
      <div className="flex items-center gap-2">
        {running && <Loader className="w-3 h-3 text-primary animate-spin" />}
        {passed && <CheckCircle2 className="w-3 h-3 text-success" />}
        {failed && <XCircle className="w-3 h-3 text-destructive" />}
        {!running && !passed && !failed && <Circle className="w-2 h-2 text-muted-foreground" />}
        <div className="text-xs font-semibold">{data.label || "未命名"}</div>
      </div>
      <div className="text-[10px] text-muted-foreground mt-0.5">{data.agent_name || "无 Agent"}</div>
      <Handle type="source" position={Position.Right} className="!bg-primary" />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

// ── Helpers ────────────────────────────────────────────────────

function makeId(): string { return "node-" + Math.random().toString(36).slice(2, 8); }

function templateToFlow(tmpl: WorkflowTemplate): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (tmpl.nodes || []).map((n, i) => ({
    id: n.id, type: "agent",
    position: { x: 100 + i * 280, y: 200 },
    data: { label: n.label, agent_name: n.agent_name },
  }));
  const edges: Edge[] = [];
  for (const n of tmpl.nodes || []) {
    for (const dep of n.depends_on || []) {
      edges.push({ id: `${dep}-${n.id}`, source: dep, target: n.id, markerEnd: { type: MarkerType.ArrowClosed }, animated: true });
    }
  }
  return { nodes, edges };
}

// ── Editor ──────────────────────────────────────────────────────

interface Props { templateName: string | null; onBack: () => void; }

export function WorkflowEditor({ templateName, onBack }: Props) {
  const toast = useToast();
  const [name, setName] = useState(templateName || "");
  const [description, setDescription] = useState("");
  const [workspace, setWorkspace] = useState("");
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [saving, setSaving] = useState(false);
  const [selectedNode, setSelectedNode] = useState<Node | null>(null);
  const [nodeProps, setNodeProps] = useState({ label: "", agent_name: "", prompt: "" });
  const [workshops, setWorkshops] = useState<{ name: string; agents?: Record<string, any> }[]>([]);
  const [sidebarWs, setSidebarWs] = useState("");
  const [wsAgents, setWsAgents] = useState<{ name: string; type: string; model: string }[]>([]);
  const [sidebarOpen, setSidebarOpen] = useState(true);

  const [running, setRunning] = useState(false);
  const [runStatus, setRunStatus] = useState<Record<string, { status: string; detail: string }>>({});
  const [showRunDialog, setShowRunDialog] = useState(false);
  const [task, setTask] = useState("");
  const [runWorkspace, setRunWorkspace] = useState(workspace);
  const [runResult, setRunResult] = useState<{
    status: string; final_output: string;
    node_results: Record<string, { node_id: string; agent_name: string; status: string; output: string; error: string }>;
  } | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    if (templateName) {
      api.getWorkflow(templateName).then((tmpl) => {
        setName(tmpl.name); setDescription(tmpl.description || ""); setWorkspace(tmpl.workspace || ""); setSidebarWs(tmpl.workspace || "");
        const flow = templateToFlow(tmpl); setNodes(flow.nodes); setEdges(flow.edges);
      }).catch(() => toast.error("加载工作流失败"));
    }
  }, [templateName]);

  useEffect(() => {
    api.listWorkshops().then((data: any[]) => {
      setWorkshops(data.map((w) => ({ name: w.name, agents: w.agents })));
    }).catch(() => {});
  }, []);

  useEffect(() => {
    if (!sidebarWs) { setWsAgents([]); return; }
    const ws = workshops.find((w) => w.name === sidebarWs);
    if (ws?.agents) {
      setWsAgents(Object.entries(ws.agents).map(([name, cfg]: [string, any]) => ({
        name, type: cfg.type || "super", model: cfg.model || "",
      })));
    } else { setWsAgents([]); }
  }, [sidebarWs, workshops]);

  useEffect(() => {
    if (selectedNode) {
      setNodeProps({ label: String(selectedNode.data.label || ""), agent_name: String(selectedNode.data.agent_name || ""), prompt: String(selectedNode.data.prompt || "") });
    }
  }, [selectedNode]);

  useEffect(() => {
    const statusKeys = Object.keys(runStatus);
    if (statusKeys.length === 0) return;
    setNodes((nds) => nds.map((n) => ({ ...n, data: { ...n.data, status: runStatus[n.id]?.status } })));
  }, [runStatus, setNodes]);

  const onConnect = useCallback((conn: { source: string; target: string }) => {
    setEdges((eds) => addEdge({ id: `e-${conn.source}-${conn.target}`, ...conn, markerEnd: { type: MarkerType.ArrowClosed }, animated: true }, eds));
  }, []);

  const addNode = (agentName = "", agentLabel = "") => {
    const id = makeId();
    setNodes((nds) => [...nds, { id, type: "agent", position: { x: 200 + Math.random() * 300, y: 100 + Math.random() * 200 }, data: { label: agentLabel || "新节点", agent_name: agentName, prompt: "" } }]);
  };

  const addAgentNode = (agent: { name: string }) => {
    const id = makeId();
    const newNode: Node = { id, type: "agent", position: { x: 200 + Math.random() * 300, y: 100 + Math.random() * 200 }, data: { label: agent.name, agent_name: agent.name, prompt: "" } };
    setNodes((nds) => [...nds, newNode]); setSelectedNode(newNode);
  };

  const deleteNode = (id: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== id));
    setEdges((eds) => eds.filter((e) => e.source !== id && e.target !== id));
    if (selectedNode?.id === id) setSelectedNode(null);
  };

  const applyNodeProps = () => {
    if (!selectedNode) return;
    setNodes((nds) => nds.map((n) => n.id === selectedNode.id ? { ...n, data: { ...n.data, ...nodeProps } } : n));
    setSelectedNode((prev) => prev ? { ...prev, data: { ...prev.data, ...nodeProps } } : null);
  };

  const onNodeClick = (_: unknown, node: Node) => { applyNodeProps(); setSelectedNode(node); };
  const onPaneClick = () => { applyNodeProps(); setSelectedNode(null); };

  const buildTemplate = (): WorkflowTemplate => ({
    name, description, workspace: sidebarWs || workspace,
    nodes: nodes.map((n) => ({
      id: n.id, label: String(n.data.label || ""), agent_name: String(n.data.agent_name || ""),
      prompt: String(n.data.prompt || ""), depends_on: edges.filter((e) => e.target === n.id).map((e) => e.source), expected_output: "",
    })),
  });

  const save = async () => {
    if (!name.trim()) { toast.error("请输入工作流名称"); return; }
    applyNodeProps(); setSaving(true);
    try { await api.saveWorkflow(buildTemplate()); toast.success("已保存"); } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally { setSaving(false); }
  };

  const execute = async () => {
    if (!name.trim() || !task.trim()) return;
    applyNodeProps(); setSaving(true);
    try { await api.saveWorkflow(buildTemplate()); } catch { toast.error("请先保存工作流"); setSaving(false); return; }
    setSaving(false);
    setRunning(true); setRunStatus({}); setRunResult(null); setShowRunDialog(false);
    const controller = new AbortController(); abortRef.current = controller;
    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(name)}/execute`, {
        method: "POST", headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        credentials: "include", body: JSON.stringify({ task: task.trim(), workshop: runWorkspace || sidebarWs || workspace }), signal: controller.signal,
      });
      if (!res.ok) { const err = await res.json(); throw new Error(err.detail || "执行失败"); }
      const reader = res.body?.getReader(); if (!reader) throw new Error("No response stream");
      const decoder = new TextDecoder(); let buffer = "";
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n"); buffer = lines.pop() || "";
        let eventName = "";
        for (const line of lines) {
          if (line.startsWith("event: ")) { eventName = line.slice(7).trim(); }
          else if (line.startsWith("data: ") && eventName) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventName === "node_status") setRunStatus((prev) => ({ ...prev, [data.node_id]: { status: data.status, detail: data.detail } }));
              else if (eventName === "completed") setRunResult(data);
              else if (eventName === "error") toast.error(data.message || "执行出错");
            } catch {}
          }
        }
      }
    } catch (err) { if ((err as Error).name !== "AbortError") toast.error(err instanceof Error ? err.message : "执行失败"); }
    finally { setRunning(false); abortRef.current = null; }
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 rounded-lg bg-card border border-border text-muted-foreground hover:text-foreground hover:border-ring/30 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <input value={name} onChange={(e) => setName(e.target.value)}
              placeholder="工作流名称"
              className="text-xl font-semibold tracking-tight bg-transparent placeholder:text-muted-foreground focus:outline-none border-b border-transparent focus:border-ring/30 w-64" />
            <input value={description} onChange={(e) => setDescription(e.target.value)}
              placeholder="描述（可选）"
              className="block text-xs text-muted-foreground bg-transparent placeholder:text-muted-foreground/50 focus:outline-none mt-1 w-80" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSidebarOpen(!sidebarOpen)}
            className="flex items-center gap-1.5 px-3 py-2 bg-background border border-border rounded-lg text-sm text-muted-foreground hover:text-foreground hover:border-ring/30 transition-colors">
            <Blocks className="w-4 h-4" /> {sidebarOpen ? "收起" : "面板"}
          </button>
          {running ? (
            <button onClick={() => { abortRef.current?.abort(); setRunning(false); }}
              className="flex items-center gap-1.5 px-4 py-2 bg-destructive/10 text-destructive border border-destructive/20 rounded-lg text-sm font-medium hover:bg-destructive/20 transition-colors">
              <XCircle className="w-4 h-4" /> 取消
            </button>
          ) : (
            <>
              <button onClick={() => addNode()}
                className="flex items-center gap-1.5 px-3 py-2 bg-background border border-border rounded-lg text-sm text-muted-foreground hover:text-foreground hover:border-ring/30 transition-colors">
                <Plus className="w-4 h-4" /> 添加节点
              </button>
              <button onClick={() => { applyNodeProps(); setShowRunDialog(true); }}
                className="flex items-center gap-1.5 px-4 py-2 bg-success/10 text-success border border-success/20 rounded-lg text-sm font-medium hover:bg-success/20 transition-colors">
                <Play className="w-4 h-4" /> 执行
              </button>
              <Button onClick={save} disabled={saving} variant="outline" size="sm">
                {saving ? <Loader2 className="w-4 h-4 animate-spin mr-2" /> : <Save className="w-4 h-4 mr-2" />} 保存
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Canvas + Sidebar */}
      <div className="flex gap-4" style={{ height: "calc(100vh - 180px)" }}>
        {sidebarOpen && (
          <div className="w-56 shrink-0 bg-card border border-border rounded-xl flex flex-col">
            <div className="p-3 border-b border-border space-y-2">
              <span className="text-[10px] uppercase tracking-wider text-muted-foreground">关联项目</span>
              <select value={sidebarWs} onChange={(e) => setSidebarWs(e.target.value)}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-ring/50">
                <option value="">选择项目...</option>
                {workshops.map((w) => <option key={w.name} value={w.name}>{w.name}</option>)}
              </select>
            </div>
            <div className="flex-1 overflow-auto p-2">
              <div className="text-[10px] uppercase tracking-wider text-muted-foreground/50 px-2 pb-2">
                可用 Agent {wsAgents.length > 0 && `(${wsAgents.length})`}
              </div>
              {sidebarWs && wsAgents.length === 0 && <p className="text-xs text-muted-foreground/30 px-2 py-4">该项目暂无 Agent</p>}
              {!sidebarWs && <p className="text-xs text-muted-foreground/30 px-2 py-4">选择项目查看 Agent</p>}
              <div className="space-y-1">
                {wsAgents.map((a) => (
                  <button key={a.name} onClick={() => addAgentNode(a)}
                    className="w-full flex items-center gap-2 px-3 py-2 rounded-md text-left text-sm text-foreground/80 hover:text-foreground hover:bg-accent hover:border-ring/30 border border-transparent transition-all group">
                    <Bot className="w-3.5 h-3.5 text-muted-foreground group-hover:text-primary shrink-0" />
                    <div className="min-w-0">
                      <div className="text-xs truncate">{a.name}</div>
                      <div className="text-[9px] text-muted-foreground/50">{a.type} · {a.model || "默认"}</div>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* Flow Canvas */}
        <div className="flex-1 bg-card border border-border rounded-xl overflow-hidden">
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect} onNodeClick={onNodeClick} onPaneClick={onPaneClick}
            nodeTypes={nodeTypes} fitView
            deleteKeyCode={["Backspace", "Delete"]} multiSelectionKeyCode="Shift"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--border)" />
            <Controls className="!bg-card !border-border !rounded-lg" />
            <MiniMap className="!bg-card !border-border !rounded-lg" nodeColor="var(--primary)" />
            <Panel position="bottom-center" className="!bg-transparent">
              <span className="text-[10px] text-muted-foreground">{nodes.length} 节点 · {edges.length} 连线</span>
            </Panel>
          </ReactFlow>
        </div>

        {/* Properties Panel */}
        {selectedNode && (
          <div className="w-72 shrink-0 bg-card border border-border rounded-xl p-5 space-y-4 overflow-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">节点属性</h3>
              <button onClick={() => deleteNode(selectedNode.id)}
                className="p-1.5 rounded-md text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">Agent 名称</label>
              <Input value={nodeProps.agent_name} onChange={(e) => setNodeProps((p) => ({ ...p, agent_name: e.target.value }))}
                onBlur={applyNodeProps} placeholder="Agent 名称" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">显示标签</label>
              <Input value={nodeProps.label} onChange={(e) => setNodeProps((p) => ({ ...p, label: e.target.value }))}
                onBlur={applyNodeProps} placeholder="节点显示名" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5 block">任务 Prompt</label>
              <textarea value={nodeProps.prompt} onChange={(e) => setNodeProps((p) => ({ ...p, prompt: e.target.value }))}
                onBlur={applyNodeProps} placeholder="该节点 Agent 要执行的任务..." rows={4}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:border-ring/50 resize-none" />
            </div>
          </div>
        )}

        {/* Run Status */}
        {(running || runResult) && (
          <div className="w-80 shrink-0 bg-card border border-border rounded-xl p-5 space-y-4 overflow-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold">{running ? "执行中..." : runResult?.status === "passed" ? "执行完成" : "执行结果"}</h3>
              {running && <span className="text-[10px] text-primary animate-pulse">运行中</span>}
            </div>
            <div className="space-y-2">
              {nodes.map((n) => {
                const s = runStatus[n.id];
                const r = runResult?.node_results?.[n.id];
                const status = r?.status || s?.status;
                return (
                  <div key={n.id} className={`p-3 rounded-lg border text-xs transition-all ${
                    status === "running" ? "border-primary/30 bg-primary/5" :
                    status === "passed" ? "border-success/30 bg-success/5" :
                    status === "failed" ? "border-destructive/30 bg-destructive/5" :
                    "border-border bg-background"
                  }`}>
                    <div className="flex items-center justify-between">
                      <span className="font-medium">{String(n.data.label || n.id)}</span>
                      <span className={`text-[10px] ${
                        status === "running" ? "text-primary" :
                        status === "passed" ? "text-success" :
                        status === "failed" ? "text-destructive" : "text-muted-foreground"
                      }`}>
                        {status === "running" ? "运行中" : status === "passed" ? "通过" : status === "failed" ? "失败" : r ? r.status : "等待"}
                      </span>
                    </div>
                    {r?.output && <p className="text-muted-foreground mt-1 line-clamp-2">{r.output}</p>}
                    {r?.error && <p className="text-destructive mt-1 line-clamp-2">{r.error}</p>}
                  </div>
                );
              })}
            </div>
            {runResult?.final_output && (
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">最终产出</label>
                <div className="mt-1 p-3 bg-background border border-border rounded-lg">
                  <p className="text-xs whitespace-pre-wrap line-clamp-6">{runResult.final_output}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Execute Dialog */}
      <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>执行工作流</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">项目</label>
              <select value={runWorkspace} onChange={(e) => setRunWorkspace(e.target.value)}
                className="w-full h-9 bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-ring/50">
                <option value="">{sidebarWs || "选择项目..."}</option>
                {workshops.map((w) => <option key={w.name} value={w.name}>{w.name}</option>)}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">任务描述</label>
              <textarea value={task} onChange={(e) => setTask(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && e.metaKey) execute(); }}
                placeholder="描述要执行的任务..." rows={5}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:border-ring/50 resize-none" />
              <p className="text-[10px] text-muted-foreground mt-1">Cmd+Enter 快速执行</p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRunDialog(false)}>取消</Button>
            <Button onClick={execute} disabled={!task.trim() || !name.trim()} className="gap-1.5">
              <Play className="w-4 h-4" /> 开始执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

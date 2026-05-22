import { useState, useEffect, useCallback, useRef } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, Panel, addEdge,
  useNodesState, useEdgesState, type Node, type Edge,
  BackgroundVariant, MarkerType, Handle, Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, Play, Plus, Trash2, Loader2, ArrowLeft, X, CheckCircle2, XCircle, Circle, Loader } from "lucide-react";
import { api } from "../lib/api";
import { useToast } from "./Toast";
import type { WorkflowTemplate } from "../lib/types";

// ── Custom Agent Node ──────────────────────────────────────

function AgentNode({ data, selected }: { data: { label: string; agent_name: string; status?: string }; selected: boolean }) {
  const running = data.status === "running";
  const passed = data.status === "passed";
  const failed = data.status === "failed";

  return (
    <div className={`px-4 py-3 rounded-xl border-2 min-w-[180px] transition-all ${
      running ? "border-info/50 bg-info/5" :
      passed ? "border-success/50 bg-success/5" :
      failed ? "border-warning/50 bg-warning/5" :
      selected ? "border-accent bg-surface shadow-lg shadow-accent/10" : "border-border bg-card"
    }`}>
      <Handle type="target" position={Position.Left} className="!bg-muted" />
      <div className="flex items-center gap-2">
        {running && <Loader className="w-3 h-3 text-info animate-spin" />}
        {passed && <CheckCircle2 className="w-3 h-3 text-success" />}
        {failed && <XCircle className="w-3 h-3 text-warning" />}
        {!running && !passed && !failed && <Circle className="w-2 h-2 text-muted" />}
        <div className="text-xs font-semibold text-white">{data.label || "未命名"}</div>
      </div>
      <div className="text-[10px] text-muted mt-0.5">{data.agent_name || "无 Agent"}</div>
      <Handle type="source" position={Position.Right} className="!bg-accent" />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

// ── Helpers ────────────────────────────────────────────────

function makeId(): string {
  return "node-" + Math.random().toString(36).slice(2, 8);
}

function templateToFlow(tmpl: WorkflowTemplate): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (tmpl.nodes || []).map((n, i) => ({
    id: n.id,
    type: "agent",
    position: { x: 100 + i * 280, y: 200 },
    data: { label: n.label, agent_name: n.agent_name },
  }));
  const edges: Edge[] = [];
  for (const n of tmpl.nodes || []) {
    for (const dep of n.depends_on || []) {
      edges.push({
        id: `${dep}-${n.id}`,
        source: dep, target: n.id,
        markerEnd: { type: MarkerType.ArrowClosed },
        animated: true,
      });
    }
  }
  return { nodes, edges };
}

// ── Editor ───────────────────────────────────────────────────

interface Props {
  templateName: string | null;
  onBack: () => void;
}

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
  const [workshops, setWorkshops] = useState<{ name: string }[]>([]);

  // Execution state
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

  // Load template if editing
  useEffect(() => {
    if (templateName) {
      api.getWorkflow(templateName).then(tmpl => {
        setName(tmpl.name);
        setDescription(tmpl.description || "");
        setWorkspace(tmpl.workspace || "");
        const flow = templateToFlow(tmpl);
        setNodes(flow.nodes);
        setEdges(flow.edges);
      }).catch(() => toast.error("加载工作流失败"));
    }
  }, [templateName]);

  // Sync selected node → properties panel
  useEffect(() => {
    if (selectedNode) {
      setNodeProps({
        label: String(selectedNode.data.label || ""),
        agent_name: String(selectedNode.data.agent_name || ""),
        prompt: String(selectedNode.data.prompt || ""),
      });
    }
  }, [selectedNode]);

  // Load workshops for execute dialog
  useEffect(() => {
    api.listWorkshops().then(data => {
      setWorkshops(data.map((w: { name: string }) => ({ name: w.name })));
    }).catch((err) => { console.warn("加载车间列表失败", err); });
  }, []);

  // Sync runStatus to node data for canvas indicators
  useEffect(() => {
    const statusKeys = Object.keys(runStatus);
    if (statusKeys.length === 0) return;
    setNodes(nds => nds.map(n => ({
      ...n,
      data: { ...n.data, status: runStatus[n.id]?.status },
    })));
  }, [runStatus, setNodes]);

  const onConnect = useCallback((conn: { source: string; target: string }) => {
    setEdges(eds => addEdge({ id: `e-${conn.source}-${conn.target}`, ...conn, markerEnd: { type: MarkerType.ArrowClosed }, animated: true }, eds));
  }, []);

  const addNode = () => {
    const id = makeId();
    const newNode: Node = {
      id, type: "agent",
      position: { x: 200 + Math.random() * 300, y: 100 + Math.random() * 200 },
      data: { label: "新节点", agent_name: "", prompt: "" },
    };
    setNodes(nds => [...nds, newNode]);
    setSelectedNode(newNode);
  };

  const deleteNode = (id: string) => {
    setNodes(nds => nds.filter(n => n.id !== id));
    setEdges(eds => eds.filter(e => e.source !== id && e.target !== id));
    if (selectedNode?.id === id) setSelectedNode(null);
  };

  const applyNodeProps = () => {
    if (!selectedNode) return;
    setNodes(nds => nds.map(n => n.id === selectedNode.id ? { ...n, data: { ...n.data, ...nodeProps } } : n));
    setSelectedNode(prev => prev ? { ...prev, data: { ...prev.data, ...nodeProps } } : null);
  };

  const onNodeClick = (_: unknown, node: Node) => {
    applyNodeProps(); // save previous selection
    setSelectedNode(node);
  };

  const onPaneClick = () => {
    applyNodeProps();
    setSelectedNode(null);
  };

  const buildTemplate = (): WorkflowTemplate => ({
    name, description, workspace,
    nodes: nodes.map(n => ({
      id: n.id,
      label: String(n.data.label || ""),
      agent_name: String(n.data.agent_name || ""),
      prompt: String(n.data.prompt || ""),
      depends_on: edges.filter(e => e.target === n.id).map(e => e.source),
      expected_output: "",
    })),
  });

  const save = async () => {
    if (!name.trim()) { toast.error("请输入工作流名称"); return; }
    applyNodeProps();
    setSaving(true);
    try {
      await api.saveWorkflow(buildTemplate());
      toast.success(`工作流 "${name}" 已保存`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally { setSaving(false); }
  };

  const execute = async () => {
    if (!name.trim() || !task.trim()) return;
    applyNodeProps();

    // Save first
    setSaving(true);
    try {
      await api.saveWorkflow(buildTemplate());
    } catch (err) {
      toast.error("请先保存工作流");
      setSaving(false);
      return;
    }
    setSaving(false);

    setRunning(true);
    setRunStatus({});
    setRunResult(null);
    setShowRunDialog(false);

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      const res = await fetch(`/api/workflows/${encodeURIComponent(name)}/execute`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ task: task.trim(), workshop: runWorkspace || workspace }),
        signal: controller.signal,
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "执行失败");
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error("No response stream");

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
          if (line.startsWith("event: ")) {
            eventName = line.slice(7).trim();
          } else if (line.startsWith("data: ") && eventName) {
            try {
              const data = JSON.parse(line.slice(6));
              if (eventName === "node_status") {
                setRunStatus(prev => ({ ...prev, [data.node_id]: { status: data.status, detail: data.detail } }));
              } else if (eventName === "completed") {
                setRunResult(data);
              } else if (eventName === "error") {
                toast.error(data.message || "执行出错");
              }
            } catch { /* skip malformed JSON */ }
          }
        }
      }
    } catch (err) {
      if ((err as Error).name !== "AbortError") {
        toast.error(err instanceof Error ? err.message : "执行失败");
      }
    } finally {
      setRunning(false);
      abortRef.current = null;
    }
  };

  const cancelRun = () => {
    abortRef.current?.abort();
    setRunning(false);
  };

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <button onClick={onBack} className="p-2 rounded-xl bg-card border border-border text-muted hover:text-white hover:border-accent/20 transition-colors">
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <input value={name} onChange={e => setName(e.target.value)}
              placeholder="工作流名称"
              className="text-xl font-black tracking-tight text-white bg-transparent placeholder:text-muted focus:outline-none border-b border-transparent focus:border-accent/30 w-64" />
            <input value={description} onChange={e => setDescription(e.target.value)}
              placeholder="描述（可选）"
              className="block text-xs text-muted bg-transparent placeholder:text-muted/50 focus:outline-none mt-1 w-80" />
          </div>
        </div>
        <div className="flex items-center gap-2">
          {running ? (
            <button onClick={cancelRun}
              className="flex items-center gap-1.5 px-4 py-2 bg-warning/10 text-warning border border-warning/20 rounded-xl text-sm font-medium hover:bg-warning/20 transition-colors">
              <XCircle className="w-4 h-4" /> 取消执行
            </button>
          ) : (
            <>
              <button onClick={addNode}
                className="flex items-center gap-1.5 px-3 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white hover:border-accent/20 transition-colors">
                <Plus className="w-4 h-4" /> 添加节点
              </button>
              <button onClick={() => { applyNodeProps(); setShowRunDialog(true); }}
                className="flex items-center gap-1.5 px-4 py-2 bg-success/10 text-success border border-success/20 rounded-xl text-sm font-medium hover:bg-success/20 transition-colors">
                <Play className="w-4 h-4" /> 执行
              </button>
              <button onClick={save} disabled={saving}
                className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30">
                {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Save className="w-4 h-4" />}
                保存
              </button>
            </>
          )}
        </div>
      </div>

      {/* Canvas + Sidebar */}
      <div className="flex gap-4" style={{ height: "calc(100vh - 180px)" }}>
        {/* Flow Canvas */}
        <div className="flex-1 bg-card border border-border rounded-[20px] overflow-hidden">
          <ReactFlow
            nodes={nodes} edges={edges}
            onNodesChange={onNodesChange} onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={onNodeClick}
            onPaneClick={onPaneClick}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode="Shift"
          >
            <Background variant={BackgroundVariant.Dots} gap={20} size={1} color="var(--color-border)" />
            <Controls className="!bg-card !border-border !rounded-xl" />
            <MiniMap className="!bg-card !border-border !rounded-xl" nodeColor="var(--color-accent)" />
            <Panel position="bottom-center" className="!bg-transparent">
              <span className="text-[10px] text-muted">{nodes.length} 节点 · {edges.length} 连线 · 拖拽连线设置依赖</span>
            </Panel>
          </ReactFlow>
        </div>

        {/* Properties Panel */}
        {selectedNode && (
          <div className="w-72 shrink-0 bg-card border border-border rounded-[20px] p-5 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">节点属性</h3>
              <button onClick={() => deleteNode(selectedNode.id)}
                className="p-1.5 rounded-lg text-muted hover:text-warning hover:bg-warning/10 transition-colors">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">节点 ID</label>
              <p className="text-xs text-white font-mono mt-1 bg-surface rounded-lg px-3 py-1.5">{selectedNode.id}</p>
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">名称</label>
              <input value={nodeProps.label} onChange={e => setNodeProps(p => ({ ...p, label: e.target.value }))}
                onBlur={applyNodeProps}
                placeholder="节点显示名"
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">Agent</label>
              <input value={nodeProps.agent_name} onChange={e => setNodeProps(p => ({ ...p, agent_name: e.target.value }))}
                onBlur={applyNodeProps}
                placeholder="Agent 名称"
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1" />
            </div>
            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">任务 Prompt</label>
              <textarea value={nodeProps.prompt} onChange={e => setNodeProps(p => ({ ...p, prompt: e.target.value }))}
                onBlur={applyNodeProps}
                placeholder="该节点 Agent 要执行的任务..."
                rows={4}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1 resize-none" />
            </div>
            <div className="text-[10px] text-muted pt-2 border-t border-border">
              连线到此节点的上游节点将作为依赖 (depends_on)
            </div>
          </div>
        )}

        {/* Run Status Panel — shown during/after execution */}
        {(running || runResult) && (
          <div className="w-80 shrink-0 bg-card border border-border rounded-[20px] p-5 space-y-4 overflow-auto">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-semibold text-white">
                {running ? "执行中..." : runResult?.status === "passed" ? "执行完成" : "执行结果"}
              </h3>
              {running && (
                <span className="text-[10px] text-info animate-pulse">运行中</span>
              )}
            </div>

            {/* Per-node status */}
            <div className="space-y-2">
              {nodes.map(n => {
                const s = runStatus[n.id];
                const r = runResult?.node_results?.[n.id];
                const status = r?.status || s?.status;
                return (
                  <div key={n.id} className={`p-3 rounded-xl border text-xs transition-all ${
                    status === "running" ? "border-info/30 bg-info/5" :
                    status === "passed" ? "border-success/30 bg-success/5" :
                    status === "failed" ? "border-warning/30 bg-warning/5" :
                    "border-border bg-surface"
                  }`}>
                    <div className="flex items-center justify-between">
                      <span className="text-white font-medium">{String(n.data.label || n.id)}</span>
                      <span className={`text-[10px] ${
                        status === "running" ? "text-info" :
                        status === "passed" ? "text-success" :
                        status === "failed" ? "text-warning" : "text-muted"
                      }`}>
                        {status === "running" ? "运行中" :
                         status === "passed" ? "通过" :
                         status === "failed" ? "失败" : r ? r.status : "等待"}
                      </span>
                    </div>
                    {r?.output && (
                      <p className="text-muted mt-1 line-clamp-2">{r.output}</p>
                    )}
                    {r?.error && (
                      <p className="text-warning mt-1 line-clamp-2">{r.error}</p>
                    )}
                  </div>
                );
              })}
            </div>

            {/* Final output */}
            {runResult?.final_output && (
              <div>
                <label className="text-[10px] uppercase tracking-widest text-muted">最终产出</label>
                <div className="mt-1 p-3 bg-surface border border-border rounded-xl">
                  <p className="text-xs text-white whitespace-pre-wrap line-clamp-6">{runResult.final_output}</p>
                </div>
              </div>
            )}
          </div>
        )}
      </div>

      {/* ── Execute Dialog ── */}
      {showRunDialog && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowRunDialog(false)}>
          <div className="bg-card border border-border rounded-[20px] p-6 w-full max-w-md space-y-4 shadow-2xl" onClick={e => e.stopPropagation()}>
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-bold text-white">执行工作流</h2>
              <button onClick={() => setShowRunDialog(false)} className="p-1.5 rounded-lg text-muted hover:text-white transition-colors">
                <X className="w-4 h-4" />
              </button>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">工作区</label>
              <select value={runWorkspace} onChange={e => setRunWorkspace(e.target.value)}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white focus:outline-none focus:border-accent/30 mt-1">
                <option value="">{workspace || "选择工作区..."}</option>
                {workshops.map(w => (
                  <option key={w.name} value={w.name}>{w.name}</option>
                ))}
              </select>
            </div>

            <div>
              <label className="text-[10px] uppercase tracking-widest text-muted">任务描述</label>
              <textarea value={task} onChange={e => setTask(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && e.metaKey) execute(); }}
                placeholder="描述要执行的任务，例如：分析市场数据并生成报告..."
                rows={5}
                className="w-full bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 mt-1 resize-none" />
              <p className="text-[10px] text-muted mt-1">Cmd+Enter 快速执行</p>
            </div>

            <div className="flex justify-end gap-2">
              <button onClick={() => setShowRunDialog(false)}
                className="px-4 py-2 bg-surface border border-border rounded-xl text-sm text-muted hover:text-white transition-colors">
                取消
              </button>
              <button onClick={execute} disabled={!task.trim() || !name.trim()}
                className="flex items-center gap-1.5 px-4 py-2 bg-success/10 text-success border border-success/20 rounded-xl text-sm font-medium hover:bg-success/20 transition-colors disabled:opacity-30">
                <Play className="w-4 h-4" /> 开始执行
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

import { useState, useEffect, useCallback } from "react";
import {
  ReactFlow, Background, Controls, MiniMap, Panel, addEdge,
  useNodesState, useEdgesState, type Node, type Edge, type Connection,
  BackgroundVariant, MarkerType, Handle, Position,
} from "@xyflow/react";
import "@xyflow/react/dist/style.css";
import { Save, Play, Loader2, ArrowLeft, XCircle, CheckCircle2, Bot } from "lucide-react";
import { api } from "../lib/api";
import { Button } from "@/components/ui/button";
import {
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter,
} from "@/components/ui/dialog";
import { useToast } from "./Toast";
import { NodePalette } from "./NodePalette";
import { NodeConfigPanel } from "./NodeConfigPanel";
import { NodeSearchDialog } from "./NodeSearchDialog";
import { useWorkflowExecution } from "../hooks/useWorkflowExecution";
import type { WorkflowTemplate } from "../lib/types";

// ── n8n-style flat card Agent Node ──────────────────────────

function AgentNode({ data, selected }: { data: Record<string, unknown>; selected: boolean }) {
  const label = String(data.label || "未命名");
  const agentName = String(data.agent_name || "");
  const nodeType = String(data.node_type || "agent");
  const status = String(data.status || "");
  const running = status === "running";
  const passed = status === "passed";
  const failed = status === "failed";

  const typeLabel =
    nodeType === "agent" ? "Agent" : nodeType === "condition" ? "IF" : "Code";

  return (
    <div
      className={`relative px-4 py-3 rounded-lg border min-w-[160px] transition-all ${
        running
          ? "border-primary/40 bg-card shadow-[0_0_12px_rgba(var(--primary)/0.15)]"
          : passed
          ? "border-emerald-500/30 bg-card"
          : failed
          ? "border-red-400/30 bg-card"
          : selected
          ? "border-primary/60 bg-card ring-1 ring-primary/20"
          : "border-border bg-card hover:border-ring/30"
      }`}
    >
      {/* Glow ring when running (n8n pulse) */}
      {running && (
        <div className="absolute inset-0 rounded-lg border-2 border-primary/50 animate-pulse pointer-events-none" />
      )}

      <Handle
        type="target"
        position={Position.Left}
        className="!w-2.5 !h-2.5 !bg-muted-foreground !border-2 !border-card !rounded-full"
      />

      {/* Type badge */}
      <div className="flex items-center gap-2 mb-1">
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-muted text-muted-foreground font-medium">
          {typeLabel}
        </span>
        {running && (
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
        )}
        {passed && <CheckCircle2 className="w-3 h-3 text-emerald-500" />}
        {failed && <XCircle className="w-3 h-3 text-red-400" />}
      </div>

      {/* Label */}
      <div className="text-xs font-semibold text-foreground">{label}</div>

      {/* Subtitle */}
      {agentName && (
        <div className="text-[10px] text-muted-foreground mt-0.5 flex items-center gap-1">
          <Bot className="w-2.5 h-2.5" />
          {agentName}
        </div>
      )}

      <Handle
        type="source"
        position={Position.Right}
        className="!w-2.5 !h-2.5 !bg-primary !border-2 !border-card !rounded-full"
      />
    </div>
  );
}

const nodeTypes = { agent: AgentNode };

// ── Helpers ──────────────────────────────────────────────────

function makeId(): string {
  return "node-" + Math.random().toString(36).slice(2, 8);
}

function templateToFlow(tmpl: WorkflowTemplate): { nodes: Node[]; edges: Edge[] } {
  const nodes: Node[] = (tmpl.nodes || []).map((n, i) => ({
    id: n.id,
    type: "agent",
    position: { x: 100 + i * 280, y: 200 },
    data: {
      label: n.label,
      agent_name: n.agent_name || "",
      node_type: n.node_type || "agent",
      prompt: n.prompt || "",
      timeout_seconds: n.timeout_seconds || 300,
      notes: n.notes || "",
      retry_on_fail: n.retry_on_fail || false,
      continue_on_fail: n.continue_on_fail || false,
    },
  }));
  const edges: Edge[] = [];
  for (const n of tmpl.nodes || []) {
    for (const dep of n.depends_on || []) {
      edges.push({
        id: `e-${dep}-${n.id}`,
        source: dep,
        target: n.id,
        markerEnd: { type: MarkerType.ArrowClosed },
        style: { stroke: "var(--border)", strokeWidth: 1.5 },
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

  // Workflow meta
  const [name, setName] = useState(templateName || "");
  const [description, setDescription] = useState("");
  const [workspace, setWorkspace] = useState("");

  // Canvas state
  const [nodes, setNodes, onNodesChange] = useNodesState<Node>([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState<Edge>([]);
  const [selectedNodeId, setSelectedNodeId] = useState<string | null>(null);

  // Workspace data
  const [workshops, setWorkshops] = useState<{ name: string; agents?: Record<string, unknown> }[]>([]);
  const [wsAgents, setWsAgents] = useState<{ name: string; type: string; model: string }[]>([]);

  // UI state
  const [saving, setSaving] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(true);
  const [searchOpen, setSearchOpen] = useState(false);

  // Execution — delegated to hook
  const {
    running, runStatus, setRunStatus, runResult,
    showRunDialog, setShowRunDialog, task, setTask,
    runWorkspace, setRunWorkspace, executingNode,
    execute, executeSingleNode, cancel,
  } = useWorkflowExecution({
    workflowName: name,
    workspace,
    saveTemplate: async () => {
      if (!name.trim()) { toast.error("请输入工作流名称"); return false; }
      setSaving(true);
      try {
        await api.saveWorkflow(buildTemplate());
        toast.success("已保存");
        return true;
      } catch (err) {
        toast.error(err instanceof Error ? err.message : "保存失败");
        return false;
      } finally {
        setSaving(false);
      }
    },
    toast,
  });

  // ── Derived ──
  const selectedNode = nodes.find((n) => n.id === selectedNodeId) || null;

  // ── Load ──
  useEffect(() => {
    if (templateName) {
      api
        .getWorkflow(templateName)
        .then((tmpl) => {
          setName(tmpl.name);
          setDescription(tmpl.description || "");
          setWorkspace(tmpl.workspace || "");
          const flow = templateToFlow(tmpl);
          setNodes(flow.nodes);
          setEdges(flow.edges);
        })
        .catch(() => toast.error("加载工作流失败"));
    }
  }, [templateName]);

  useEffect(() => {
    api
      .listWorkshops()
      .then((data: unknown[]) => {
        setWorkshops(data.map((w: any) => ({ name: w.name, agents: w.agents })));
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!workspace) {
      setWsAgents([]);
      return;
    }
    const ws = workshops.find((w) => w.name === workspace);
    if (ws?.agents) {
      setWsAgents(
        Object.entries(ws.agents).map(([name, cfg]: [string, any]) => ({
          name,
          type: cfg.type || "super",
          model: cfg.model || "",
        }))
      );
    } else {
      setWsAgents([]);
    }
  }, [workspace, workshops]);

  // Sync run status to node data for visual feedback
  useEffect(() => {
    if (Object.keys(runStatus).length === 0) return;
    setNodes((nds) =>
      nds.map((n) => ({
        ...n,
        data: { ...n.data, status: runStatus[n.id]?.status },
      }))
    );
  }, [runStatus, setNodes]);

  // ── Keyboard shortcuts ─────────────────────────────────────
  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement;
      const inInput =
        target.tagName === "INPUT" ||
        target.tagName === "TEXTAREA" ||
        target.tagName === "SELECT" ||
        target.isContentEditable;

      // Ctrl+K — always works (node search)
      if ((e.metaKey || e.ctrlKey) && e.key === "k") {
        e.preventDefault();
        setSearchOpen(true);
        return;
      }

      // Don't steal shortcuts from inputs
      if (inInput) return;

      // Tab — toggle palette
      if (e.key === "Tab") {
        e.preventDefault();
        setPaletteOpen((p) => !p);
        return;
      }

      // Ctrl+S — save
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        save();
        return;
      }

      // Ctrl+Enter — execute
      if ((e.metaKey || e.ctrlKey) && e.key === "Enter") {
        e.preventDefault();
        if (name.trim() && task.trim()) {
          execute();
        } else {
          setShowRunDialog(true);
        }
        return;
      }

      // Ctrl+D — duplicate selected node
      if ((e.metaKey || e.ctrlKey) && e.key === "d" && selectedNode) {
        e.preventDefault();
        duplicateNode(selectedNode.id);
        return;
      }
    };

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [name, task, selectedNode, nodes, edges]);

  // ── Canvas handlers ────────────────────────────────────────
  const onConnect = useCallback(
    (conn: Connection) => {
      setEdges((eds) =>
        addEdge(
          {
            id: `e-${conn.source}-${conn.target}`,
            ...conn,
            markerEnd: { type: MarkerType.ArrowClosed },
            style: { stroke: "var(--border)", strokeWidth: 1.5 },
          },
          eds
        )
      );
    },
    [setEdges]
  );

  // Drag from palette onto canvas
  const onDragOver = useCallback((event: React.DragEvent) => {
    event.preventDefault();
    event.dataTransfer.dropEffect = "move";
  }, []);

  const onDrop = useCallback(
    (event: React.DragEvent) => {
      event.preventDefault();
      const type = event.dataTransfer.getData("application/reactflow-type");
      const label = event.dataTransfer.getData("application/reactflow-label");
      const agentName = event.dataTransfer.getData("application/reactflow-agent");
      if (!type) return;

      const position = { x: event.clientX - 300, y: event.clientY - 120 };
      const id = makeId();
      const newNode: Node = {
        id,
        type: "agent",
        position,
        data: {
          label: label || "新节点",
          agent_name: agentName || "",
          node_type: type,
          prompt: "",
          timeout_seconds: 300,
          notes: "",
          retry_on_fail: false,
          continue_on_fail: false,
        },
      };
      setNodes((nds) => [...nds, newNode]);
      setSelectedNodeId(id);
    },
    [setNodes]
  );

  // ── Node operations ────────────────────────────────────────
  const addNode = (type = "agent", label = "新节点") => {
    const id = makeId();
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "agent",
        position: { x: 200 + Math.random() * 300, y: 100 + Math.random() * 200 },
        data: {
          label,
          agent_name: "",
          node_type: type,
          prompt: "",
          timeout_seconds: 300,
          notes: "",
          retry_on_fail: false,
          continue_on_fail: false,
        },
      },
    ]);
    setSelectedNodeId(id);
  };

  const addAgentNode = (agent: { name: string }) => {
    const id = makeId();
    setNodes((nds) => [
      ...nds,
      {
        id,
        type: "agent",
        position: { x: 200 + Math.random() * 300, y: 100 + Math.random() * 200 },
        data: {
          label: agent.name,
          agent_name: agent.name,
          node_type: "agent",
          prompt: "",
          timeout_seconds: 300,
          notes: "",
          retry_on_fail: false,
          continue_on_fail: false,
        },
      },
    ]);
    setSelectedNodeId(id);
  };

  const duplicateNode = (nodeId: string) => {
    const node = nodes.find((n) => n.id === nodeId);
    if (!node) return;
    const id = makeId();
    const offset = { x: node.position.x + 50, y: node.position.y + 50 };
    setNodes((nds) => [
      ...nds,
      { ...node, id, position: offset, data: { ...node.data }, selected: false },
    ]);
    setSelectedNodeId(id);
  };

  const deleteNode = (nodeId: string) => {
    setNodes((nds) => nds.filter((n) => n.id !== nodeId));
    setEdges((eds) => eds.filter((e) => e.source !== nodeId && e.target !== nodeId));
    if (selectedNodeId === nodeId) setSelectedNodeId(null);
  };

  const updateNodeData = (field: string, value: string | number | boolean) => {
    if (!selectedNode) return;
    setNodes((nds) =>
      nds.map((n) =>
        n.id === selectedNode.id
          ? { ...n, data: { ...n.data, [field]: value } }
          : n
      )
    );
  };

  // ── Build template from canvas ─────────────────────────────
  const buildTemplate = (): WorkflowTemplate => ({
    name,
    description,
    workspace,
    nodes: nodes.map((n) => ({
      id: n.id,
      label: String(n.data.label || ""),
      node_type: (n.data.node_type as "agent" | "condition" | "transform") || "agent",
      agent_name: String(n.data.agent_name || ""),
      prompt: String(n.data.prompt || ""),
      depends_on: edges.filter((e) => e.target === n.id).map((e) => e.source),
      expected_output: "",
      timeout_seconds: Number(n.data.timeout_seconds) || 300,
      notes: String(n.data.notes || ""),
      retry_on_fail: Boolean(n.data.retry_on_fail),
      continue_on_fail: Boolean(n.data.continue_on_fail),
    })),
  });

  // ── Save (for Ctrl+S shortcut) ────────────────────────────
  const save = useCallback(async () => {
    if (!name.trim()) { toast.error("请输入工作流名称"); return; }
    setSaving(true);
    try {
      await api.saveWorkflow(buildTemplate());
      toast.success("已保存");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "保存失败");
    } finally {
      setSaving(false);
    }
  }, [name, description, workspace, nodes, edges, toast]);

  // ── Render ─────────────────────────────────────────────────
  const selectedData = selectedNode?.data || {};

  return (
    <div className="flex flex-col h-[calc(100vh-100px)]">
      {/* Top bar — n8n style: clean, minimal */}
      <div className="flex items-center justify-between mb-3 shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={onBack}
            className="p-2 rounded-lg bg-card border border-border text-muted-foreground hover:text-foreground hover:border-ring/30 transition-colors"
          >
            <ArrowLeft className="w-4 h-4" />
          </button>
          <div>
            <input
              value={name}
              onChange={(e) => setName(e.target.value)}
              placeholder="工作流名称"
              className="text-lg font-semibold bg-transparent placeholder:text-muted-foreground/40 focus:outline-none border-b border-transparent focus:border-ring/30 w-56"
            />
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="描述（可选）"
              className="block text-[11px] text-muted-foreground bg-transparent placeholder:text-muted-foreground/40 focus:outline-none mt-0.5 w-72"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          {/* Node count */}
          <span className="text-[10px] text-muted-foreground/50 mr-2">
            {nodes.length} 节点 · {edges.length} 连线
          </span>

          {running ? (
            <button
              onClick={cancel}
              className="flex items-center gap-1.5 px-3 py-1.5 bg-destructive/10 text-destructive border border-destructive/20 rounded-lg text-xs font-medium hover:bg-destructive/20 transition-colors"
            >
              <XCircle className="w-3.5 h-3.5" /> 取消
            </button>
          ) : (
            <>
              <button
                onClick={() => setShowRunDialog(true)}
                className="flex items-center gap-1.5 px-4 py-1.5 bg-primary text-primary-foreground rounded-lg text-xs font-medium hover:bg-primary/90 transition-colors"
              >
                <Play className="w-3.5 h-3.5" /> 执行
                <kbd className="text-[9px] ml-1 opacity-60 font-mono">
                  ⌘↵
                </kbd>
              </button>
              <Button onClick={save} disabled={saving} variant="outline" size="sm">
                {saving ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin mr-1.5" />
                ) : (
                  <Save className="w-3.5 h-3.5 mr-1.5" />
                )}
                保存
                <kbd className="text-[9px] ml-1 opacity-40 font-mono">⌘S</kbd>
              </Button>
            </>
          )}
        </div>
      </div>

      {/* Main: Palette + Canvas + Config */}
      <div className="flex gap-3 flex-1 min-h-0">
        {/* Left: Node Palette */}
        {paletteOpen && (
          <NodePalette
            workspaceAgents={wsAgents}
            onAddNode={addNode}
            onAddAgentNode={addAgentNode}
          />
        )}

        {/* Center: Canvas */}
        <div className="flex-1 bg-card border border-border rounded-xl overflow-hidden">
          <ReactFlow
            nodes={nodes}
            edges={edges}
            onNodesChange={onNodesChange}
            onEdgesChange={onEdgesChange}
            onConnect={onConnect}
            onNodeClick={(_e, n) => setSelectedNodeId(n.id)}
            onPaneClick={() => setSelectedNodeId(null)}
            onDragOver={onDragOver}
            onDrop={onDrop}
            nodeTypes={nodeTypes}
            fitView
            deleteKeyCode={["Backspace", "Delete"]}
            multiSelectionKeyCode="Shift"
          >
            <Background
              variant={BackgroundVariant.Dots}
              gap={20}
              size={1}
              color="var(--border)"
            />
            <Controls className="!bg-card !border-border !rounded-lg !shadow-sm" />
            <MiniMap
              className="!bg-card !border-border !rounded-lg"
              nodeColor="var(--primary)"
              maskColor="var(--background)/80"
            />
            <Panel position="top-left" className="!bg-transparent !m-2">
              {!paletteOpen && (
                <button
                  onClick={() => setPaletteOpen(true)}
                  className="px-3 py-1.5 bg-card border border-border rounded-lg text-xs text-muted-foreground hover:text-foreground hover:border-ring/30 transition-colors shadow-sm"
                >
                  Tab 展开面板
                </button>
              )}
            </Panel>
          </ReactFlow>
        </div>

        {/* Right: Node Config Panel / Run Status */}
        {selectedNode ? (
          <NodeConfigPanel
            key={selectedNode.id}
            nodeId={selectedNode.id}
            label={String(selectedData.label || "")}
            nodeType={(selectedData.node_type as "agent" | "condition" | "transform") || "agent"}
            agentName={String(selectedData.agent_name || "")}
            prompt={String(selectedData.prompt || "")}
            timeoutSeconds={Number(selectedData.timeout_seconds) || 300}
            notes={String(selectedData.notes || "")}
            retryOnFail={Boolean(selectedData.retry_on_fail)}
            continueOnFail={Boolean(selectedData.continue_on_fail)}
            agents={wsAgents}
            lastOutput={
              runResult?.node_results?.[selectedNode.id]?.output ||
              (runStatus[selectedNode.id]?.detail)
            }
            lastStatus={
              runResult?.node_results?.[selectedNode.id]?.status ||
              runStatus[selectedNode.id]?.status
            }
            onChange={updateNodeData}
            onDelete={() => deleteNode(selectedNode.id)}
            onExecuteNode={() => executeSingleNode(selectedNode.id)}
            executing={executingNode === selectedNode.id}
          />
        ) : running || runResult ? (
          /* Run status panel when no node selected */
          <div className="w-72 shrink-0 bg-card border border-border rounded-xl p-4 space-y-3 overflow-auto">
            <h3 className="text-sm font-semibold">
              {running ? "执行中..." : runResult?.status === "passed" ? "执行完成" : "执行结果"}
            </h3>
            {running && (
              <span className="text-[10px] text-primary animate-pulse">运行中</span>
            )}
            <div className="space-y-2">
              {nodes.map((n) => {
                const s = runStatus[n.id];
                const r = runResult?.node_results?.[n.id];
                const st = r?.status || s?.status;
                return (
                  <div
                    key={n.id}
                    className={`p-2.5 rounded-lg border text-xs ${
                      st === "running"
                        ? "border-primary/30 bg-primary/5"
                        : st === "passed"
                        ? "border-emerald-500/20 bg-emerald-50/30 dark:bg-emerald-950/10"
                        : st === "failed"
                        ? "border-red-400/20 bg-red-50/30 dark:bg-red-950/10"
                        : "border-border bg-background"
                    }`}
                  >
                    <div className="flex items-center justify-between">
                      <span className="font-medium truncate">
                        {String(n.data.label || n.id)}
                      </span>
                      <span
                        className={`text-[9px] ${
                          st === "running"
                            ? "text-primary"
                            : st === "passed"
                            ? "text-emerald-600 dark:text-emerald-400"
                            : st === "failed"
                            ? "text-red-500"
                            : "text-muted-foreground"
                        }`}
                      >
                        {st === "running"
                          ? "运行中"
                          : st === "passed"
                          ? "通过"
                          : st === "failed"
                          ? "失败"
                          : "等待"}
                      </span>
                    </div>
                    {r?.error && (
                      <p className="text-red-500 mt-1 line-clamp-2">{r.error}</p>
                    )}
                    {r?.output && (
                      <p className="text-muted-foreground mt-1 line-clamp-2">{r.output}</p>
                    )}
                  </div>
                );
              })}
            </div>
            {runResult?.final_output && (
              <div>
                <label className="text-[10px] uppercase tracking-wider text-muted-foreground">
                  最终产出
                </label>
                <div className="mt-1 p-3 bg-background border border-border rounded-lg">
                  <p className="text-[10px] whitespace-pre-wrap line-clamp-6 font-mono">
                    {runResult.final_output}
                  </p>
                </div>
              </div>
            )}
          </div>
        ) : null}
      </div>

      {/* Execute Dialog */}
      <Dialog open={showRunDialog} onOpenChange={setShowRunDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>执行工作流</DialogTitle>
          </DialogHeader>
          <div className="space-y-4">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                项目
              </label>
              <select
                value={runWorkspace || workspace}
                onChange={(e) => setRunWorkspace(e.target.value)}
                className="w-full h-9 bg-background border border-border rounded-md px-3 py-2 text-sm focus:outline-none focus:border-ring/50"
              >
                <option value="">{workspace || "选择项目..."}</option>
                {workshops.map((w) => (
                  <option key={w.name} value={w.name}>
                    {w.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1.5 block">
                任务描述
              </label>
              <textarea
                value={task}
                onChange={(e) => setTask(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) execute();
                }}
                placeholder="描述要执行的任务..."
                rows={5}
                className="w-full bg-background border border-border rounded-md px-3 py-2 text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:border-ring/50 resize-none"
              />
              <p className="text-[10px] text-muted-foreground mt-1">
                ⌘+Enter 快速执行
              </p>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowRunDialog(false)}>
              取消
            </Button>
            <Button onClick={execute} disabled={!task.trim() || !name.trim()} className="gap-1.5">
              <Play className="w-4 h-4" /> 开始执行
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Node Search Dialog (Ctrl+K) */}
      <NodeSearchDialog
        open={searchOpen}
        onClose={() => setSearchOpen(false)}
        onSelect={(type, label) => addNode(type, label)}
      />
    </div>
  );
}

import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { DndContext, DragOverlay, closestCorners, PointerSensor, TouchSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { Bot, Pencil, Play, RefreshCw, ChevronDown, X, Clock, CheckCircle2, XCircle, Loader2, Wrench } from "lucide-react";
import { api, connectWS, getAuthHeaders } from "../lib/api";
import type { KanbanBoard as Board, KanbanCard, KanbanList } from "../lib/types";
import { useToast } from "./Toast";

// ── Helpers ──────────────────────────────────────────────────

const AGENT_COLORS = ["#6366f1", "#06b6d4", "#f59e0b", "#10b981", "#ec4899", "#8b5cf6", "#14b8a6", "#f97316"];

function agentColor(name: string): string {
  let hash = 0;
  for (const c of name) hash = (hash * 31 + c.charCodeAt(0)) | 0;
  return AGENT_COLORS[Math.abs(hash) % AGENT_COLORS.length];
}

function parseCardMeta(card: KanbanCard): KanbanCard {
  if (card.is_agent !== undefined) return card; // already parsed
  const desc = card.description || "";
  const metaIdx = desc.lastIndexOf("__META__");
  let output = "";
  let meta: Record<string, unknown> = {};
  if (metaIdx >= 0) {
    output = desc.slice(0, metaIdx).trim();
    try { meta = JSON.parse(desc.slice(metaIdx + 8)); } catch { /* ignore */ }
  } else if (card.source_agent) {
    output = desc;
  }
  return {
    ...card,
    output_summary: output.slice(0, 200),
    turns: meta.turns as number | undefined,
    cost_usd: meta.cost_usd as number | undefined,
    tools_used: meta.tools_used as string[] | undefined,
    model: meta.model as string | undefined,
    is_agent: !!card.source_agent,
  };
}

// ── Agent Card ─────────────────────────────────────────────────

function AgentCard({ card, onReRun, onView, isReRunning }: { card: KanbanCard; onReRun: (card: KanbanCard) => void; onView: (card: KanbanCard) => void; isReRunning?: boolean }) {
  const c = parseCardMeta(card);
  const color = agentColor(c.source_agent);
  const statusIcon = c.task_status === "in_progress"
    ? <Loader2 className="w-3 h-3 text-primary animate-spin" />
    : c.task_status === "done"
    ? <CheckCircle2 className="w-3 h-3 text-emerald-500" />
    : <XCircle className="w-3 h-3 text-red-400" />;

  return (
    <div
      onClick={() => onView(c)}
      className="group bg-background/80 border border-border/60 rounded-xl overflow-hidden cursor-pointer hover:border-ring/30 transition-all"
    >
      {/* Color stripe + header */}
      <div className="flex items-stretch">
        <div className="w-1 shrink-0" style={{ backgroundColor: color }} />
        <div className="flex-1 px-3 py-2.5 min-w-0">
          <div className="flex items-center gap-1.5 mb-0.5">
            <Bot className="w-3 h-3 text-muted-foreground shrink-0" />
            <span className="text-[10px] text-muted-foreground font-medium">{c.source_agent}</span>
            <span className="ml-auto">{statusIcon}</span>
          </div>
          <div className="text-sm text-foreground font-medium truncate">{c.title.slice(0, 80)}</div>
        </div>
      </div>
      {/* Output preview */}
      {c.output_summary && (
        <div className="px-3 pb-2">
          <p className="text-[11px] text-muted-foreground/60 line-clamp-2 leading-relaxed">{c.output_summary.slice(0, 80)}</p>
        </div>
      )}
      {/* Error preview */}
      {c.task_status === "blocked" && !c.output_summary && card.description && (
        <div className="px-3 pb-2">
          <p className="text-[11px] text-red-400/70 line-clamp-1">{card.description.slice(0, 60)}</p>
        </div>
      )}
      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-border/40 flex items-center gap-2 text-[10px] text-muted-foreground/50">
        {c.turns != null && <span>{c.turns}轮</span>}
        {c.tools_used && c.tools_used.length > 0 && (
          <span className="flex items-center gap-0.5"><Wrench className="w-2.5 h-2.5" />{c.tools_used.length}</span>
        )}
        <button onClick={e => { e.stopPropagation(); onReRun(c); }} disabled={isReRunning}
          className="ml-auto flex items-center gap-0.5 text-primary/70 hover:text-primary transition-colors disabled:opacity-40">
          <RefreshCw className={`w-2.5 h-2.5 ${isReRunning ? 'animate-spin' : ''}`} />{isReRunning ? '执行中' : '重跑'}
        </button>
      </div>
    </div>
  );
}

// ── Manual Card (simpler, draggable) ───────────────────────────

function ManualCard({ card, onEdit, onDelete, editingCard, editingTitle, setEditingTitle, saveEdit }: {
  card: KanbanCard; onEdit: (card: KanbanCard) => void; onDelete: (id: string) => void;
  editingCard: string | null; editingTitle: string; setEditingTitle: (v: string) => void;
  saveEdit: (card: KanbanCard) => void;
}) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id, data: { type: "card", card } });
  return (
    <div ref={setNodeRef} style={{ transition, transform: CSS.Translate.toString(transform) }}
      className={`group bg-background/80 border border-border/60 rounded-xl px-3 py-2.5 text-sm text-foreground flex items-center gap-2 cursor-default hover:border-border transition-colors ${isDragging ? "opacity-30" : ""}`}>
      <button {...attributes} {...listeners} className="text-muted-foreground/20 hover:text-muted-foreground/60 cursor-grab shrink-0"><Pencil className="w-3 h-3" /></button>
      {editingCard === card.id ? (
        <input autoFocus value={editingTitle} onChange={e => setEditingTitle(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter") saveEdit(card); if (e.key === "Escape") setEditingCard(null); }}
          onBlur={() => saveEdit(card)}
          className="flex-1 min-w-0 bg-transparent border-b border-primary/30 text-sm outline-none" />
      ) : (
        <span className="flex-1 min-w-0 cursor-pointer" onClick={() => onEdit(card)}>{card.title}</span>
      )}
      <button onClick={() => onDelete(card.id)} className="opacity-0 group-hover:opacity-100 text-muted-foreground/40 hover:text-destructive shrink-0 text-xs">×</button>
    </div>
  );
}

// ── Column ─────────────────────────────────────────────────────

function Column({ list, cards, onAddManual, onDelCard, onEditCard, onReRun, onView, executingCard }: {
  list: KanbanList; cards: KanbanCard[]; onAddManual: (listId: string, title: string) => void;
  onDelCard: (id: string) => void; onEditCard: (card: KanbanCard) => void;
  onReRun: (card: KanbanCard) => void; onView: (card: KanbanCard) => void;
  executingCard: string | null;
  editingCard: string | null; editingTitle: string;
  setEditingTitle: (v: string) => void; saveEditCard: (card: KanbanCard) => void;
}) {
  const agentCards = cards.filter(c => c.source_agent);
  const manualCards = cards.filter(c => !c.source_agent);
  const manualIds = useMemo(() => manualCards.map(c => c.id), [manualCards]);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");

  return (
    <div className="bg-card/40 border border-border/50 rounded-2xl min-w-[260px] flex-1 flex flex-col min-h-[500px]">
      <div className="px-4 py-3 flex items-center justify-between shrink-0">
        <span className="text-xs font-semibold text-foreground/70">{list.name}</span>
        <span className="text-[11px] text-muted-foreground/30">{cards.length}</span>
      </div>
      <div className="flex-1 px-2 pb-2 space-y-2 overflow-auto max-h-[calc(100vh-280px)]">
        {/* Agent cards (non-draggable) */}
        {agentCards.map(c => <AgentCard key={c.id} card={c} onReRun={onReRun} onView={onView} isReRunning={executingCard === c.id} />)}

        {/* Manual cards (draggable) */}
        <SortableContext items={manualIds} strategy={verticalListSortingStrategy}>
          {manualCards.map(c => <ManualCard key={c.id} card={c} onEdit={onEditCard} onDelete={onDelCard}
          editingCard={editingCard} editingTitle={editingTitle} setEditingTitle={setEditingTitle} saveEdit={(card) => saveEditCard(card)} />)}
        </SortableContext>

        {/* Add manual card */}
        {adding ? (
          <div className="bg-background border border-border/60 rounded-lg p-2 space-y-1.5">
            <input autoFocus value={title} onChange={e => setTitle(e.target.value)} onKeyDown={e => { if (e.key === "Enter") { onAddManual(list.id, title.trim()); setTitle(""); setAdding(false); } if (e.key === "Escape") setAdding(false); }} placeholder="备注..." className="w-full bg-transparent border-none outline-none text-xs text-foreground placeholder:text-muted-foreground/40" />
            <div className="flex gap-1.5"><button onClick={() => { onAddManual(list.id, title.trim()); setTitle(""); setAdding(false); }} className="px-2.5 py-1 text-[10px] bg-primary/10 text-primary rounded-md">添加</button><button onClick={() => setAdding(false)} className="px-2.5 py-1 text-[10px] text-muted-foreground/50">取消</button></div>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} className="w-full py-2 border border-dashed border-border/30 rounded-lg text-xs text-muted-foreground/30 hover:text-muted-foreground/60 hover:border-border/50 transition-colors">+ 备忘</button>
        )}
      </div>
    </div>
  );
}

// ── Detail Panel ───────────────────────────────────────────────

function DetailPanel({ card, onClose, onReRun, onViewInChat }: {
  card: KanbanCard | null; onClose: () => void; onReRun: (card: KanbanCard) => void;
  onViewInChat: (card: KanbanCard) => void;
}) {
  if (!card) return null;
  const c = parseCardMeta(card);
  return (
    <div className="w-80 shrink-0 bg-card border border-border rounded-xl flex flex-col h-full overflow-auto">
      <div className="p-4 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <Bot className="w-4 h-4 text-primary" />
          <span className="text-sm font-semibold">{c.source_agent}</span>
        </div>
        <button onClick={onClose} className="p-1 rounded-md text-muted-foreground hover:text-foreground"><X className="w-4 h-4" /></button>
      </div>
      <div className="flex-1 p-4 space-y-4 overflow-auto">
        {/* Prompt */}
        <div>
          <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">任务</div>
          <div className="p-3 bg-background border border-border rounded-lg text-xs leading-relaxed whitespace-pre-wrap">{c.title}</div>
        </div>
        {/* Output */}
        {c.output_summary && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">输出</div>
            <div className="p-3 bg-background border border-border rounded-lg text-xs leading-relaxed whitespace-pre-wrap max-h-48 overflow-auto">{c.output_summary}</div>
          </div>
        )}
        {/* Tools used */}
        {c.tools_used && c.tools_used.length > 0 && (
          <div>
            <div className="text-[10px] uppercase tracking-wider text-muted-foreground mb-1.5">工具调用</div>
            <div className="flex flex-wrap gap-1">
              {c.tools_used.map(t => (
                <span key={t} className="text-[10px] px-2 py-0.5 rounded-full bg-muted text-muted-foreground">{t}</span>
              ))}
            </div>
          </div>
        )}
        {/* Meta */}
        <div className="flex gap-4 text-[10px] text-muted-foreground/60">
          {c.turns != null && <span>{c.turns} 轮对话</span>}
          {c.cost_usd != null && <span>${c.cost_usd.toFixed(4)}</span>}
          {c.model && <span>{c.model}</span>}
        </div>
        {/* Thinking placeholder */}
        <div className="p-3 bg-muted/30 border border-border/30 rounded-lg text-[10px] text-muted-foreground/50 italic text-center">
          思考过程暂不支持（需要 Agent trace 功能 — P1）
        </div>
      </div>
      <div className="p-4 border-t border-border space-y-2 shrink-0">
        <button onClick={() => onReRun(c)} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-primary/10 text-primary border border-primary/20 rounded-lg text-xs font-medium hover:bg-primary/20 transition-colors">
          <RefreshCw className="w-3 h-3" /> 用相同输入重跑
        </button>
        <button onClick={() => { onViewInChat(c); onClose(); }} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-muted/50 border border-border/50 rounded-lg text-xs text-muted-foreground hover:text-foreground transition-colors">
          在对话中查看
        </button>
        <button onClick={onClose} className="w-full py-1.5 text-[10px] text-muted-foreground/50 hover:text-muted-foreground transition-colors">关闭</button>
      </div>
    </div>
  );
}

// ── Main Board ─────────────────────────────────────────────────

export function KanbanBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<string | null>(null);
  const [lists, setLists] = useState<KanbanList[]>([]);
  const [activeCard, setActiveCard] = useState<KanbanCard | null>(null);
  const [viewCard, setViewCard] = useState<KanbanCard | null>(null);
  const [agents, setAgents] = useState<{ name: string }[]>([]);
  const [selectedAgent, setSelectedAgent] = useState("");
  const [taskInput, setTaskInput] = useState("");
  const [executing, setExecuting] = useState(false);
  const [executingCard, setExecutingCard] = useState<string | null>(null);
  const [filterAgent, setFilterAgent] = useState("");
  const wsRef = useRef<(() => void) | null>(null);
  const toast = useToast();

  // Compute filter options
  const agentOptions = useMemo(() => {
    const names = new Set<string>();
    for (const lst of lists) {
      for (const c of lst.cards || []) {
        if (c.source_agent) names.add(c.source_agent);
      }
    }
    return [...names].sort();
  }, [lists]);

  // Apply filters to lists
  const filteredLists = useMemo(() => {
    return lists.map(lst => ({
      ...lst,
      cards: (lst.cards || []).filter(c => {
        if (filterAgent && c.source_agent && c.source_agent !== filterAgent) return false;
        return true;
      }),
    }));
  }, [lists, filterAgent]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
  );

  const loadBoard = useCallback(async (id: string) => {
    try { const b = await api.getBoard(id); setLists(b.lists || []); } catch { toast.error("加载看板失败"); }
  }, []);

  useEffect(() => { api.listBoards().then(setBoards).catch(() => {}); }, []);
  useEffect(() => { if (!selectedBoard && boards.length) setSelectedBoard(boards[0].id); }, [boards]);
  useEffect(() => {
    const ws = boards.find(b => b.id === selectedBoard)?.workshop_name;
    if (ws) api.listAgents(ws).then(setAgents).catch(() => {});
  }, [selectedBoard, boards]);

  useEffect(() => {
    if (!selectedBoard) return;
    loadBoard(selectedBoard);
    wsRef.current = connectWS(selectedBoard, (event: string, data: any) => {
      setLists(prev => {
        const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
        const listIdx = (lid: string) => next.findIndex(l => l.id === lid);
        switch (event) {
          case "card_created": {
            const i = listIdx(data.list_id);
            if (i >= 0) next[i].cards = [...(next[i].cards || []), data];
            return next;
          }
          case "card_updated": {
            for (const lst of next) {
              const ci = lst.cards?.findIndex(c => c.id === data.id);
              if (ci !== undefined && ci >= 0) { lst.cards![ci] = { ...lst.cards![ci], ...data }; break; }
            }
            return next;
          }
          case "card_moved": {
            for (const lst of next) lst.cards = lst.cards?.filter(c => c.id !== data.id);
            const i = listIdx(data.list_id);
            if (i >= 0) next[i].cards = [...(next[i].cards || []), data];
            return next;
          }
          case "card_deleted": {
            for (const lst of next) lst.cards = lst.cards?.filter(c => c.id !== data.id);
            return next;
          }
          default: return prev;
        }
      });
    });
    return () => wsRef.current?.();
  }, [selectedBoard, loadBoard]);

  // ── Execute agent from input bar ──────────────────────────
  const executeAgent = async () => {
    if (!taskInput.trim() || !selectedAgent || !selectedBoard) return;
    const task = taskInput.trim();
    setTaskInput("");
    setExecuting(true);

    try {
      const res = await fetch("/api/agent/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ task, workshop: boards.find(b => b.id === selectedBoard)?.workshop_name || "" }),
      });
      if (!res.ok) { toast.error("执行失败"); return; }
      // Read SSE stream to completion (card will appear via WebSocket)
      const reader = res.body?.getReader();
      if (reader) {
        const decoder = new TextDecoder();
        while (true) {
          const { done } = await reader.read();
          if (done) break;
        }
      }
    } catch (err) { toast.error("执行失败"); }
    finally { setExecuting(false); }
  };

  // ── Re-run agent ──────────────────────────────────────────
  const reRunAgent = async (card: KanbanCard) => {
    const c = parseCardMeta(card);
    const ws = boards.find(b => b.id === selectedBoard)?.workshop_name || "";
    setExecutingCard(card.id);
    try {
      await fetch("/api/agent/run/stream", {
        method: "POST",
        headers: { "Content-Type": "application/json", ...getAuthHeaders() },
        body: JSON.stringify({ task: c.title, workshop: ws }),
      });
    } catch { toast.error("重跑失败"); }
    finally { setExecutingCard(null); }
  };

  // ── Manual card CRUD ──────────────────────────────────────
  const addManual = async (listId: string, title: string) => {
    try { await api.createCard(listId, title); if (selectedBoard) loadBoard(selectedBoard); } catch { toast.error("创建失败"); }
  };
  const delCard = async (id: string) => {
    try { await api.deleteCard(id); if (selectedBoard) loadBoard(selectedBoard); } catch { toast.error("删除失败"); }
  };
  const [editingCard, setEditingCard] = useState<string | null>(null);
  const [editingTitle, setEditingTitle] = useState("");
  const startEditCard = (card: KanbanCard) => { setEditingCard(card.id); setEditingTitle(card.title); };
  const saveEditCard = async (card: KanbanCard) => {
    if (editingTitle.trim() && editingTitle !== card.title) {
      try { await api.updateCard(card.id, { title: editingTitle.trim() }); if (selectedBoard) loadBoard(selectedBoard); }
      catch { toast.error("编辑失败"); }
    }
    setEditingCard(null);
  };
  const moveCard = async (cardId: string, toListId: string) => {
    setLists(prev => {
      const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
      let moved: KanbanCard | null = null;
      for (const lst of next) {
        const idx = lst.cards?.findIndex(c => c.id === cardId) ?? -1;
        if (idx >= 0) { moved = lst.cards![idx]; lst.cards!.splice(idx, 1); break; }
      }
      if (moved) {
        const target = next.find(l => l.id === toListId);
        if (target) target.cards = [...(target.cards || []), { ...moved, list_id: toListId }];
      }
      return next;
    });
    try { await api.moveCard(cardId, toListId); } catch { if (selectedBoard) loadBoard(selectedBoard); }
  };

  if (boards.length === 0) return (
    <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground/30">暂无看板 — Agent 执行后自动创建</div>
  );

  return (
    <div className="h-full flex flex-col min-h-0 space-y-3">
      {/* ── Input bar ── */}
      <div className="flex items-center gap-2 shrink-0">
        <div className="relative">
          <select value={selectedAgent} onChange={e => setSelectedAgent(e.target.value)}
            className="appearance-none h-9 bg-background border border-border rounded-lg pl-3 pr-8 text-sm focus:outline-none focus:border-ring/50">
            <option value="">选 Agent</option>
            {agents.map(a => <option key={a.name} value={a.name}>{a.name}</option>)}
          </select>
          <ChevronDown className="absolute right-2 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-muted-foreground pointer-events-none" />
        </div>
        <input value={taskInput} onChange={e => setTaskInput(e.target.value)}
          onKeyDown={e => { if (e.key === "Enter" && !executing) executeAgent(); }}
          placeholder="描述要做什么..." disabled={executing}
          className="flex-1 h-9 bg-background border border-border rounded-lg px-3 text-sm placeholder:text-muted-foreground/40 focus:outline-none focus:border-ring/50 disabled:opacity-50" />
        <button onClick={executeAgent} disabled={executing || !taskInput.trim() || !selectedAgent}
          className="h-9 px-4 bg-primary/10 text-primary border border-primary/20 rounded-lg text-sm font-medium hover:bg-primary/20 transition-colors disabled:opacity-40 flex items-center gap-1.5 shrink-0">
          {executing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
          执行
        </button>
      </div>

      {/* ── Filter bar ── */}
      <div className="flex items-center gap-2 shrink-0 text-xs text-muted-foreground">
        <span className="text-[10px]">筛选：</span>
        <select value={filterAgent} onChange={e => setFilterAgent(e.target.value)}
          className="appearance-none h-7 bg-background border border-border rounded-md px-2 pr-6 text-[11px] focus:outline-none focus:border-ring/30">
          <option value="">全部 Agent ({agentOptions.length})</option>
          {agentOptions.map(a => <option key={a} value={a}>{a}</option>)}
        </select>
        {filterAgent && (
          <button onClick={() => setFilterAgent("")} className="text-[10px] text-primary/70 hover:text-primary">清除</button>
        )}
      </div>

      {/* ── Board tabs ── */}
      {boards.length > 1 && (
        <div className="flex gap-2 shrink-0">
          {boards.map(b => (
            <button key={b.id} onClick={() => setSelectedBoard(b.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${selectedBoard === b.id ? "bg-primary/15 text-primary border border-primary/30" : "bg-card/30 border border-border/30 text-muted-foreground hover:text-foreground hover:border-border/50"}`}
            >{b.name}</button>
          ))}
        </div>
      )}

      {/* ── Board body ── */}
      <div className="flex-1 flex gap-4 min-h-0">
        <div className="flex-1 flex gap-4 overflow-x-auto pb-4 items-start min-h-0">
          <DndContext sensors={sensors} collisionDetection={closestCorners}
            onDragStart={e => { const d = e.active.data.current; if (d?.type === "card") setActiveCard(d.card as KanbanCard); }}
            onDragEnd={e => {
              setActiveCard(null); if (!e.over) return;
              const a = e.active.data.current; const o = e.over.data.current;
              if (a?.type === "card" && !(a.card as KanbanCard).source_agent) {
                const tid = o?.type === "col" ? (o.listId as string) : (o?.card as KanbanCard)?.list_id;
                if (tid && tid !== (a.card as KanbanCard).list_id) moveCard((a.card as KanbanCard).id, tid);
              }
            }}
          >
            {lists.length > 0 ? filteredLists.map(l => (
              <Column key={l.id} list={l} cards={l.cards || []}
                onAddManual={addManual} onDelCard={delCard} onEditCard={startEditCard}
                onReRun={reRunAgent} onView={setViewCard} executingCard={executingCard}
                editingCard={editingCard} editingTitle={editingTitle} setEditingTitle={setEditingTitle} saveEditCard={saveEditCard} />
            )) : (
              <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground/30">
                Agent 执行后卡片将自动出现在这里
              </div>
            )}
            <DragOverlay>{activeCard ? <div className="bg-background border border-primary/30 rounded-xl p-3 rotate-2 shadow-xl text-sm text-foreground">{activeCard.title}</div> : null}</DragOverlay>
          </DndContext>
        </div>

        {/* Detail panel */}
        {viewCard && (
          <DetailPanel card={viewCard} onClose={() => setViewCard(null)} onReRun={reRunAgent}
            onViewInChat={(card) => {
              // Navigate to chat panel and set input to the task prompt
              window.dispatchEvent(new CustomEvent("navigate", { detail: { panel: "chat", task: card.title } }));
            }} />
        )}
      </div>

      {/* Hint */}
      <div className="text-center text-[9px] text-muted-foreground/25 shrink-0 pb-1">
        Agent 执行后卡片自动出现 · 手动拖拽仅限备忘卡片 · 点 Agent 卡片查看详情
      </div>
    </div>
  );
}


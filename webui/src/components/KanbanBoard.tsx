import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { DndContext, DragOverlay, closestCorners, KeyboardSensor, PointerSensor, TouchSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { api, connectWS } from "../lib/api";
import type { KanbanBoard as Board, KanbanCard, KanbanList } from "../lib/types";
import { useToast } from "./Toast";

function Card({ card, onDelete }: { card: KanbanCard; onDelete: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id, data: { type: "card", card } });
  return (
    <div ref={setNodeRef} style={{ transition, transform: CSS.Translate.toString(transform) }}
      className={`group bg-background/80 border border-border/60 rounded-xl px-3 py-2.5 text-sm text-foreground flex items-center gap-2 cursor-default hover:border-border transition-colors ${isDragging ? "opacity-30" : ""}`}>
      <button {...attributes} {...listeners} className="text-muted-foreground/20 hover:text-muted-foreground/60 cursor-grab shrink-0"><GripVertical className="w-3 h-3" /></button>
      <span className="flex-1 min-w-0">{card.title}</span>
      <button onClick={() => onDelete(card.id)} className="opacity-0 group-hover:opacity-100 text-muted-foreground/40 hover:text-destructive shrink-0 text-xs">×</button>
    </div>
  );
}

function Column({ list, cards, onAdd, onDelCard }: { list: KanbanList; cards: KanbanCard[]; onAdd: (listId: string, title: string) => void; onDelCard: (id: string) => void }) {
  const ids = useMemo(() => cards.map(c => c.id), [cards]);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const submit = () => { if (title.trim()) { onAdd(list.id, title.trim()); setTitle(""); setAdding(false); } else setAdding(false); };

  return (
    <div className="bg-card/40 border border-border/50 rounded-2xl w-[290px] shrink-0 flex flex-col min-h-[320px]">
      <div className="px-4 py-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground/70">{list.name}</span>
        <span className="text-[11px] text-muted-foreground/30">{cards.length}</span>
      </div>
      <div className="flex-1 px-2 pb-2 space-y-1.5 overflow-auto max-h-[62vh]">
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {cards.map(c => <Card key={c.id} card={c} onDelete={onDelCard} />)}
        </SortableContext>
        {adding ? (
          <div className="bg-background border border-border/60 rounded-lg p-2 space-y-1.5">
            <input autoFocus value={title} onChange={e => setTitle(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submit(); if (e.key === "Escape") setAdding(false); }} placeholder="卡片标题..." className="w-full bg-transparent border-none outline-none text-xs text-foreground placeholder:text-muted-foreground/40" />
            <div className="flex gap-1.5"><button onClick={submit} className="px-2.5 py-1 text-[10px] bg-primary/10 text-primary rounded-md">添加</button><button onClick={() => setAdding(false)} className="px-2.5 py-1 text-[10px] text-muted-foreground/50">取消</button></div>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} className="w-full py-2.5 border border-dashed border-border/30 rounded-lg text-xs text-muted-foreground/30 hover:text-muted-foreground/60 hover:border-border/50 transition-colors">+ 添加卡片</button>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<string | null>(null);
  const [lists, setLists] = useState<KanbanList[]>([]);
  const [activeCard, setActiveCard] = useState<KanbanCard | null>(null);
  const wsRef = useRef<(() => void) | null>(null);
  const toast = useToast();

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadBoard = useCallback(async (id: string) => {
    try { const b = await api.getBoard(id); setLists(b.lists || []); } catch (err) { console.error("加载看板失败", err); toast.error("加载看板失败"); }
  }, []);

  useEffect(() => { api.listBoards().then(setBoards).catch((err) => { console.error("加载看板列表失败", err); }); }, []);
  useEffect(() => { if (!selectedBoard && boards.length) setSelectedBoard(boards[0].id); }, [boards]);

  // ── WebSocket 增量更新（非全量刷新） ──
  useEffect(() => {
    if (!selectedBoard) return;
    loadBoard(selectedBoard);

    wsRef.current = connectWS(selectedBoard, (event: string, data: any) => {
      setLists((prev) => {
          const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
          const listIdx = (lid: string) => next.findIndex(l => l.id === lid);

          switch (event) {
            case "card_created": {
              const i = listIdx(data.list_id);
              if (i >= 0) { next[i].cards = [...(next[i].cards || []), data]; }
              return next;
            }
            case "card_updated": {
              for (const lst of next) {
                const ci = lst.cards?.findIndex(c => c.id === data.id);
                if (ci !== undefined && ci >= 0) {
                  lst.cards![ci] = { ...lst.cards![ci], ...data };
                  break;
                }
              }
              return next;
            }
            case "card_moved": {
              // Remove from old list, add to new list
              for (const lst of next) {
                lst.cards = lst.cards?.filter(c => c.id !== data.id);
              }
              const i = listIdx(data.list_id);
              if (i >= 0) { next[i].cards = [...(next[i].cards || []), data]; }
              return next;
            }
            case "card_deleted": {
              for (const lst of next) {
                lst.cards = lst.cards?.filter(c => c.id !== data.id);
              }
              return next;
            }
            case "list_created": {
              next.push({ id: data.id, board_id: selectedBoard!, name: data.name, position: next.length, cards: [] });
              return next;
            }
            case "list_deleted": {
              return next.filter(l => l.id !== data.id);
            }
            default:
              return prev;
          }
      });
    });

    return () => wsRef.current?.();
  }, [selectedBoard, loadBoard]);

  // ── 乐观更新：添加卡片 ──
  const addCard = async (listId: string, title: string) => {
    const tempId = "temp-" + Date.now();
    const optimistic: KanbanCard = { id: tempId, list_id: listId, title, description: "", position: 999, labels: [], task_status: "todo", source_agent: "", source_task_id: "" };
    setLists(prev => prev.map(l => l.id === listId ? { ...l, cards: [...(l.cards || []), optimistic] } : l));
    try {
      const real = await api.createCard(listId, title);
      setLists(prev => prev.map(l => l.id === listId ? { ...l, cards: (l.cards || []).map(c => c.id === tempId ? real : c) } : l));
    } catch (err) {
      setLists(prev => prev.map(l => l.id === listId ? { ...l, cards: (l.cards || []).filter(c => c.id !== tempId) } : l));
      console.error("创建卡片失败", err); toast.error("创建卡片失败");
    }
  };

  // ── 乐观更新：删除卡片 ──
  const delCard = async (id: string) => {
    // find and snapshot the card
    let snapshot: KanbanCard | null = null;
    let snapshotListId = "";
    setLists(prev => {
      const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
      for (const lst of next) {
        const idx = lst.cards?.findIndex(c => c.id === id) ?? -1;
        if (idx >= 0) {
          snapshot = lst.cards![idx];
          snapshotListId = lst.id;
          lst.cards!.splice(idx, 1);
          break;
        }
      }
      return next;
    });
    try {
      await api.deleteCard(id);
    } catch (err) {
      if (snapshot && snapshotListId) {
        setLists(prev => prev.map(l => l.id === snapshotListId ? { ...l, cards: [...(l.cards || []), snapshot!] } : l));
      }
      console.error("删除卡片失败", err); toast.error("删除卡片失败");
    }
  };

  // ── 乐观更新：拖拽移动 ──
  const moveCard = async (cardId: string, toListId: string) => {
    let snapshot: KanbanCard | null = null;
    let fromListId = "";
    // Optimistically move
    setLists(prev => {
      const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
      for (const lst of next) {
        const idx = lst.cards?.findIndex(c => c.id === cardId) ?? -1;
        if (idx >= 0) {
          snapshot = { ...lst.cards![idx] };
          fromListId = lst.id;
          lst.cards!.splice(idx, 1);
          break;
        }
      }
      const target = next.find(l => l.id === toListId);
      if (target && snapshot) {
        target.cards = [...(target.cards || []), { ...snapshot, list_id: toListId }];
      }
      return next;
    });
    try {
      await api.moveCard(cardId, toListId);
    } catch (err) {
      // Revert
      if (snapshot && fromListId) {
        setLists(prev => {
          const next = prev.map(l => ({ ...l, cards: l.cards ? [...l.cards] : [] }));
          const target = next.find(l => l.id === toListId);
          if (target) target.cards = target.cards?.filter(c => c.id !== cardId);
          const origin = next.find(l => l.id === fromListId);
          if (origin) origin.cards = [...(origin.cards || []), snapshot!];
          return next;
        });
      }
      console.error("移动卡片失败", err); toast.error("移动卡片失败");
    }
  };

  return (
    <div className="h-full flex flex-col min-h-0 space-y-4">
      {boards.length > 1 && (
        <div className="flex gap-2 shrink-0">
          {boards.map(b => (
            <button key={b.id} onClick={() => setSelectedBoard(b.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${selectedBoard === b.id ? "bg-primary/15 text-primary border border-primary/30" : "bg-card/30 border border-border/30 text-muted-foreground hover:text-foreground hover:border-border/50"}`}
            >{b.name}</button>
          ))}
        </div>
      )}

      {selectedBoard && lists.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCorners}
          onDragStart={e => { const d = e.active.data.current; if (d?.type === "card") setActiveCard(d.card as KanbanCard); }}
          onDragEnd={e => {
            setActiveCard(null); if (!e.over) return;
            const a = e.active.data.current; const o = e.over.data.current;
            if (a?.type === "card") { const tid = o?.type === "col" ? (o.listId as string) : (o?.card as KanbanCard)?.list_id; if (tid && tid !== (a.card as KanbanCard).list_id) moveCard((a.card as KanbanCard).id, tid); }
          }}
        >
          <div className="flex-1 flex gap-4 overflow-x-auto pb-4 items-start min-h-0">
            {lists.map((l) => (
              <Column key={l.id} list={l} cards={l.cards || []} onAdd={addCard} onDelCard={delCard} />
            ))}
          </div>
          <DragOverlay>{activeCard ? <div className="bg-background border border-primary/30 rounded-xl p-3 rotate-2 shadow-xl text-sm text-foreground">{activeCard.title}</div> : null}</DragOverlay>
        </DndContext>
      )}

      {boards.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-sm text-muted-foreground/30">暂无看板</div>
      )}
    </div>
  );
}

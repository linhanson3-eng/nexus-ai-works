import { useEffect, useState, useCallback, useRef, useMemo } from "react";
import { DndContext, DragOverlay, closestCorners, KeyboardSensor, PointerSensor, TouchSensor, useSensor, useSensors } from "@dnd-kit/core";
import { SortableContext, sortableKeyboardCoordinates, useSortable, verticalListSortingStrategy } from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { GripVertical } from "lucide-react";
import { api, connectWS } from "../lib/api";
import type { KanbanBoard as Board } from "../lib/types";

function Card({ card, onDelete }: { card: any; onDelete: (id: string) => void }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } =
    useSortable({ id: card.id, data: { type: "card", card } });
  return (
    <div ref={setNodeRef} style={{ transition, transform: CSS.Translate.toString(transform) }}
      className={`group bg-surface/80 border border-border/60 rounded-xl px-3 py-2.5 text-sm text-white flex items-center gap-2 cursor-default hover:border-border transition-colors ${isDragging ? "opacity-30" : ""}`}>
      <button {...attributes} {...listeners} className="text-muted/20 hover:text-muted/60 cursor-grab shrink-0"><GripVertical className="w-3 h-3" /></button>
      <span className="flex-1 min-w-0">{card.title}</span>
      <button onClick={() => onDelete(card.id)} className="opacity-0 group-hover:opacity-100 text-muted/40 hover:text-warning shrink-0 text-xs">×</button>
    </div>
  );
}

function Column({ list, cards, onAdd, onDelCard }: { list: any; cards: any[]; onAdd: (listId: string, title: string) => void; onDelCard: (id: string) => void }) {
  const ids = useMemo(() => cards.map(c => c.id), [cards]);
  const [adding, setAdding] = useState(false);
  const [title, setTitle] = useState("");
  const submit = () => { if (title.trim()) { onAdd(list.id, title.trim()); setTitle(""); setAdding(false); } else setAdding(false); };

  return (
    <div className="bg-card/40 border border-border/50 rounded-2xl w-[290px] shrink-0 flex flex-col min-h-[320px]">
      <div className="px-4 py-3 flex items-center justify-between">
        <span className="text-xs font-semibold text-white/70">{list.name}</span>
        <span className="text-[11px] text-muted/30">{cards.length}</span>
      </div>
      <div className="flex-1 px-2 pb-2 space-y-1.5 overflow-auto max-h-[62vh]">
        <SortableContext items={ids} strategy={verticalListSortingStrategy}>
          {cards.map(c => <Card key={c.id} card={c} onDelete={onDelCard} />)}
        </SortableContext>
        {adding ? (
          <div className="bg-surface border border-border/60 rounded-lg p-2 space-y-1.5">
            <input autoFocus value={title} onChange={e => setTitle(e.target.value)} onKeyDown={e => { if (e.key === "Enter") submit(); if (e.key === "Escape") setAdding(false); }} placeholder="卡片标题..." className="w-full bg-transparent border-none outline-none text-xs text-white placeholder:text-muted/40" />
            <div className="flex gap-1.5"><button onClick={submit} className="px-2.5 py-1 text-[10px] bg-accent/10 text-accent rounded-md">添加</button><button onClick={() => setAdding(false)} className="px-2.5 py-1 text-[10px] text-muted/50">取消</button></div>
          </div>
        ) : (
          <button onClick={() => setAdding(true)} className="w-full py-2.5 border border-dashed border-border/30 rounded-lg text-xs text-muted/30 hover:text-muted/60 hover:border-border/50 transition-colors">+ 添加卡片</button>
        )}
      </div>
    </div>
  );
}

export function KanbanBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<string | null>(null);
  const [lists, setLists] = useState<any[]>([]);
  const [activeCard, setActiveCard] = useState<any>(null);
  const wsRef = useRef<(() => void) | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 5 } }),
    useSensor(TouchSensor, { activationConstraint: { delay: 250, tolerance: 5 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  const loadBoard = useCallback(async (id: string) => {
    try { const b = await api.getBoard(id); setLists((b as any).lists || []); } catch {}
  }, []);

  useEffect(() => { api.listBoards().then(setBoards).catch(() => {}); }, []);
  useEffect(() => { if (!selectedBoard && boards.length) setSelectedBoard(boards[0].id); }, [boards]);

  useEffect(() => {
    if (!selectedBoard) return;
    loadBoard(selectedBoard);
    wsRef.current = connectWS(selectedBoard, () => loadBoard(selectedBoard), () => {});
    return () => wsRef.current?.();
  }, [selectedBoard, loadBoard]);

  const addCard = async (listId: string, title: string) => {
    try { await api.createCard(listId, title); if (selectedBoard) loadBoard(selectedBoard); } catch {}
  };
  const delCard = async (id: string) => {
    try { await api.deleteCard(id); if (selectedBoard) loadBoard(selectedBoard); } catch {}
  };
  const moveCard = async (cardId: string, toListId: string) => {
    try { await api.moveCard(cardId, toListId); if (selectedBoard) loadBoard(selectedBoard); } catch {}
  };

  return (
    <div className="h-full flex flex-col min-h-0 space-y-4">
      {boards.length > 1 && (
        <div className="flex gap-2 shrink-0">
          {boards.map(b => (
            <button key={b.id} onClick={() => setSelectedBoard(b.id)}
              className={`px-3 py-1 rounded-lg text-xs font-medium transition-colors ${selectedBoard === b.id ? "bg-accent/15 text-accent border border-accent/30" : "bg-card/30 border border-border/30 text-slate-400 hover:text-white hover:border-border/50"}`}
            >{b.name}</button>
          ))}
        </div>
      )}

      {selectedBoard && lists.length > 0 && (
        <DndContext sensors={sensors} collisionDetection={closestCorners}
          onDragStart={e => { const d = e.active.data.current as any; if (d?.type === "card") setActiveCard(d.card); }}
          onDragEnd={e => {
            setActiveCard(null); if (!e.over) return;
            const a = e.active.data.current as any; const o = e.over.data.current as any;
            if (a?.type === "card") { const tid = o?.type === "col" ? o.listId : o?.card?.list_id; if (tid && tid !== a.card.list_id) moveCard(a.card.id, tid); }
          }}
        >
          <div className="flex-1 flex gap-4 overflow-x-auto pb-4 items-start min-h-0">
            {lists.map((l: any) => (
              <Column key={l.id} list={l} cards={l.cards || []} onAdd={addCard} onDelCard={delCard} />
            ))}
          </div>
          <DragOverlay>{activeCard ? <div className="bg-surface border border-accent/30 rounded-xl p-3 rotate-2 shadow-xl text-sm text-white">{activeCard.title}</div> : null}</DragOverlay>
        </DndContext>
      )}

      {boards.length === 0 && (
        <div className="flex-1 flex items-center justify-center text-sm text-muted/30">暂无看板</div>
      )}
    </div>
  );
}

import { useEffect, useState, useCallback, useRef } from "react";
import { AlertTriangle, Plus, Trash2, RefreshCw, Kanban } from "lucide-react";
import { api, connectWS } from "../lib/api";
import { useToast } from "./Toast";
import { ConfirmDialog } from "./ConfirmDialog";
import type { KanbanBoard as Board, KanbanList as List } from "../lib/types";

export function KanbanBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedBoard, setSelectedBoard] = useState<string | null>(null);
  const [lists, setLists] = useState<List[]>([]);
  const [listsLoading, setListsLoading] = useState(false);
  const [newTitle, setNewTitle] = useState("");
  const [newBoardName, setNewBoardName] = useState("");
  const [deleteTarget, setDeleteTarget] = useState<{ type: "board" | "card"; id: string; label: string } | null>(null);
  const wsCleanupRef = useRef<(() => void) | null>(null);
  const toast = useToast();

  const loadBoards = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.listBoards();
      setBoards(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadBoards(); }, [loadBoards]);

  const loadBoard = useCallback(async (boardId: string) => {
    setListsLoading(true);
    try {
      const board = await api.getBoard(boardId);
      setLists(board.lists || []);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "加载看板失败");
    } finally {
      setListsLoading(false);
    }
  }, [toast]);

  // WebSocket with event-driven reconnect (exponential backoff)
  const reconnectRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const attemptRef = useRef(0);

  useEffect(() => {
    if (!selectedBoard) {
      wsCleanupRef.current?.();
      wsCleanupRef.current = null;
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      attemptRef.current = 0;
      return;
    }

    loadBoard(selectedBoard);

    const scheduleReconnect = () => {
      const delay = Math.min(1000 * 2 ** attemptRef.current, 30000);
      attemptRef.current += 1;
      reconnectRef.current = setTimeout(() => {
        const cleanup = connectWS(
          selectedBoard!,
          () => loadBoard(selectedBoard!),
          scheduleReconnect,
        );
        wsCleanupRef.current = cleanup;
      }, delay);
    };

    const cleanup = connectWS(
      selectedBoard,
      () => loadBoard(selectedBoard),
      scheduleReconnect,
    );
    wsCleanupRef.current = cleanup;

    return () => {
      cleanup();
      if (reconnectRef.current) clearTimeout(reconnectRef.current);
      attemptRef.current = 0;
    };
  }, [selectedBoard, loadBoard]);

  const selectBoard = (id: string) => {
    setSelectedBoard(prev => prev === id ? null : id);
  };

  const addCard = async (listId: string) => {
    if (!newTitle.trim()) return;
    try {
      await api.createCard(listId, newTitle.trim());
      setNewTitle("");
      toast.success("卡片已添加");
      if (selectedBoard) loadBoard(selectedBoard);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "添加失败");
    }
  };

  const moveCard = async (cardId: string, toListId: string) => {
    try {
      await api.moveCard(cardId, toListId);
      if (selectedBoard) loadBoard(selectedBoard);
    } catch (err) {
      toast.error("移动失败");
    }
  };

  const deleteCard = async (cardId: string) => {
    try {
      await api.deleteCard(cardId);
      toast.success("卡片已删除");
      if (selectedBoard) loadBoard(selectedBoard);
    } catch (err) {
      toast.error("删除失败");
    } finally {
      setDeleteTarget(null);
    }
  };

  const createBoard = async () => {
    const name = newBoardName.trim();
    if (!name) return;
    try {
      await api.createBoard(name, name);
      setNewBoardName("");
      toast.success(`看板 "${name}" 已创建`);
      loadBoards();
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "创建失败");
    }
  };

  const deleteBoard = async (id: string) => {
    try {
      await api.deleteBoard(id);
      toast.success("看板已删除");
      if (selectedBoard === id) setSelectedBoard(null);
      loadBoards();
    } catch (err) {
      toast.error("删除失败");
    } finally {
      setDeleteTarget(null);
    }
  };

  const statusClasses = (status: string) =>
    status === "done" ? "text-success" :
    status === "in_progress" ? "text-info" :
    status === "blocked" ? "text-warning" : "text-muted";

  const statusIcon = (status: string) =>
    status === "done" ? "✓" :
    status === "in_progress" ? "·" :
    status === "blocked" ? "!" : "○";

  // ── Loading ──
  if (loading) {
    return (
      <div className="space-y-6">
        <div><div className="h-8 w-24 bg-card rounded animate-pulse" /></div>
        <div className="flex gap-2">{[1,2,3].map(i => <div key={i} className="h-10 w-28 bg-card rounded-xl animate-pulse" />)}</div>
        <div className="grid grid-cols-4 gap-4">{[1,2,3,4].map(i => <div key={i} className="h-48 bg-card rounded-[20px] border border-border animate-pulse" />)}</div>
      </div>
    );
  }

  // ── Error ──
  if (error) {
    return (
      <div className="space-y-6">
        <div><h1 className="text-2xl font-black tracking-tight text-white">看板</h1></div>
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <AlertTriangle className="w-10 h-10 text-warning" />
          <p className="text-white font-semibold">加载失败</p>
          <p className="text-sm text-muted">{error}</p>
          <button onClick={loadBoards} className="inline-flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm hover:bg-accent/20 transition-colors">
            <RefreshCw className="w-3.5 h-3.5" /> 重试
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-3">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">看板</h1>
          <p className="text-muted text-sm mt-1">实时任务跟踪</p>
        </div>
        <div className="flex gap-2">
          <input
            value={newBoardName}
            onChange={e => setNewBoardName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && newBoardName.trim() && createBoard()}
            placeholder="看板名称"
            className="bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 w-36"
          />
          <button
            onClick={createBoard}
            disabled={!newBoardName.trim()}
            className="flex items-center gap-1.5 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors disabled:opacity-30 shrink-0"
          >
            <Plus className="w-4 h-4" /> 新建看板
          </button>
        </div>
      </div>

      {/* Empty state */}
      {boards.length === 0 && (
        <div className="flex flex-col items-center justify-center min-h-[300px] gap-4">
          <div className="w-14 h-14 rounded-2xl bg-card border border-border flex items-center justify-center">
            <Kanban className="w-7 h-7 text-muted" />
          </div>
          <div className="text-center">
            <p className="text-white font-semibold">暂无看板</p>
            <p className="text-sm text-muted mt-1">创建工作区时会自动生成看板，也可以手动创建</p>
          </div>
        </div>
      )}

      {/* Board selector */}
      <div className="flex gap-2 flex-wrap">
        {boards.map(b => (
          <div key={b.id} className="flex items-center">
            <button
              onClick={() => selectBoard(b.id)}
              className={`px-4 py-2 rounded-l-xl text-sm transition-all ${
                selectedBoard === b.id
                  ? "bg-accent/15 text-accent border border-accent/30"
                  : "bg-card border border-border text-slate-400 hover:text-white"
              }`}
            >
              {b.name}
            </button>
            <button
              onClick={(e) => { e.stopPropagation(); setDeleteTarget({ type: "board", id: b.id, label: b.name }); }}
              className="px-2 py-2 bg-card border border-l-0 border-border rounded-r-xl text-muted/30 hover:text-warning transition-colors"
              title="删除看板"
            >
              <Trash2 className="w-3 h-3" />
            </button>
          </div>
        ))}
      </div>

      {/* Lists + Cards */}
      {selectedBoard && (
        <>
          {listsLoading ? (
            <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2">
              {[1,2,3,4].map(i => <div key={i} className="h-48 bg-card rounded-[20px] border border-border animate-pulse" />)}
            </div>
          ) : (
            <div className="grid grid-cols-4 gap-4 max-lg:grid-cols-2 max-md:grid-cols-1">
              {lists.map(list => (
                <div key={list.id} className="bg-card border border-border rounded-[16px] p-4 min-h-[200px]">
                  <div className="flex items-center justify-between mb-3">
                    <span className="text-[11px] uppercase tracking-widest text-muted font-medium">{list.name}</span>
                    <span className="text-xs text-muted">{list.cards?.length || 0}</span>
                  </div>

                  <div className="space-y-2">
                    {list.cards?.map(card => (
                      <div
                        key={card.id}
                        className="group bg-surface border border-border rounded-xl p-3 hover:border-accent/20 transition-all"
                      >
                        <div className="flex items-start justify-between gap-2">
                          <span className="text-sm text-white leading-snug">{card.title}</span>
                          <button
                            onClick={() => setDeleteTarget({ type: "card", id: card.id, label: card.title })}
                            className="opacity-0 group-hover:opacity-100 text-muted hover:text-warning transition-all shrink-0"
                          >
                            <Trash2 className="w-3 h-3" />
                          </button>
                        </div>
                        <div className="flex items-center gap-2 mt-2">
                          <span className={`text-[10px] ${statusClasses(card.task_status)}`}>
                            {statusIcon(card.task_status)} {card.task_status}
                          </span>
                          {card.source_agent && (
                            <span className="text-[10px] text-muted truncate">{card.source_agent}</span>
                          )}
                        </div>
                        {/* Move to other lists */}
                        <div className="mt-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity flex-wrap">
                          {lists.filter(l => l.id !== card.list_id).map(l => (
                            <button
                              key={l.id}
                              onClick={() => moveCard(card.id, l.id)}
                              className="text-[10px] px-2 py-0.5 bg-surface border border-border rounded-md text-muted hover:text-accent hover:border-accent/30 transition-colors"
                            >
                              → {l.name}
                            </button>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>

                  {/* Quick add to this list */}
                  <button
                    onClick={() => addCard(list.id)}
                    className="mt-3 w-full py-2 border border-dashed border-border rounded-xl text-xs text-muted hover:text-white hover:border-white/20 transition-colors"
                  >
                    + 添加
                  </button>
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* Delete confirmation */}
      {deleteTarget && (
        <ConfirmDialog
          title={deleteTarget.type === "board" ? "删除看板" : "删除卡片"}
          message={
            deleteTarget.type === "board"
              ? `确定要删除看板 "${deleteTarget.label}" 吗？其中的所有列表和卡片都会被删除。`
              : `确定要删除卡片 "${deleteTarget.label}" 吗？`
          }
          confirmLabel="删除"
          onConfirm={() => {
            if (deleteTarget.type === "board") deleteBoard(deleteTarget.id);
            else deleteCard(deleteTarget.id);
          }}
          onCancel={() => setDeleteTarget(null)}
        />
      )}
    </div>
  );
}

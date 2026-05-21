import { useEffect, useState, useCallback } from "react";
import { Plus, Trash2 } from "lucide-react";
import { api, connectWS } from "../lib/api";
import type { KanbanBoard as Board, KanbanList as List } from "../lib/types";

export function KanbanBoard() {
  const [boards, setBoards] = useState<Board[]>([]);
  const [selectedBoard, setSelectedBoard] = useState<string | null>(null);
  const [lists, setLists] = useState<List[]>([]);
  const [newTitle, setNewTitle] = useState("");
  const [newBoardName, setNewBoardName] = useState("");
  const [newBoardWorkshop, setNewBoardWorkshop] = useState("");

  const refreshBoards = () => api.listBoards().then(setBoards);

  const refreshBoard = useCallback(async (boardId: string) => {
    const board = await api.getBoard(boardId);
    setLists(board.lists || []);
  }, []);

  useEffect(() => { refreshBoards(); }, []);

  useEffect(() => {
    if (!selectedBoard) return;
    refreshBoard(selectedBoard);
    const unsub = connectWS(selectedBoard, () => refreshBoard(selectedBoard));
    return unsub;
  }, [selectedBoard, refreshBoard]);

  const addCard = async (listId: string) => {
    if (!newTitle) return;
    await api.createCard(listId, newTitle);
    setNewTitle("");
    if (selectedBoard) refreshBoard(selectedBoard);
  };

  const moveCard = async (cardId: string, toListId: string) => {
    await api.moveCard(cardId, toListId);
    if (selectedBoard) refreshBoard(selectedBoard);
  };

  const deleteCard = async (cardId: string) => {
    await api.deleteCard(cardId);
    if (selectedBoard) refreshBoard(selectedBoard);
  };

  const createBoard = async () => {
    if (!newBoardName) return;
    await api.createBoard(newBoardName, newBoardWorkshop || newBoardName);
    setNewBoardName("");
    setNewBoardWorkshop("");
    refreshBoards();
  };

  const statusColor = (status: string) =>
    status === "done" ? "text-success" :
    status === "in_progress" ? "text-info" :
    status === "blocked" ? "text-warning" : "text-muted";

  const statusIcon = (status: string) =>
    status === "done" ? "✓" :
    status === "in_progress" ? "·" :
    status === "blocked" ? "!" : "○";

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-black tracking-tight text-white">看板</h1>
          <p className="text-muted text-sm mt-1">实时任务跟踪</p>
        </div>
        <div className="flex gap-2">
          <input
            value={newBoardName}
            onChange={e => setNewBoardName(e.target.value)}
            onKeyDown={e => e.key === "Enter" && createBoard()}
            placeholder="看板名称"
            className="bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 w-32"
          />
          <input
            value={newBoardWorkshop}
            onChange={e => setNewBoardWorkshop(e.target.value)}
            placeholder="车间"
            className="bg-surface border border-border rounded-xl px-3 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30 w-24"
          />
          <button onClick={createBoard} className="flex items-center gap-2 px-4 py-2 bg-accent/10 text-accent border border-accent/20 rounded-xl text-sm font-medium hover:bg-accent/20 transition-colors">
            <Plus className="w-4 h-4" /> 新建
          </button>
        </div>
      </div>

      {/* Board selector */}
      <div className="flex gap-2 flex-wrap">
        {boards.map(b => (
          <button
            key={b.id}
            onClick={() => setSelectedBoard(selectedBoard === b.id ? null : b.id)}
            className={`px-4 py-2 rounded-xl text-sm transition-all ${
              selectedBoard === b.id
                ? "bg-accent/15 text-accent border border-accent/30"
                : "bg-card border border-border text-slate-400 hover:text-white"
            }`}
          >
            {b.name}
          </button>
        ))}
      </div>

      {/* Lists + Cards */}
      {selectedBoard && (
        <>
          {/* Add card bar */}
          <div className="flex gap-3">
            <input
              value={newTitle}
              onChange={e => setNewTitle(e.target.value)}
              placeholder="新建卡片..."
              className="flex-1 bg-card border border-border rounded-xl px-4 py-2 text-sm text-white placeholder:text-muted focus:outline-none focus:border-accent/30"
            />
          </div>

          <div className="grid grid-cols-4 gap-4">
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
                      className="group bg-surface border border-border rounded-xl p-3 hover:border-accent/20 transition-all cursor-pointer"
                    >
                      <div className="flex items-start justify-between gap-2">
                        <span className="text-sm text-white leading-snug">{card.title}</span>
                        <button
                          onClick={() => deleteCard(card.id)}
                          className="opacity-0 group-hover:opacity-100 text-muted hover:text-warning transition-all shrink-0"
                        >
                          <Trash2 className="w-3 h-3" />
                        </button>
                      </div>
                      <div className="flex items-center gap-2 mt-2">
                        <span className={`text-[10px] ${statusColor(card.task_status)}`}>
                          {statusIcon(card.task_status)} {card.task_status}
                        </span>
                        {card.source_agent && (
                          <span className="text-[10px] text-muted truncate">{card.source_agent}</span>
                        )}
                      </div>
                      {/* Move to other lists */}
                      <div className="mt-2 flex gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
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
        </>
      )}
    </div>
  );
}

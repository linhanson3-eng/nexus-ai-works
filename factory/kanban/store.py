"""Kanban storage engine — SQLite-backed Board/List/Card management.

Follows the same patterns as factory/memory/store.py.
"""

from __future__ import annotations

import logging
import sqlite3
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

INIT_KANBAN_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS kanban_boards (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    workshop_name TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kanban_lists (
    id TEXT PRIMARY KEY,
    board_id TEXT NOT NULL REFERENCES kanban_boards(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    position INTEGER NOT NULL DEFAULT 0,
    color TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS kanban_cards (
    id TEXT PRIMARY KEY,
    list_id TEXT NOT NULL REFERENCES kanban_lists(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    position INTEGER NOT NULL DEFAULT 0,
    labels_json TEXT NOT NULL DEFAULT '[]',
    assignee TEXT NOT NULL DEFAULT '',
    due_date TEXT,
    task_status TEXT NOT NULL DEFAULT 'todo'
        CHECK(task_status IN ('todo','in_progress','done','blocked')),
    source_agent TEXT NOT NULL DEFAULT '',
    source_task_id TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_kanban_cards_status ON kanban_cards(task_status);
CREATE INDEX IF NOT EXISTS idx_kanban_cards_agent ON kanban_cards(source_agent);
CREATE INDEX IF NOT EXISTS idx_kanban_lists_board ON kanban_lists(board_id);
CREATE UNIQUE INDEX IF NOT EXISTS idx_card_task ON kanban_cards(source_agent, source_task_id)
    WHERE source_agent != '' AND source_task_id != '';
"""


def _short_id() -> str:
    return hashlib.sha256(str(time.time_ns()).encode()).hexdigest()[:12]


def _utc_now() -> str:
    from datetime import timezone, datetime

    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class KanbanBoard:
    id: str
    name: str
    workshop_name: str = ""
    description: str = ""
    created_at: str = ""
    updated_at: str = ""


@dataclass(frozen=True)
class KanbanList:
    id: str
    board_id: str
    name: str
    position: int = 0
    color: str = ""


@dataclass(frozen=True)
class KanbanCard:
    id: str
    list_id: str
    title: str
    description: str = ""
    position: int = 0
    labels: tuple[str, ...] = ()
    assignee: str = ""
    due_date: str | None = None
    task_status: str = "todo"
    source_agent: str = ""
    source_task_id: str = ""
    created_at: str = ""
    updated_at: str = ""


class KanbanStore:
    """SQLite-backed kanban store.

    One board per workshop. Uses WAL mode for concurrent reads.
    """

    def __init__(self, db_path: str | Path = "~/.factory/kanban.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_conn()
        return self._conn

    def _ensure_conn(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(INIT_KANBAN_SQL)
        conn.commit()
        self._conn = conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def commit(self) -> None:
        if self._conn:
            self._conn.commit()

    # --- Board CRUD ---

    def create_board(self, name: str, workshop_name: str = "", description: str = "") -> KanbanBoard:
        board_id = _short_id()
        now = _utc_now()
        self.conn.execute(
            "INSERT INTO kanban_boards (id, name, workshop_name, description, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (board_id, name, workshop_name, description, now, now),
        )
        self.commit()
        logger.debug("kanban board created: %s (%s)", name, board_id[:8])
        return KanbanBoard(
            id=board_id, name=name, workshop_name=workshop_name,
            description=description, created_at=now, updated_at=now,
        )

    def get_board(self, board_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM kanban_boards WHERE id = ?", (board_id,)).fetchone()
        return dict(row) if row else None

    def list_boards(self, workshop_name: str = "") -> list[dict]:
        if workshop_name:
            rows = self.conn.execute(
                "SELECT * FROM kanban_boards WHERE workshop_name = ? ORDER BY created_at DESC",
                (workshop_name,),
            ).fetchall()
        else:
            rows = self.conn.execute("SELECT * FROM kanban_boards ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def get_board_by_name(self, name: str, workshop_name: str = "") -> dict | None:
        row = self.conn.execute(
            "SELECT * FROM kanban_boards WHERE name = ? AND workshop_name = ?",
            (name, workshop_name),
        ).fetchone()
        return dict(row) if row else None

    def delete_board(self, board_id: str) -> None:
        self.conn.execute("DELETE FROM kanban_boards WHERE id = ?", (board_id,))
        self.commit()
        logger.debug("kanban board deleted: %s", board_id[:8])

    # --- List CRUD ---

    def create_list(self, board_id: str, name: str, position: int = -1, color: str = "") -> KanbanList:
        if position < 0:
            max_pos = self.conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM kanban_lists WHERE board_id = ?",
                (board_id,),
            ).fetchone()[0]
            position = max_pos + 1
        list_id = _short_id()
        now = _utc_now()
        self.conn.execute(
            "INSERT INTO kanban_lists (id, board_id, name, position, color, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (list_id, board_id, name, position, color, now),
        )
        self.commit()
        return KanbanList(id=list_id, board_id=board_id, name=name, position=position, color=color)

    def get_lists(self, board_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM kanban_lists WHERE board_id = ? ORDER BY position",
            (board_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_list(self, list_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM kanban_lists WHERE id = ?", (list_id,)).fetchone()
        return dict(row) if row else None

    def move_list(self, list_id: str, new_position: int) -> None:
        self.conn.execute(
            "UPDATE kanban_lists SET position = ? WHERE id = ?",
            (new_position, list_id),
        )
        self.commit()

    def delete_list(self, list_id: str) -> None:
        self.conn.execute("DELETE FROM kanban_lists WHERE id = ?", (list_id,))
        self.commit()

    # --- Card CRUD ---

    def create_card(
        self, list_id: str, title: str, description: str = "",
        position: int = -1, labels: list[str] | None = None,
        assignee: str = "", due_date: str | None = None,
        source_agent: str = "", source_task_id: str = "",
        task_status: str = "todo",
    ) -> KanbanCard:
        import json

        if position < 0:
            max_pos = self.conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM kanban_cards WHERE list_id = ?",
                (list_id,),
            ).fetchone()[0]
            position = max_pos + 1
        card_id = _short_id()
        now = _utc_now()
        labels_json = json.dumps(labels or [])
        self.conn.execute(
            "INSERT INTO kanban_cards (id, list_id, title, description, position, labels_json, "
            "assignee, due_date, task_status, source_agent, source_task_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (card_id, list_id, title, description, position, labels_json,
             assignee, due_date, task_status, source_agent, source_task_id, now, now),
        )
        self.commit()
        logger.debug("kanban card created: %s in list %s", title[:40], list_id[:8])
        return KanbanCard(
            id=card_id, list_id=list_id, title=title, description=description,
            position=position, labels=tuple(labels or ()), assignee=assignee,
            due_date=due_date, task_status=task_status,
            source_agent=source_agent, source_task_id=source_task_id,
            created_at=now, updated_at=now,
        )

    def get_card(self, card_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM kanban_cards WHERE id = ?", (card_id,)).fetchone()
        return dict(row) if row else None

    def get_cards(self, list_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM kanban_cards WHERE list_id = ? ORDER BY position",
            (list_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    _ALLOWED_CARD_FIELDS = {
        "title", "description", "position", "labels_json",
        "assignee", "due_date", "task_status", "list_id",
        "source_agent", "source_task_id",
    }

    def update_card(self, card_id: str, **fields) -> None:
        if not fields:
            return
        field_names = []
        args = []
        for f, v in fields.items():
            if f not in self._ALLOWED_CARD_FIELDS:
                raise ValueError(f"Invalid card field: {f}")
            field_names.append(f)
            args.append(v)
        sets = ", ".join(f"{f} = ?" for f in field_names)
        sets += ", updated_at = ?"
        args += [_utc_now(), card_id]
        self.conn.execute(f"UPDATE kanban_cards SET {sets} WHERE id = ?", args)
        self.commit()

    def move_card(self, card_id: str, target_list_id: str, position: int = -1) -> None:
        if position < 0:
            max_pos = self.conn.execute(
                "SELECT COALESCE(MAX(position), -1) FROM kanban_cards WHERE list_id = ?",
                (target_list_id,),
            ).fetchone()[0]
            position = max_pos + 1
        self.update_card(card_id, list_id=target_list_id, position=position)
        logger.debug("kanban card moved: %s → list %s", card_id[:8], target_list_id[:8])

    def delete_card(self, card_id: str) -> None:
        self.conn.execute("DELETE FROM kanban_cards WHERE id = ?", (card_id,))
        self.commit()
        logger.debug("kanban card deleted: %s", card_id[:8])

    # --- Agent Task Sync ---

    def upsert_card_from_task(
        self, agent_name: str, task_id: str, title: str,
        status: str = "todo", list_id: str = "",
    ) -> KanbanCard:
        """Create or update a kanban card from an agent task event.

        If the card doesn't exist and no list_id is given, a default
        board and 'To Do' list are created automatically.
        """
        if existing := self.conn.execute(
            "SELECT * FROM kanban_cards WHERE source_agent = ? AND source_task_id = ?",
            (agent_name, task_id),
        ).fetchone():
            self.update_card(existing["id"], title=title, task_status=status)
            updated = self.conn.execute(
                "SELECT * FROM kanban_cards WHERE id = ?", (existing["id"],)
            ).fetchone()
            return self._row_to_card(dict(updated))

        if not list_id:
            list_id = self._ensure_default_list(agent_name)
        return self.create_card(
            list_id=list_id, title=title, task_status=status,
            source_agent=agent_name, source_task_id=task_id,
        )

    def _ensure_default_list(self, agent_name: str) -> str:
        board = self.conn.execute(
            "SELECT id FROM kanban_boards WHERE workshop_name = ? LIMIT 1",
            (agent_name,),
        ).fetchone()
        if not board:
            board_id = self.create_board(agent_name, workshop_name=agent_name).id
        else:
            board_id = board["id"]
        todo = self.conn.execute(
            "SELECT id FROM kanban_lists WHERE board_id = ? AND name = 'To Do' LIMIT 1",
            (board_id,),
        ).fetchone()
        if todo:
            return todo["id"]
        return self.create_list(board_id, "To Do").id

    def _row_to_card(self, row: dict) -> KanbanCard:
        """Convert a SQLite row dict to a KanbanCard."""
        import json
        labels_raw = row.get("labels_json", "[]")
        try:
            labels = tuple(json.loads(labels_raw) if isinstance(labels_raw, str) else labels_raw)
        except (json.JSONDecodeError, TypeError):
            labels = ()
        fields = {k: v for k, v in row.items() if k != "labels_json"}
        return KanbanCard(labels=labels, **fields)

    def get_cards_by_agent(self, agent_name: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM kanban_cards WHERE source_agent = ? ORDER BY updated_at DESC",
            (agent_name,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_cards_by_status(self, board_id: str, status: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT c.* FROM kanban_cards c "
            "JOIN kanban_lists l ON c.list_id = l.id "
            "WHERE l.board_id = ? AND c.task_status = ? "
            "ORDER BY c.position",
            (board_id, status),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_board_full(self, board_id: str) -> dict:
        """Return the full board with all lists and cards (like 4gaBoards GET /api/boards/:id)."""
        board = self.get_board(board_id)
        if not board:
            return {}
        lists = self.get_lists(board_id)
        if not lists:
            board["lists"] = []
            return board
        # Batch-fetch all cards for all lists in ONE query (fix N+1)
        list_ids = [lst["id"] for lst in lists]
        placeholders = ",".join("?" for _ in list_ids)
        rows = self.conn.execute(
            f"SELECT * FROM kanban_cards WHERE list_id IN ({placeholders}) ORDER BY position",
            list_ids,
        ).fetchall()
        cards_by_list: dict[str, list] = {}
        for row in rows:
            lid = row["list_id"]
            if lid not in cards_by_list:
                cards_by_list[lid] = []
            cards_by_list[lid].append(dict(row))
        for lst in lists:
            lst["cards"] = cards_by_list.get(lst["id"], [])
        board["lists"] = lists
        return board

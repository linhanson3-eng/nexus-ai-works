"""SQLite + FTS5 存储引擎。

参考 OpenHuman memory/tree/types.rs 的数据模型：
- Chunk: 原子记忆单元，SHA256 确定 ID
- Tree: 摘要树容器
- SummaryNode: 封桶后的摘要节点
- Buffer: 未封桶的前沿缓冲
"""

import hashlib
import json
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

INIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS trees (
    id TEXT PRIMARY KEY,
    kind TEXT NOT NULL CHECK(kind IN ('source', 'topic', 'global')),
    scope TEXT NOT NULL,
    root_id TEXT,
    max_level INTEGER NOT NULL DEFAULT 2,
    status TEXT NOT NULL DEFAULT 'active',
    created_at TEXT NOT NULL,
    last_sealed_at TEXT
);

CREATE TABLE IF NOT EXISTS chunks (
    id TEXT PRIMARY KEY,
    tree_id TEXT NOT NULL REFERENCES trees(id),
    content TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    source_kind TEXT NOT NULL CHECK(source_kind IN ('chat', 'tool_output', 'document')),
    source_id TEXT NOT NULL,
    owner TEXT NOT NULL DEFAULT '',
    timestamp TEXT NOT NULL,
    tags TEXT NOT NULL DEFAULT '[]',
    metadata_json TEXT NOT NULL DEFAULT '{}',
    token_count INTEGER NOT NULL DEFAULT 0
);

CREATE VIRTUAL TABLE IF NOT EXISTS chunks_fts USING fts5(
    content, source_id, owner, tags,
    content=chunks,
    content_rowid=rowid
);

CREATE TRIGGER IF NOT EXISTS chunks_ai AFTER INSERT ON chunks BEGIN
    INSERT INTO chunks_fts(rowid, content, source_id, owner, tags)
    VALUES (new.rowid, new.content, new.source_id, new.owner, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS chunks_ad AFTER DELETE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, source_id, owner, tags)
    VALUES ('delete', old.rowid, old.content, old.source_id, old.owner, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS chunks_au AFTER UPDATE ON chunks BEGIN
    INSERT INTO chunks_fts(chunks_fts, rowid, content, source_id, owner, tags)
    VALUES ('delete', old.rowid, old.content, old.source_id, old.owner, old.tags);
    INSERT INTO chunks_fts(rowid, content, source_id, owner, tags)
    VALUES (new.rowid, new.content, new.source_id, new.owner, new.tags);
END;

CREATE TABLE IF NOT EXISTS summary_nodes (
    id TEXT PRIMARY KEY,
    tree_id TEXT NOT NULL REFERENCES trees(id),
    level INTEGER NOT NULL CHECK(level >= 1),
    parent_id TEXT REFERENCES summary_nodes(id),
    content TEXT NOT NULL,
    entities TEXT NOT NULL DEFAULT '[]',
    topics TEXT NOT NULL DEFAULT '[]',
    embedding BLOB,
    child_ids_json TEXT NOT NULL DEFAULT '[]',
    token_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    time_start TEXT,
    time_end TEXT
);

CREATE INDEX IF NOT EXISTS idx_summary_tree_level ON summary_nodes(tree_id, level);

CREATE TABLE IF NOT EXISTS buffers (
    tree_id TEXT NOT NULL REFERENCES trees(id),
    level INTEGER NOT NULL,
    item_ids_json TEXT NOT NULL DEFAULT '[]',
    token_sum INTEGER NOT NULL DEFAULT 0,
    oldest_at TEXT,
    PRIMARY KEY (tree_id, level)
);
"""


class SourceKind(str, Enum):
    CHAT = "chat"
    TOOL_OUTPUT = "tool_output"
    DOCUMENT = "document"


class TreeKind(str, Enum):
    SOURCE = "source"
    TOPIC = "topic"
    GLOBAL = "global"


@dataclass(frozen=True)
class Chunk:
    """原子记忆单元。"""

    id: str
    tree_id: str
    content: str
    content_hash: str
    source_kind: SourceKind
    source_id: str
    owner: str
    timestamp: str
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)
    token_count: int = 0

    @classmethod
    def create(
        cls,
        content: str,
        source_kind: SourceKind,
        source_id: str,
        tree_id: str,
        *,
        owner: str = "",
        tags: tuple[str, ...] = (),
        metadata: dict[str, Any] | None = None,
        timestamp: str | None = None,
    ) -> "Chunk":
        content_hash = hashlib.sha256(content.encode()).hexdigest()[:16]
        chunk_id = f"{source_id}-{content_hash}"
        return cls(
            id=chunk_id,
            tree_id=tree_id,
            content=content,
            content_hash=content_hash,
            source_kind=source_kind,
            source_id=source_id,
            owner=owner,
            timestamp=timestamp or datetime.now(timezone.utc).isoformat(),
            tags=tags,
            metadata=metadata or {},
            token_count=estimate_tokens(content),
        )


@dataclass(frozen=True)
class SummaryNode:
    """封桶后的摘要节点。"""

    id: str
    tree_id: str
    level: int
    content: str
    entities: tuple[str, ...] = ()
    topics: tuple[str, ...] = ()
    parent_id: str | None = None
    child_ids: tuple[str, ...] = ()
    token_count: int = 0
    created_at: str = ""
    time_start: str | None = None
    time_end: str | None = None


@dataclass
class Buffer:
    """未封桶的前沿缓冲。"""

    tree_id: str
    level: int
    item_ids: list[str] = field(default_factory=list)
    token_sum: int = 0
    oldest_at: str | None = None


def estimate_tokens(text: str) -> int:
    """粗略 token 估算：英文 ~1.3 token/词，中文 ~0.5 token/字。"""
    import re

    en_words = len(re.findall(r"[a-zA-Z]+", text))
    cn_chars = len(re.findall(r"[一-鿿]", text))
    other = max(0, len(text) - en_words * 5 - cn_chars)
    return int(en_words * 1.3 + cn_chars * 0.5 + other * 0.25)


class MemoryStore:
    """SQLite + FTS5 记忆存储引擎。"""

    def __init__(self, db_path: str | Path = "~/.factory/memory.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.executescript(INIT_SQL)
        return self._conn

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    # ── Tree CRUD ──

    def create_tree(
        self, tree_id: str, kind: TreeKind, scope: str, max_level: int = 2
    ) -> None:
        self.conn.execute(
            "INSERT INTO trees (id, kind, scope, max_level, created_at) VALUES (?, ?, ?, ?, ?)",
            (tree_id, kind.value, scope, max_level, _utc_now()),
        )
        self.conn.commit()

    def get_tree(self, tree_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM trees WHERE id = ?", (tree_id,)).fetchone()
        return dict(row) if row else None

    # ── Chunk CRUD ──

    def insert_chunk(self, chunk: Chunk) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO chunks (id, tree_id, content, content_hash, source_kind,
               source_id, owner, timestamp, tags, metadata_json, token_count)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                chunk.id,
                chunk.tree_id,
                chunk.content,
                chunk.content_hash,
                chunk.source_kind.value,
                chunk.source_id,
                chunk.owner,
                chunk.timestamp,
                json.dumps(list(chunk.tags)),
                json.dumps(chunk.metadata),
                chunk.token_count,
            ),
        )
        self.conn.commit()
        self._touch_buffer(chunk.tree_id, level=0, item_id=chunk.id, token_count=chunk.token_count)

    def get_chunk(self, chunk_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM chunks WHERE id = ?", (chunk_id,)).fetchone()
        return dict(row) if row else None

    def get_chunks(self, tree_id: str, limit: int = 100) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM chunks WHERE tree_id = ? ORDER BY timestamp DESC LIMIT ?",
            (tree_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    # ── FTS5 搜索 ──

    def search(self, query: str, limit: int = 20) -> list[dict]:
        """FTS5 全文搜索记忆。"""
        try:
            rows = self.conn.execute(
                """SELECT c.* FROM chunks c
                   JOIN chunks_fts f ON c.rowid = f.rowid
                   WHERE chunks_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
            ).fetchall()
        except sqlite3.OperationalError:
            rows = self.conn.execute(
                "SELECT * FROM chunks WHERE content LIKE ? LIMIT ?",
                (f"%{query}%", limit),
            ).fetchall()
        return [dict(r) for r in rows]

    # ── SummaryNode CRUD ──

    def insert_summary(self, node: SummaryNode) -> None:
        self.conn.execute(
            """INSERT INTO summary_nodes
               (id, tree_id, level, parent_id, content, entities, topics,
                child_ids_json, token_count, created_at, time_start, time_end)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                node.id,
                node.tree_id,
                node.level,
                node.parent_id,
                node.content,
                json.dumps(list(node.entities)),
                json.dumps(list(node.topics)),
                json.dumps(list(node.child_ids)),
                node.token_count,
                node.created_at or _utc_now(),
                node.time_start,
                node.time_end,
            ),
        )
        self.conn.commit()

    def get_summaries(self, tree_id: str, level: int | None = None) -> list[dict]:
        if level is not None:
            rows = self.conn.execute(
                "SELECT * FROM summary_nodes WHERE tree_id = ? AND level = ? ORDER BY created_at DESC",
                (tree_id, level),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM summary_nodes WHERE tree_id = ? ORDER BY level, created_at DESC",
                (tree_id,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_summary(self, node_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM summary_nodes WHERE id = ?", (node_id,)).fetchone()
        return dict(row) if row else None

    def get_summary_children(self, node_id: str) -> list[dict]:
        node = self.get_summary(node_id)
        if not node:
            return []
        child_ids = json.loads(node.get("child_ids_json", "[]"))
        if not child_ids:
            return []
        placeholders = ",".join("?" * len(child_ids))
        rows = self.conn.execute(
            f"SELECT * FROM chunks WHERE id IN ({placeholders})",
            child_ids,
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Buffer ──

    def _touch_buffer(self, tree_id: str, level: int, item_id: str, token_count: int = 0) -> None:
        cur = self.conn.execute(
            "SELECT item_ids_json, token_sum, oldest_at FROM buffers WHERE tree_id = ? AND level = ?",
            (tree_id, level),
        ).fetchone()
        now = _utc_now()
        if cur:
            ids = json.loads(cur["item_ids_json"])
            ids.append(item_id)
            self.conn.execute(
                "UPDATE buffers SET item_ids_json = ?, token_sum = token_sum + ?, oldest_at = COALESCE(oldest_at, ?) WHERE tree_id = ? AND level = ?",
                (json.dumps(ids), token_count, now, tree_id, level),
            )
        else:
            self.conn.execute(
                "INSERT INTO buffers (tree_id, level, item_ids_json, token_sum, oldest_at) VALUES (?, ?, ?, ?, ?)",
                (tree_id, level, json.dumps([item_id]), token_count, now),
            )
        self.conn.commit()

    def get_buffer(self, tree_id: str, level: int = 0) -> Buffer:
        row = self.conn.execute(
            "SELECT * FROM buffers WHERE tree_id = ? AND level = ?", (tree_id, level)
        ).fetchone()
        if row:
            return Buffer(
                tree_id=row["tree_id"],
                level=row["level"],
                item_ids=json.loads(row["item_ids_json"]),
                token_sum=row["token_sum"],
                oldest_at=row["oldest_at"],
            )
        return Buffer(tree_id=tree_id, level=level)

    def clear_buffer(self, tree_id: str, level: int) -> None:
        self.conn.execute(
            "UPDATE buffers SET item_ids_json = '[]', token_sum = 0, oldest_at = NULL WHERE tree_id = ? AND level = ?",
            (tree_id, level),
        )
        self.conn.commit()

    def update_buffer_parent(self, tree_id: str, level: int, summary_id: str, token_count: int) -> None:
        """将摘要节点添加到父级 buffer。"""
        self._touch_buffer(tree_id, level + 1, summary_id, token_count)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

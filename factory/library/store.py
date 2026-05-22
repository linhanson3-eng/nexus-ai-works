"""LibraryStore — SQLite-indexed, YAML-backed local template library.

Storage layout:
  ~/.nexus/library/
    library.db          SQLite index + FTS5 search
    workflows/          {name}.yaml
    agents/             {name}.yaml
    roles/              {name}.yaml
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

from config.schema import AgentSpec
from factory.library.models import EntryType, LibraryEntry

LIBRARY_SQL = """
CREATE TABLE IF NOT EXISTS entries (
    id TEXT PRIMARY KEY,
    entry_type TEXT NOT NULL,
    name TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    category TEXT NOT NULL DEFAULT '其他',
    tags TEXT NOT NULL DEFAULT '[]',
    source_workshop TEXT NOT NULL DEFAULT '',
    version TEXT NOT NULL DEFAULT '1.0.0',
    created_at TEXT NOT NULL,
    body_path TEXT NOT NULL,
    UNIQUE(entry_type, name)
);

CREATE VIRTUAL TABLE IF NOT EXISTS entries_fts USING fts5(
    name, description, category, tags, content='entries', content_rowid='rowid'
);

CREATE TRIGGER IF NOT EXISTS entries_ai AFTER INSERT ON entries BEGIN
    INSERT INTO entries_fts(rowid, name, description, category, tags)
    VALUES (new.rowid, new.name, new.description, new.category, new.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_ad AFTER DELETE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, name, description, category, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.category, old.tags);
END;

CREATE TRIGGER IF NOT EXISTS entries_au AFTER UPDATE ON entries BEGIN
    INSERT INTO entries_fts(entries_fts, rowid, name, description, category, tags)
    VALUES ('delete', old.rowid, old.name, old.description, old.category, old.tags);
    INSERT INTO entries_fts(rowid, name, description, category, tags)
    VALUES (new.rowid, new.name, new.description, new.category, new.tags);
END;
"""


class LibraryStore:
    """Manages saved templates with SQLite index + YAML file storage."""

    def __init__(self, root: str | Path = "~/.nexus/library") -> None:
        self._root = Path(root).expanduser().resolve()
        self._db_path = self._root / "library.db"
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        import sqlite3

        self._root.mkdir(parents=True, exist_ok=True)
        for sub in ("workflows", "agents", "roles"):
            (self._root / sub).mkdir(exist_ok=True)
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(LIBRARY_SQL)
        conn.commit()
        conn.close()

    def _conn(self):
        import sqlite3

        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _yaml_path(self, entry_type: EntryType, name: str) -> Path:
        return self._root / f"{entry_type.value}s" / f"{name}.yaml"

    def _row_to_entry(self, row) -> LibraryEntry:
        path = Path(row["body_path"])
        body = path.read_text(encoding="utf-8") if path.exists() else ""
        return LibraryEntry(
            id=row["id"],
            entry_type=EntryType(row["entry_type"]),
            name=row["name"],
            description=row["description"],
            category=row["category"],
            tags=json.loads(row["tags"]),
            source_workshop=row["source_workshop"],
            version=row["version"],
            created_at=row["created_at"],
            body=body,
        )

    # ── Save ──

    def save(
        self,
        entry_type: EntryType,
        name: str,
        body: str,
        description: str = "",
        category: str = "其他",
        tags: list[str] | None = None,
        source_workshop: str = "",
    ) -> LibraryEntry:
        now = datetime.now(timezone.utc).isoformat()
        entry_id = str(uuid.uuid4())[:8]
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        yaml_path = self._yaml_path(entry_type, name)
        yaml_path.write_text(body, encoding="utf-8")

        conn = self._conn()
        try:
            existing = conn.execute(
                "SELECT id FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if existing:
                entry_id = existing["id"]
                conn.execute(
                    "UPDATE entries SET description=?, category=?, tags=?, "
                    "source_workshop=?, version=?, created_at=?, body_path=? "
                    "WHERE id=?",
                    (description, category, tags_json, source_workshop,
                     "1.0.0", now, str(yaml_path), entry_id),
                )
            else:
                conn.execute(
                    "INSERT INTO entries (id, entry_type, name, description, "
                    "category, tags, source_workshop, version, created_at, body_path) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (entry_id, entry_type.value, name, description, category,
                     tags_json, source_workshop, "1.0.0", now, str(yaml_path)),
                )
            conn.commit()
        finally:
            conn.close()
        result = self.get(entry_type, name)
        if result is None:
            raise RuntimeError(f"Failed to read back saved entry: {entry_type}/{name}")
        return result

    # ── List ──

    def list_all(
        self,
        entry_type: EntryType,
        search: str = "",
        category: str = "",
        tag: str = "",
    ) -> list[LibraryEntry]:
        conn = self._conn()
        try:
            if search:
                like_query = f"%{search}%"
                rows = conn.execute(
                    "SELECT * FROM entries WHERE entry_type = ? AND "
                    "(name LIKE ? OR description LIKE ? OR tags LIKE ?) "
                    "ORDER BY created_at DESC",
                    (entry_type.value, like_query, like_query, like_query),
                ).fetchall()
            else:
                where = "WHERE entry_type = ?"
                params: list = [entry_type.value]
                if category:
                    where += " AND category = ?"
                    params.append(category)
                rows = conn.execute(
                    f"SELECT * FROM entries {where} ORDER BY created_at DESC",
                    params,
                ).fetchall()

            entries = [self._row_to_entry(r) for r in rows]
            if tag:
                entries = [e for e in entries if tag in e.tags]
            return entries
        finally:
            conn.close()

    # ── Get ──

    def get(self, entry_type: EntryType, name: str) -> LibraryEntry | None:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT * FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if row is None:
                return None
            return self._row_to_entry(row)
        finally:
            conn.close()

    # ── Delete ──

    def delete(self, entry_type: EntryType, name: str) -> bool:
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT body_path FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            ).fetchone()
            if row is None:
                return False
            path = Path(row["body_path"])
            if path.exists():
                path.unlink()
            conn.execute(
                "DELETE FROM entries WHERE entry_type = ? AND name = ?",
                (entry_type.value, name),
            )
            conn.commit()
            return True
        finally:
            conn.close()

    # ── Install ──

    def install_workflow(self, name: str, workflow_store) -> bool:
        from factory.workflow.models import WorkflowNode, WorkflowTemplate

        entry = self.get(EntryType.WORKFLOW, name)
        if entry is None:
            return False
        data = yaml.safe_load(entry.body)
        nodes = [WorkflowNode.from_dict(n) for n in data.get("nodes", [])]
        tmpl = WorkflowTemplate(
            name=data["name"],
            description=data.get("description", ""),
            workspace=data.get("workspace", ""),
            nodes=nodes,
        )
        workflow_store.save(tmpl)
        return True

    def install_agent(self, name: str, workshop_name: str, org) -> bool:
        from factory.kanban import KanbanStore
        from factory.workshop.manager import WorkshopManager

        entry = self.get(EntryType.AGENT, name)
        if entry is None:
            return False
        data = yaml.safe_load(entry.body)
        spec = AgentSpec(**data) if isinstance(data, dict) else AgentSpec(name=name)
        mgr = WorkshopManager(org, KanbanStore())
        result = mgr.add_agent(workshop_name, spec)
        return result is not None

    def install_role(self, name: str) -> bool:
        entry = self.get(EntryType.ROLE, name)
        if entry is None:
            return False
        dest = Path("config/roles") / f"{name}.yaml"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(entry.body, encoding="utf-8")
        return True


# ── Static helpers for CLI/API ──


def save_workflow_to_library(store: LibraryStore, name: str, org, **meta) -> LibraryEntry:
    tmpl = org.workflow_store.load(name)
    if tmpl is None:
        raise ValueError(f"Workflow not found: {name}")
    body = yaml.dump(tmpl.to_dict(), allow_unicode=True, default_flow_style=False)
    return store.save(
        entry_type=EntryType.WORKFLOW,
        name=name,
        body=body,
        description=meta.get("description", tmpl.description),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
        source_workshop=meta.get("source_workshop", ""),
    )


def save_agent_to_library(
    store: LibraryStore, name: str, workshop_name: str, org, **meta
) -> LibraryEntry:
    from factory.kanban import KanbanStore
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(org, KanbanStore())
    agents = mgr.list_agents(workshop_name)
    if agents is None:
        raise ValueError(f"Workshop not found: {workshop_name}")
    target = next((a for a in agents if a["name"] == name), None)
    if target is None:
        raise ValueError(f"Agent not found: {name} in workshop {workshop_name}")
    body = yaml.dump(target, allow_unicode=True, default_flow_style=False)
    return store.save(
        entry_type=EntryType.AGENT,
        name=name,
        body=body,
        description=meta.get("description", ""),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
        source_workshop=workshop_name,
    )


def save_role_to_library(store: LibraryStore, name: str, role_file: str, **meta) -> LibraryEntry:
    path = Path(role_file)
    if not path.exists():
        raise ValueError(f"Role file not found: {role_file}")
    body = path.read_text(encoding="utf-8")
    return store.save(
        entry_type=EntryType.ROLE,
        name=name,
        body=body,
        description=meta.get("description", ""),
        category=meta.get("category", "其他"),
        tags=meta.get("tags", []),
    )

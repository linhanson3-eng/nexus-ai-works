from __future__ import annotations

"""Audit trail system — immutable event log for security-relevant actions.

Records authentication attempts, permission changes, secret access,
configuration modifications, and data mutations to a structured,
append-only SQLite log for compliance and forensic analysis.
"""


import sqlite3
import logging
from datetime import datetime, timezone
import os
from pathlib import Path

logger = logging.getLogger(__name__)
def _get_audit_db_path() -> Path:
    return Path(os.environ.get("AUDIT_DB_PATH", str(Path("~/.nexus/audit.db").expanduser()))).expanduser()

INIT_AUDIT_SQL = """
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;

CREATE TABLE IF NOT EXISTS audit_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    actor TEXT NOT NULL DEFAULT 'system',
    action TEXT NOT NULL,
    resource TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    ip_address TEXT NOT NULL DEFAULT '',
    user_agent TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL DEFAULT 'success',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_audit_actor_time
    ON audit_events(actor, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_type
    ON audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_resource
    ON audit_events(resource);
"""


class AuditEvent:
    """Audit event type constants."""

    AUTH_LOGIN = "auth.login"
    AUTH_LOGOUT = "auth.logout"
    AUTH_REGISTER = "auth.register"
    AUTH_FAILED = "auth.failed"
    CONFIG_CHANGE = "config.change"
    PERMISSION_CHANGE = "permission.change"
    SECRET_ACCESS = "secret.access"
    SECRET_ROTATE = "secret.rotate"
    DATA_DELETE = "data.delete"
    DATA_EXPORT = "data.export"
    DATA_IMPORT = "data.import"
    WORKFLOW_EXECUTE = "workflow.execute"
    AGENT_SPAWN = "agent.spawn"
    SKILL_INSTALL = "skill.install"
    MCP_INVOKE = "mcp.invoke"


def _get_conn() -> sqlite3.Connection:
    _get_audit_db_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_get_audit_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.executescript(INIT_AUDIT_SQL)
    return conn


def record(
    event_type: str,
    action: str,
    *,
    actor: str = "system",
    resource: str = "",
    detail: str = "",
    ip_address: str = "",
    user_agent: str = "",
    status: str = "success",
) -> None:
    """Record an audit event asynchronously (fire-and-forget)."""
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        conn.execute(
            """INSERT INTO audit_events
               (event_type, actor, action, resource, detail, ip_address, user_agent, status, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_type, actor, action, resource, detail, ip_address, user_agent, status, ts),
        )
        conn.commit()
        conn.close()
    except Exception:
        logger.exception("Audit record failed: event_type=%s action=%s actor=%s", event_type, action, actor)


def query(
    *,
    event_type: str = "",
    actor: str = "",
    resource: str = "",
    limit: int = 100,
    offset: int = 0,
) -> list[dict]:
    """Query audit events with optional filters."""
    conn = _get_conn()
    conn.row_factory = sqlite3.Row

    where: list[str] = []
    params: list[str] = []
    if event_type:
        where.append("event_type = ?")
        params.append(event_type)
    if actor:
        where.append("actor = ?")
        params.append(actor)
    if resource:
        where.append("resource LIKE ?")
        params.append(f"%{resource}%")

    clause = (" WHERE " + " AND ".join(where)) if where else ""
    rows = conn.execute(
        f"SELECT * FROM audit_events{clause} ORDER BY created_at DESC LIMIT ? OFFSET ?",
        params + [limit, offset],
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_recent_events(hours: int = 24, limit: int = 200) -> list[dict]:
    from datetime import timedelta

    conn = _get_conn()
    conn.row_factory = sqlite3.Row
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    rows = conn.execute(
        "SELECT * FROM audit_events WHERE created_at > ? ORDER BY created_at DESC LIMIT ?",
        (cutoff, limit),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def purge_old(days: int = 365) -> int:
    """Delete audit events older than N days. Returns count deleted."""
    from datetime import timedelta

    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_conn()
    cur = conn.execute("DELETE FROM audit_events WHERE created_at < ?", (cutoff_str,))
    conn.commit()
    deleted = cur.rowcount
    conn.close()
    return deleted

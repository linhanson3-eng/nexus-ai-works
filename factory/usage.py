"""Usage tracking — lightweight counters for billing and analytics.

Uses a simple SQLite database at ~/.nexus/usage.db for persistence.
Designed to be zero-cost when not queried.
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime, timezone
import os
from pathlib import Path

logger = logging.getLogger(__name__)

def _get_db_path() -> Path:
    return Path(os.environ.get("USAGE_DB_PATH", str(Path("~/.nexus/usage.db").expanduser()))).expanduser()


def _get_conn() -> sqlite3.Connection:
    _get_db_path().parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_get_db_path()))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute(
        """CREATE TABLE IF NOT EXISTS usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            event_detail TEXT DEFAULT '',
            count INTEGER DEFAULT 1,
            created_at TEXT NOT NULL
        )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_usage_user_time
           ON usage(user_id, created_at)"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_usage_type
           ON usage(event_type)"""
    )
    return conn


def record(user_id: str, event_type: str, event_detail: str = "", count: int = 1) -> None:
    """Record a usage event asynchronously (fire-and-forget)."""
    ts = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        conn.execute(
            "INSERT INTO usage (user_id, event_type, event_detail, count, created_at) VALUES (?,?,?,?,?)",
            (user_id, event_type, event_detail, count, ts),
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.warning("Usage record failed: %s", e)


def get_user_stats(user_id: str, days: int = 30) -> dict[str, int]:
    """Get usage statistics for a user over the given period."""
    import datetime as _dt
    cutoff = _dt.datetime.now(tz=_dt.timezone.utc) - _dt.timedelta(days=days)
    cutoff_str = cutoff.strftime("%Y-%m-%dT%H:%M:%S")
    conn = _get_conn()
    rows = conn.execute(
        "SELECT event_type, SUM(count) FROM usage WHERE user_id=? AND created_at > ? GROUP BY event_type",
        (user_id, cutoff_str),
    ).fetchall()
    conn.close()
    return {row[0]: row[1] for row in rows}


# Event type constants
class UsageEvent:
    WORKFLOW_RUN = "workflow.run"
    WORKFLOW_COMPLETED = "workflow.completed"
    AGENT_CALL = "agent.call"
    TOKEN_CONSUMED = "token.consumed"
    WORKSPACE_CREATED = "workspace.created"
    MARKETPLACE_INSTALL = "marketplace.install"
    MARKETPLACE_BROWSE = "marketplace.browse"
    SKILL_SYNC = "skill.sync"
    MCP_INVOKE = "mcp.invoke"

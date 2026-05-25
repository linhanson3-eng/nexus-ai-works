from __future__ import annotations
"""EvolutionLogger — SQLite-backed evolution audit trail."""


import sqlite3
from pathlib import Path

from factory.evolution.types import EvolutionResult

EVO_LOG_SQL = """
CREATE TABLE IF NOT EXISTS evolution_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL CHECK(action IN ('cycle','approve','reject','rollback')),
    skill_name TEXT NOT NULL DEFAULT '',
    trajectory_id TEXT NOT NULL DEFAULT '',
    detail TEXT NOT NULL DEFAULT '',
    approved_by TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_evo_timestamp ON evolution_log(timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_evo_skill ON evolution_log(skill_name);
"""


class EvolutionLogger:
    """SQLite-backed log of all evolution actions for audit and rollback."""

    def __init__(self, db_path: str | Path = "~/.factory/memory.db"):
        self.db_path = Path(db_path).expanduser().resolve()
        self._conn: sqlite3.Connection | None = None

    @property
    def conn(self) -> sqlite3.Connection:
        if self._conn is None:
            self._ensure_conn()
        return self._conn

    def _ensure_conn(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False, timeout=30)
        conn.row_factory = sqlite3.Row
        conn.executescript(EVO_LOG_SQL)
        conn.commit()
        self._conn = conn

    def _utc_now(self) -> str:
        from datetime import timezone, datetime
        return datetime.now(timezone.utc).isoformat()

    def close(self) -> None:
        if self._conn:
            self._conn.close()
            self._conn = None

    def _insert(self, action: str, skill_name: str = "", trajectory_id: str = "",
                detail: str = "", approved_by: str = "") -> None:
        self.conn.execute(
            "INSERT INTO evolution_log (timestamp, action, skill_name, trajectory_id, detail, approved_by) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (self._utc_now(), action, skill_name, trajectory_id, detail, approved_by),
        )
        self.conn.commit()

    def log_cycle(self, result: EvolutionResult) -> None:
        names = [s.name for s in result.skills_created]
        self._insert(
            action="cycle",
            trajectory_id=result.trajectory_id,
            skill_name=",".join(names),
            detail=result.message,
        )

    def log_approval(self, skill_name: str, approved_by: str = "human") -> None:
        self._insert(action="approve", skill_name=skill_name, approved_by=approved_by,
                     detail=f"Skill '{skill_name}' approved by {approved_by}")

    def log_rejection(self, skill_name: str, rejected_by: str = "human") -> None:
        self._insert(action="reject", skill_name=skill_name, approved_by=rejected_by,
                     detail=f"Skill '{skill_name}' rejected by {rejected_by}")

    def log_rollback(self, skill_name: str, reason: str = "") -> None:
        self._insert(action="rollback", skill_name=skill_name,
                     detail=reason or f"Skill '{skill_name}' rolled back")

    def get_history(self, limit: int = 50, skill_name: str = "") -> list[dict]:
        if skill_name:
            rows = self.conn.execute(
                "SELECT * FROM evolution_log WHERE skill_name = ? ORDER BY timestamp DESC LIMIT ?",
                (skill_name, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT * FROM evolution_log ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(r) for r in rows]

    def get_stats(self) -> dict:
        cycles = self.conn.execute(
            "SELECT COUNT(*) FROM evolution_log WHERE action='cycle'"
        ).fetchone()[0]
        approved = self.conn.execute(
            "SELECT COUNT(*) FROM evolution_log WHERE action='approve'"
        ).fetchone()[0]
        rejected = self.conn.execute(
            "SELECT COUNT(*) FROM evolution_log WHERE action='reject'"
        ).fetchone()[0]
        rolled = self.conn.execute(
            "SELECT COUNT(*) FROM evolution_log WHERE action='rollback'"
        ).fetchone()[0]
        return {"cycles": cycles, "approved": approved, "rejected": rejected, "rollbacks": rolled}

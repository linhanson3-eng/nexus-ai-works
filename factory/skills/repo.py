from __future__ import annotations
"""Skill Repository -- workshop-level skill management."""


from pathlib import Path

from factory.skills.loader import SkillLoader, SkillIndex

SKILL_REPO_SQL = """
CREATE TABLE IF NOT EXISTS skill_installations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_name TEXT NOT NULL,
    workshop_name TEXT NOT NULL DEFAULT '__global__',
    enabled INTEGER NOT NULL DEFAULT 1,
    installed_at TEXT NOT NULL,
    UNIQUE(skill_name, workshop_name)
);
"""


class SkillRepo:
    """Per-workshop skill library. Uses same SQLite DB as kanban."""

    def __init__(
        self,
        db_path: str | Path = "~/.factory/memory.db",
        skills_dir: str | Path = "skills",
    ) -> None:
        self.db_path = Path(db_path).expanduser().resolve()
        self.loader = SkillLoader(skills_dir)
        self._ensure_tables()

    def _ensure_tables(self) -> None:
        import sqlite3

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.executescript(SKILL_REPO_SQL)
        conn.commit()
        conn.close()

    def _conn(self) -> "sqlite3.Connection":
        import sqlite3

        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def install(self, skill_name: str, workshop_name: str = "__global__") -> None:
        """Install a skill to a workshop (or globally)."""
        from datetime import datetime, timezone

        now = datetime.now(timezone.utc).isoformat()
        conn = self._conn()
        try:
            conn.execute(
                "INSERT OR IGNORE INTO skill_installations "
                "(skill_name, workshop_name, enabled, installed_at) "
                "VALUES (?, ?, 1, ?)",
                (skill_name, workshop_name, now),
            )
            conn.commit()
        finally:
            conn.close()

    def uninstall(
        self, skill_name: str, workshop_name: str = "__global__"
    ) -> None:
        """Remove a skill from a workshop."""
        conn = self._conn()
        try:
            conn.execute(
                "DELETE FROM skill_installations "
                "WHERE skill_name = ? AND workshop_name = ?",
                (skill_name, workshop_name),
            )
            conn.commit()
        finally:
            conn.close()

    def list_installed(
        self, workshop_name: str = "__global__"
    ) -> list[SkillIndex]:
        """List skills installed for a workshop."""
        conn = self._conn()
        try:
            rows = conn.execute(
                "SELECT skill_name, enabled FROM skill_installations "
                "WHERE workshop_name = ? ORDER BY skill_name",
                (workshop_name,),
            ).fetchall()
            skills: list[SkillIndex] = []
            for row in rows:
                idx = self.loader.load_skill(row["skill_name"])
                if idx is None:
                    all_idx = self.loader.list_skills(row["skill_name"])
                    if all_idx:
                        skills.append(all_idx[0])
                    continue
                skills.append(
                    SkillIndex(
                        name=idx.name,
                        description=idx.description,
                        triggers=idx.triggers,
                        version=idx.version,
                        path=idx.path,
                    )
                )
            return skills
        finally:
            conn.close()

    def is_installed(
        self, skill_name: str, workshop_name: str = "__global__"
    ) -> bool:
        """Check whether a skill is installed and enabled for a workshop."""
        conn = self._conn()
        try:
            row = conn.execute(
                "SELECT 1 FROM skill_installations "
                "WHERE skill_name = ? AND workshop_name = ? AND enabled = 1",
                (skill_name, workshop_name),
            ).fetchone()
            return row is not None
        finally:
            conn.close()

    def enable(self, skill_name: str, workshop_name: str = "__global__") -> None:
        """Enable a previously disabled skill."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE skill_installations SET enabled = 1 "
                "WHERE skill_name = ? AND workshop_name = ?",
                (skill_name, workshop_name),
            )
            conn.commit()
        finally:
            conn.close()

    def disable(self, skill_name: str, workshop_name: str = "__global__") -> None:
        """Disable a skill without uninstalling."""
        conn = self._conn()
        try:
            conn.execute(
                "UPDATE skill_installations SET enabled = 0 "
                "WHERE skill_name = ? AND workshop_name = ?",
                (skill_name, workshop_name),
            )
            conn.commit()
        finally:
            conn.close()

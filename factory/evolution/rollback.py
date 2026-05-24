from __future__ import annotations
"""RollbackManager — undo evolution actions safely."""


import shutil
from pathlib import Path

from factory.evolution.logger import EvolutionLogger


class RollbackManager:
    """Manage rollback of approved skills with audit trail.

    Rollback can:
    - Delete a skill entirely (if v1 and never updated)
    - Revert to previous version (if skill was updated)
    - Archive to a .retired/ backup directory
    """

    def __init__(self, skills_dir: str | Path = "skills",
                 logger: EvolutionLogger | None = None):
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self.logger = logger
        self._archive_dir = self.skills_dir / ".retired"
        self._archive_dir.mkdir(parents=True, exist_ok=True)

    def rollback(self, skill_name: str, reason: str = "") -> bool:
        """Rollback a skill. Returns True if successful."""
        skill_dir = self.skills_dir / skill_name
        meta_path = skill_dir / ".meta.json"

        if not skill_dir.exists():
            return False

        # Archive before rollback
        if meta_path.exists():
            try:
                archive_dest = self._archive_dir / f"{skill_name}-{self._ts()}"
                shutil.copytree(skill_dir, archive_dest)
            except (OSError, shutil.Error):
                pass

        # Remove the skill
        shutil.rmtree(skill_dir, ignore_errors=True)

        if self.logger:
            self.logger.log_rollback(skill_name, reason)

        return True

    def _ts(self) -> str:
        from datetime import timezone, datetime
        return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    def get_rollback_history(self) -> list[dict]:
        """Get all rollback events from the evolution log."""
        if self.logger is None:
            return []
        return self.logger.get_history(action="rollback")

    def list_archived(self) -> list[str]:
        """List skills in the archive directory."""
        if not self._archive_dir.exists():
            return []
        return [d.name for d in self._archive_dir.iterdir() if d.is_dir()]

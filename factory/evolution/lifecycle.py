"""SkillLifecycle — versioned skill management with deprecation and retirement."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class SkillMeta:
    """Metadata for a skill tracked across its lifecycle."""
    name: str
    version: int = 1
    status: str = "active"  # active | deprecated | retired
    description: str = ""
    created_at: str = ""
    updated_at: str = ""
    deprecated_reason: str = ""
    history: list[dict] = field(default_factory=list)


class SkillLifecycle:
    """Manage skill versions, deprecation, and retirement.

    Tracks lifecycle state in .meta.json files alongside Skill.md files
    in the skills directory.
    """

    def __init__(self, skills_dir: str | Path = "skills"):
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self._meta_cache: dict[str, SkillMeta] = {}
        self._load_all_meta()

    def _meta_path(self, skill_name: str) -> Path:
        return self.skills_dir / skill_name / ".meta.json"

    def _load_meta(self, skill_name: str) -> SkillMeta | None:
        path = self._meta_path(skill_name)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            return SkillMeta(**data)
        except (json.JSONDecodeError, TypeError):
            return None

    def _save_meta(self, meta: SkillMeta) -> None:
        skill_dir = self.skills_dir / meta.name
        skill_dir.mkdir(parents=True, exist_ok=True)
        path = skill_dir / ".meta.json"
        path.write_text(json.dumps({
            "name": meta.name, "version": meta.version, "status": meta.status,
            "description": meta.description, "created_at": meta.created_at,
            "updated_at": meta.updated_at, "deprecated_reason": meta.deprecated_reason,
            "history": meta.history,
        }, indent=2, ensure_ascii=False), encoding="utf-8")
        self._meta_cache[meta.name] = meta

    def _load_all_meta(self) -> None:
        if not self.skills_dir.exists():
            return
        for skill_dir in self.skills_dir.iterdir():
            if skill_dir.is_dir():
                meta = self._load_meta(skill_dir.name)
                if meta:
                    self._meta_cache[meta.name] = meta

    def _utc_now(self) -> str:
        from datetime import timezone, datetime
        return datetime.now(timezone.utc).isoformat()

    def register(self, name: str, description: str = "") -> SkillMeta:
        """Register a newly created skill in the lifecycle tracker."""
        now = self._utc_now()
        meta = SkillMeta(name=name, version=1, status="active",
                         description=description, created_at=now, updated_at=now)
        self._save_meta(meta)
        return meta

    def update(self, name: str, new_description: str = "", new_prompt: str = "") -> SkillMeta | None:
        """Bump version and update a skill."""
        meta = self._load_meta(name)
        if meta is None:
            return None
        meta.version += 1
        meta.updated_at = self._utc_now()
        meta.history.append({"version": meta.version - 1, "updated_at": meta.updated_at,
                             "action": "update"})
        if new_description:
            meta.description = new_description
        if new_prompt:
            skill_file = self.skills_dir / name / "Skill.md"
            if skill_file.exists():
                content = skill_file.read_text(encoding="utf-8")
                parts = content.split("---", 2)
                if len(parts) >= 3:
                    skill_file.write_text(f"{parts[0]}---{parts[1]}---\n\n{new_prompt}", encoding="utf-8")
        self._save_meta(meta)
        return meta

    def deprecate(self, name: str, reason: str = "") -> SkillMeta | None:
        """Mark a skill as deprecated (still usable but not recommended)."""
        meta = self._load_meta(name)
        if meta is None:
            return None
        meta.status = "deprecated"
        meta.deprecated_reason = reason
        meta.updated_at = self._utc_now()
        meta.history.append({"version": meta.version, "updated_at": meta.updated_at,
                             "action": "deprecate", "reason": reason})
        self._save_meta(meta)
        return meta

    def retire(self, name: str, reason: str = "") -> SkillMeta | None:
        """Fully retire a skill (archived, will not be suggested)."""
        meta = self._load_meta(name)
        if meta is None:
            return None
        meta.status = "retired"
        meta.deprecated_reason = reason or meta.deprecated_reason
        meta.updated_at = self._utc_now()
        meta.history.append({"version": meta.version, "updated_at": meta.updated_at,
                             "action": "retire", "reason": reason})
        self._save_meta(meta)
        return meta

    def list_active(self) -> list[SkillMeta]:
        return [m for m in self._meta_cache.values() if m.status == "active"]

    def list_deprecated(self) -> list[SkillMeta]:
        return [m for m in self._meta_cache.values() if m.status == "deprecated"]

    def get(self, name: str) -> SkillMeta | None:
        return self._load_meta(name) or self._meta_cache.get(name)

    def reload(self) -> None:
        self._meta_cache.clear()
        self._load_all_meta()

"""Skill.md progressive disclosure loader.

Compatible with Hermes and Claude Code Skill.md format.
Two-phase loading: list (index only) -> load (full content).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class SkillIndex:
    """Lightweight skill entry for directory listing. Does NOT include body."""

    name: str
    description: str = ""
    triggers: tuple[str, ...] = ()
    version: str = "1.0.0"
    path: str = ""


@dataclass(frozen=True)
class Skill:
    """Full skill with all content loaded."""

    name: str
    description: str = ""
    triggers: tuple[str, ...] = ()
    version: str = "1.0.0"
    path: str = ""
    body: str = ""
    tools: tuple[str, ...] = ()
    models: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_file(cls, path: Path) -> Skill | None:
        """Parse a Skill.md file.

        Front matter -> metadata, body -> body.
        """
        if not path.exists():
            return None
        content = path.read_text(encoding="utf-8")
        front_matter: dict[str, Any] = {}
        body = content
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    front_matter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    pass
                body = parts[2].strip()
        return cls(
            name=front_matter.get("name", path.stem),
            description=front_matter.get("description", ""),
            triggers=tuple(front_matter.get("triggers", [])),
            version=front_matter.get("version", "1.0.0"),
            path=str(path),
            body=body,
            tools=tuple(front_matter.get("tools", [])),
            models=tuple(front_matter.get("models", [])),
            metadata={
                k: v
                for k, v in front_matter.items()
                if k not in (
                    "name",
                    "description",
                    "triggers",
                    "version",
                    "tools",
                    "models",
                )
            },
        )


class SkillLoader:
    """Progressive disclosure skill loader.

    Two-phase loading:
    1. list_skills() -> SkillIndex objects (name + description only)
    2. load_skill(name) -> full Skill with body content
    """

    def __init__(self, skills_dir: str | Path = "skills") -> None:
        self.skills_dir = Path(skills_dir).expanduser().resolve()
        self._index: dict[str, SkillIndex] = {}
        self._loaded: dict[str, Skill] = {}
        self._build_index()

    def _build_index(self) -> None:
        """Scan skills_dir for Skill.md files. Parse only front matter."""
        if not self.skills_dir.exists():
            return
        # Directory-per-skill: skills/<name>/Skill.md
        for skill_dir in self.skills_dir.iterdir():
            if not skill_dir.is_dir():
                continue
            skill_file = skill_dir / "Skill.md"
            if skill_file.exists():
                self._add_index_entry(skill_file, skill_dir.name)
        # Flat layout: skills/<name>.md
        for skill_file in self.skills_dir.glob("*.md"):
            name = skill_file.stem
            if name not in self._index:
                self._add_index_entry(skill_file, name)

    def _add_index_entry(self, path: Path, name: str) -> None:
        """Parse only the front matter to build a SkillIndex."""
        content = path.read_text(encoding="utf-8")
        front_matter: dict[str, Any] = {}
        if content.startswith("---"):
            parts = content.split("---", 2)
            if len(parts) >= 3:
                try:
                    front_matter = yaml.safe_load(parts[1]) or {}
                except yaml.YAMLError:
                    pass
        self._index[name] = SkillIndex(
            name=front_matter.get("name", name),
            description=front_matter.get("description", ""),
            triggers=tuple(front_matter.get("triggers", [])),
            version=front_matter.get("version", "1.0.0"),
            path=str(path),
        )

    def list_skills(self, query: str = "") -> list[SkillIndex]:
        """List available skills.

        If query provided, filter by name/trigger match.
        """
        skills = list(self._index.values())
        if not query:
            return sorted(skills, key=lambda s: s.name)
        q = query.lower()
        return sorted(
            [
                s
                for s in skills
                if q in s.name.lower()
                or any(q in t.lower() for t in s.triggers)
            ],
            key=lambda s: s.name,
        )

    def load_skill(self, name: str) -> Skill | None:
        """Load full skill content. Caches for fast re-access."""
        if name in self._loaded:
            return self._loaded[name]
        idx = self._index.get(name)
        if idx is None:
            return None
        skill = Skill.from_file(Path(idx.path))
        if skill:
            self._loaded[name] = skill
        return skill

    def reload(self) -> None:
        """Clear caches and rebuild index (for hot-reloading)."""
        self._index.clear()
        self._loaded.clear()
        self._build_index()

    def find_by_trigger(self, text: str) -> list[SkillIndex]:
        """Find skills whose triggers match the given text."""
        text_lower = text.lower()
        matched: list[SkillIndex] = []
        for skill in self._index.values():
            for trigger in skill.triggers:
                if trigger.lower() in text_lower:
                    matched.append(skill)
                    break
        return matched

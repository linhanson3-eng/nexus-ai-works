"""Skill Marketplace — discovers SKILL.md files from installed plugins.

Scans standard Claude Code plugin paths for SKILL.md files, parses
YAML frontmatter for name + description, and formats them for
system-prompt injection and Skill-tool execution.

Discovery paths:
1. ~/.claude/plugins/installed_plugins.json → installed plugins
2. <workspace>/.claude/plugins/ → project-level plugins
3. Each plugin's SKILL.md files (recursive)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_INSTALLED_PLUGINS_JSON = Path.home() / ".claude" / "plugins" / "installed_plugins.json"


@dataclass
class MarketplaceSkill:
    """A skill discovered from a SKILL.md file."""

    name: str
    plugin: str
    full_name: str  # "plugin:name"
    description: str
    file_path: str
    source: str = "plugin"  # "plugin" | "workspace"
    _body: str | None = field(default=None, repr=False)

    def get_body(self) -> str:
        """Lazy-load the full markdown body (without frontmatter)."""
        if self._body is None:
            try:
                raw = Path(self.file_path).read_text(encoding="utf-8")
                self._body = _strip_frontmatter(raw)
            except Exception as exc:
                logger.warning("Failed to read skill body %s: %s", self.file_path, exc)
                self._body = ""
        return self._body


class SkillMarketplace:
    """Discovers skills from the Claude Code plugin ecosystem.

    Usage:
        mp = SkillMarketplace()
        mp.discover()
        prompt = mp.format_for_prompt()
    """

    def __init__(self, workspace: str | Path | None = None):
        self._skills: dict[str, MarketplaceSkill] = {}
        self._workspace = Path(workspace) if workspace else None

    def discover(self) -> int:
        """Scan all sources for SKILL.md files. Returns count loaded."""
        self._skills.clear()

        # 1. Installed plugins (~/.claude/plugins/installed_plugins.json)
        for plugin_dir in _installed_plugin_paths():
            self._scan_dir(plugin_dir, "plugin")

        # 2. Workspace-level plugins
        if self._workspace:
            ws_plugins = self._workspace / ".claude" / "plugins"
            if ws_plugins.exists():
                self._scan_dir(ws_plugins, "workspace")

        # 3. Project-local plugins/ directory
        if self._workspace:
            plugins_dir = self._workspace / "plugins"
            if plugins_dir.exists():
                self._scan_dir(plugins_dir, "workspace")

        logger.info(f"SkillMarketplace discovered {len(self._skills)} skills")
        return len(self._skills)

    def _scan_dir(self, root: Path, source: str) -> None:
        """Scan a directory tree for SKILL.md files."""
        for skill_md in root.rglob("SKILL.md"):
            entry = _parse_skill_file(skill_md, source)
            if entry is None:
                continue
            if entry.name in self._skills:
                continue  # first plugin wins
            self._skills[entry.name] = entry

    def get(self, name: str) -> MarketplaceSkill | None:
        """Look up a skill by name (supports 'plugin:name' and plain 'name')."""
        clean = name.strip().lstrip("/")
        if ":" in clean:
            clean = clean.split(":", 1)[1]
        return self._skills.get(clean.lower())

    def list_all(self) -> list[MarketplaceSkill]:
        return list(self._skills.values())

    def format_for_prompt(self) -> str:
        """Format available skills for system prompt injection."""
        if not self._skills:
            return ""

        lines = ["## 可用技能 (Skills)", "",
                  "以下专业技能可通过 Skill 工具调用：", ""]
        for entry in sorted(self._skills.values(), key=lambda e: e.full_name):
            desc = entry.description
            if len(desc) > 200:
                desc = desc[:197] + "..."
            tag = "[项目]" if entry.source == "workspace" else "[插件]"
            lines.append(f"- **{entry.full_name}** {tag}: {desc}")
        return "\n".join(lines)


# ── helpers ────────────────────────────────────────────────────────────

def _installed_plugin_paths() -> list[Path]:
    """Read installed_plugins.json and return install paths."""
    if not _INSTALLED_PLUGINS_JSON.exists():
        return []
    try:
        data = json.loads(_INSTALLED_PLUGINS_JSON.read_text(encoding="utf-8"))
    except Exception as e:
        logger.warning(f"Failed to parse installed_plugins.json: {e}")
        return []

    paths: list[Path] = []
    for entries in data.get("plugins", {}).values():
        if not isinstance(entries, list) or not entries:
            continue
        install_path = entries[0].get("installPath", "")
        if install_path:
            p = Path(install_path)
            if p.exists():
                paths.append(p)
    return paths


def _parse_skill_file(path: Path, source: str = "plugin") -> MarketplaceSkill | None:
    """Parse a SKILL.md file, extracting name + description from frontmatter."""
    try:
        raw = path.read_text(encoding="utf-8")
    except Exception as exc:
        logger.warning("Failed to read skill file %s: %s", path, exc)
        return None

    fm = _parse_frontmatter(raw)
    name = fm.get("name", "")
    description = fm.get("description", "")

    if not name:
        return None
    if "Replace with description" in description:
        return None
    if "template" in name.lower() and "skill" in name.lower():
        return None

    plugin = _infer_plugin_name(path)
    full_name = f"{plugin}:{name}" if plugin else name

    return MarketplaceSkill(
        name=name,
        plugin=plugin,
        full_name=full_name,
        description=description,
        file_path=str(path),
        source=source,
    )


def _parse_frontmatter(text: str) -> dict[str, str]:
    """Extract YAML frontmatter from markdown text using yaml.safe_load."""
    if not text.startswith("---"):
        return {}
    end = text.find("---", 3)
    if end == -1:
        return {}
    fm_text = text[3:end].strip()
    try:
        parsed = yaml.safe_load(fm_text)
        if isinstance(parsed, dict):
            return {str(k): str(v) for k, v in parsed.items() if v is not None}
    except Exception as exc:
        logger.debug("Failed to parse skill frontmatter YAML: %s", exc)
    return {}


def _strip_frontmatter(text: str) -> str:
    """Remove YAML frontmatter from markdown text."""
    if not text.startswith("---"):
        return text
    end = text.find("---", 3)
    if end == -1:
        return text
    return text[end + 3:].strip()


def _infer_plugin_name(skill_md_path: Path) -> str:
    """Infer plugin name from a SKILL.md file path.

    Supports patterns:
      cache/<marketplace>/<plugin>/<version>/skills/<skill>/SKILL.md
      plugins/<plugin>/skills/<skill>/SKILL.md
    """
    parts = list(skill_md_path.parts)

    # Pattern: .../plugins/<plugin>/.../SKILL.md
    try:
        plug_idx = parts.index("plugins")
        if plug_idx + 1 < len(parts):
            return parts[plug_idx + 1]
    except ValueError:
        pass

    # Pattern: cache/<marketplace>/<plugin>/...
    try:
        cache_idx = parts.index("cache")
        if cache_idx + 2 < len(parts):
            name = parts[cache_idx + 2]
            if not name[0].isdigit():
                return name
    except ValueError:
        pass

    return skill_md_path.parent.name

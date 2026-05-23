"""Memory V2 — 文件型语义记忆存储。

与 SQLite Memory Tree 互补：
- Memory Tree (SQLite): 短期操作记忆，chunks/summaries/buffers
- Memory V2 (Files):   长期语义记忆，profiles/events/rules，跨会话持久化

目录结构:
~/.nexus/memory/
├── MEMORY.md              # 索引文件，每次对话注入 system prompt
├── profile/
│   ├── user.md            # 用户画像（合并更新，不堆积）
│   └── project.md         # 项目背景
├── events/
│   └── 2026-05-21.md      # 每日事件（append only）
└── rules/
    └── feedback.md        # 用户纠正过的反馈
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ── Frontmatter helpers ──────────────────────────────────────────────

def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Parse YAML frontmatter from markdown text. Returns (metadata, body)."""
    import yaml

    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        meta = yaml.safe_load(parts[1]) or {}
    except Exception:
        logger = logging.getLogger(__name__)
        logger.warning("Failed to parse memory V2 frontmatter: %s", parts[1][:80] if len(parts) > 1 else "(empty)")
        meta = {}
    body = parts[2]
    return meta, body


def format_frontmatter(metadata: dict[str, Any], body: str) -> str:
    """Write YAML frontmatter + body as markdown."""
    import yaml

    fm = yaml.dump(dict(metadata), allow_unicode=True, sort_keys=False).strip()
    return f"---\n{fm}\n---\n\n{body.strip()}\n"


# ── Entry types ──────────────────────────────────────────────────────

@dataclass
class MemoryEntry:
    """A single entry in MEMORY.md index."""

    name: str
    title: str
    path: str
    description: str
    type: str  # profile | event | rule

    def to_index_line(self) -> str:
        return f"- [{self.title}]({self.path}) — {self.description}"


# ── Store ────────────────────────────────────────────────────────────

class MemoryV2Store:
    """文件型语义记忆存储。

    用法:
        store = MemoryV2Store()
        store.ensure_dirs()

        # 更新用户画像
        store.merge_profile("user", new_facts)

        # 记录每日事件
        store.append_event("完成了架构升级", date_str="2026-05-21")

        # 获取上下文（注入 system prompt）
        ctx = store.get_context_for_prompt()
    """

    def __init__(self, root: str | Path = "~/.nexus/memory"):
        self.root = Path(root).expanduser().resolve()

    def ensure_dirs(self) -> None:
        for sub in ("profile", "events", "rules"):
            (self.root / sub).mkdir(parents=True, exist_ok=True)

    # ── MEMORY.md index ───────────────────────────────────────────

    @property
    def index_path(self) -> Path:
        return self.root / "MEMORY.md"

    def read_index(self) -> list[MemoryEntry]:
        """Parse MEMORY.md into entries."""
        if not self.index_path.exists():
            return []
        text = self.index_path.read_text("utf-8")
        entries: list[MemoryEntry] = []
        for line in text.splitlines():
            entry = _parse_index_line(line)
            if entry:
                entries.append(entry)
        return entries

    def write_index(self, entries: list[MemoryEntry]) -> None:
        self.ensure_dirs()
        lines = ["# Nexus Memory", ""]
        for e in entries:
            lines.append(e.to_index_line())
        lines.append("")
        self.index_path.write_text("\n".join(lines), "utf-8")

    def add_to_index(self, entry: MemoryEntry) -> None:
        entries = self.read_index()
        existing = {e.path for e in entries}
        if entry.path in existing:
            # Replace existing entry
            entries = [e if e.path != entry.path else entry for e in entries]
        else:
            entries.append(entry)
        self.write_index(entries)

    # ── Profile ───────────────────────────────────────────────────

    def read_profile(self, kind: str) -> tuple[dict[str, Any], str]:
        """Read a profile file. Returns (metadata, body)."""
        path = self.root / "profile" / f"{kind}.md"
        if not path.exists():
            return {}, ""
        return parse_frontmatter(path.read_text("utf-8"))

    def write_profile(self, kind: str, content: str, description: str = "") -> None:
        """Write (overwrite) a profile file."""
        self.ensure_dirs()
        path = self.root / "profile" / f"{kind}.md"
        metadata = {
            "name": f"{kind}-profile",
            "description": description or f"{kind.title()} profile",
            "type": "profile",
            "updated": _utc_now(),
        }
        path.write_text(format_frontmatter(metadata, content), "utf-8")

        entry = MemoryEntry(
            name=f"{kind}-profile",
            title=f"{kind.title()} Profile",
            path=f"profile/{kind}.md",
            description=description or f"{kind.title()} profile and preferences",
            type="profile",
        )
        self.add_to_index(entry)

    # ── Events ─────────────────────────────────────────────────────

    def append_event(
        self, content: str, date_str: str | None = None, title: str = ""
    ) -> None:
        """Append a timestamped entry to a daily events file."""
        self.ensure_dirs()
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        path = self.root / "events" / f"{date_str}.md"

        now = datetime.now(timezone.utc).strftime("%H:%M UTC")
        line = f"- **{now}** — {content}\n"

        if path.exists():
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
        else:
            metadata = {
                "name": f"events-{date_str}",
                "description": f"Events for {date_str}",
                "type": "event",
                "date": date_str,
            }
            body = f"# Events — {date_str}\n\n{line}"
            path.write_text(format_frontmatter(metadata, body), "utf-8")

        entry = MemoryEntry(
            name=f"events-{date_str}",
            title=title or date_str,
            path=f"events/{date_str}.md",
            description=f"Events for {date_str}",
            type="event",
        )
        self.add_to_index(entry)

    # ── Rules ──────────────────────────────────────────────────────

    def append_rule(self, content: str) -> None:
        """Append a feedback rule."""
        self.ensure_dirs()
        path = self.root / "rules" / "feedback.md"

        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        line = f"- **{now}** — {content}\n"

        if path.exists():
            with path.open("a", encoding="utf-8") as f:
                f.write(line)
        else:
            metadata = {
                "name": "feedback-rules",
                "description": "User feedback and corrections",
                "type": "rule",
                "updated": _utc_now(),
            }
            body = f"# Feedback Rules\n\n{line}"
            path.write_text(format_frontmatter(metadata, body), "utf-8")

        entry = MemoryEntry(
            name="feedback-rules",
            title="Feedback Rules",
            path="rules/feedback.md",
            description="User corrections and preferences",
            type="rule",
        )
        self.add_to_index(entry)

    # ── Context assembly ───────────────────────────────────────────

    def get_context_for_prompt(self, max_lines: int = 200) -> str:
        """Read MEMORY.md content for system prompt injection.

        Returns the full MEMORY.md text, capped at max_lines.
        """
        if not self.index_path.exists():
            return ""
        lines = self.index_path.read_text("utf-8").splitlines()
        if len(lines) > max_lines:
            lines = lines[:max_lines] + ["", "<!-- truncated -->"]
        return "\n".join(lines)

    def get_full_context(self) -> str:
        """Read all memory files for full context injection."""
        parts: list[str] = []

        # Index first
        if self.index_path.exists():
            parts.append(self.index_path.read_text("utf-8"))

        # Profiles
        for kind in ("user", "project"):
            _, body = self.read_profile(kind)
            if body.strip():
                parts.append(body)

        # Today's events
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        event_path = self.root / "events" / f"{today}.md"
        if event_path.exists():
            _, body = parse_frontmatter(event_path.read_text("utf-8"))
            parts.append(body)

        # Rules
        rules_path = self.root / "rules" / "feedback.md"
        if rules_path.exists():
            _, body = parse_frontmatter(rules_path.read_text("utf-8"))
            parts.append(body)

        return "\n\n---\n\n".join(parts)


# ── Helpers ───────────────────────────────────────────────────────────

def _parse_index_line(line: str) -> MemoryEntry | None:
    """Parse a '- [Title](path.md) — description' line."""
    m = re.match(r"-\s*\[([^]]+)\]\(([^)]+)\)\s*[—\-]\s*(.+)", line)
    if not m:
        return None
    title, path, desc = m.group(1), m.group(2), m.group(3)
    name = Path(path).stem

    if "event" in path.lower() or path.startswith("events/"):
        etype = "event"
    elif "rule" in path.lower() or path.startswith("rules/"):
        etype = "rule"
    else:
        etype = "profile"

    return MemoryEntry(name=name, title=title, path=path, description=desc, type=etype)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()

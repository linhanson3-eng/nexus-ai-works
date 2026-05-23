"""Obsidian 兼容 Markdown 双写导出。

SQLite 写入同时维护可读的 Obsidian vault。
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from factory.memory.store import Chunk, MemoryStore, SummaryNode, SourceKind


class VaultWriter:
    """Obsidian vault 写入器。"""

    def __init__(self, vault_path: str | Path = "~/.factory/vault"):
        self.vault_path = Path(vault_path).expanduser().resolve()
        self.vault_path.mkdir(parents=True, exist_ok=True)

    def write_chunk(self, chunk: Chunk) -> Path:
        src_id = _safe_path_segment(chunk.source_id)
        cid = _safe_path_segment(chunk.id)
        agent_dir = self.vault_path / "agents" / src_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        out_path = agent_dir / "chunks" / f"{cid}.md"
        out_path.parent.mkdir(parents=True, exist_ok=True)

        tags_yml = "\n  - ".join(chunk.tags)
        content = f"""---
id: "{chunk.id}"
source: "{chunk.source_id}"
kind: "{chunk.source_kind.value}"
timestamp: {chunk.timestamp}
tags:
  - {tags_yml}
---

{chunk.content}
"""
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def write_summary(self, node: SummaryNode) -> Path:
        tree_dir = self.vault_path / _tree_dir(node.tree_id)
        tree_dir.mkdir(parents=True, exist_ok=True)
        out_path = tree_dir / f"{node.id}.md"

        wikilinks = "\n".join(f"- [[{cid}]]" for cid in node.child_ids)
        content = f"""---
id: "{node.id}"
level: {node.level}
time_start: {node.time_start or ""}
time_end: {node.time_end or ""}
entities: {json.dumps(list(node.entities))}
---

# L{node.level} 摘要

{node.content}

## 来源
{wikilinks}
"""
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def write_index(self, store: MemoryStore) -> Path:
        out_path = self.vault_path / "INDEX.md"
        trees = store.conn.execute("SELECT * FROM trees").fetchall()
        lines = ["# 工厂记忆索引", ""]
        for t in trees:
            count = store.conn.execute(
                "SELECT COUNT(*) FROM chunks WHERE tree_id = ?", (t["id"],)
            ).fetchone()[0]
            summary_count = store.conn.execute(
                "SELECT COUNT(*) FROM summary_nodes WHERE tree_id = ?", (t["id"],)
            ).fetchone()[0]
            lines.append(f"- **{t['kind']}** `{t['id']}` ({count} chunks, {summary_count} summaries)")
        out_path.write_text("\n".join(lines), encoding="utf-8")
        return out_path


def _tree_dir(tree_id: str) -> str:
    if tree_id.startswith("src-"):
        return f"agents/{_safe_path_segment(tree_id[4:])}"
    if tree_id.startswith("topic-"):
        return f"workshops/{_safe_path_segment(tree_id[6:])}"
    return f"factory/{_safe_path_segment(tree_id)}"


def _safe_path_segment(name: str) -> str:
    return name.replace("/", "_").replace("\\", "_").replace("..", "_")

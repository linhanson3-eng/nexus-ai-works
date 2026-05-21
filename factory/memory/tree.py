"""Memory Tree 核心 — 三级树 + Bucket-Seal 级联压缩。

参考 OpenHuman memory/tree/ 实现：
- MemoryTree: 通用树基类
- SourceTree: Agent 级，会话 + 工具输出
- TopicTree: 车间级，实体/主题聚合
- GlobalTree: 工厂级，daily → weekly → monthly
"""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable

from factory.memory.store import (
    Buffer,
    Chunk,
    MemoryStore,
    SourceKind,
    SummaryNode,
    TreeKind,
    estimate_tokens,
)


@dataclass
class BucketSealConfig:
    """封桶阈值配置。"""

    input_token_budget: int = 50_000
    output_token_budget: int = 5_000
    summary_fanout: int = 10


class BucketSeal:
    """Bucket-Seal 级联压缩引擎。"""

    def __init__(self, store: MemoryStore, config: BucketSealConfig | None = None):
        self.store = store
        self.config = config or BucketSealConfig()

    def should_seal(self, buffer: Buffer) -> bool:
        if buffer.level == 0:
            return (
                buffer.token_sum >= self.config.input_token_budget
                or len(buffer.item_ids) >= self.config.summary_fanout
            )
        return len(buffer.item_ids) >= self.config.summary_fanout

    async def seal_one_level(
        self,
        tree_id: str,
        level: int,
        summariser: Callable[[list[str], str], Any],
    ) -> SummaryNode | None:
        buffer = self.store.get_buffer(tree_id, level)
        if not self.should_seal(buffer):
            return None

        item_ids = list(buffer.item_ids)
        contents: list[str] = []
        time_start: str | None = None
        time_end: str | None = None

        for cid in item_ids:
            chunk = self.store.get_chunk(cid)
            if chunk:
                contents.append(chunk["content"])
                ts = chunk["timestamp"]
                if time_start is None or ts < time_start:
                    time_start = ts
                if time_end is None or ts > time_end:
                    time_end = ts

        if not contents:
            self.store.clear_buffer(tree_id, level)
            return None

        try:
            summary_content = await summariser(contents, tree_id)
        except Exception:
            summary_content = "\n".join(contents[-3:])

        summary_id = f"{tree_id}-L{level}-{_short_hash(summary_content)}"

        node = SummaryNode(
            id=summary_id,
            tree_id=tree_id,
            level=level + 1,
            content=summary_content,
            child_ids=tuple(item_ids),
            token_count=estimate_tokens(summary_content),
            created_at=_utc_now(),
            time_start=time_start,
            time_end=time_end,
        )

        self.store.insert_summary(node)
        self.store.clear_buffer(tree_id, level)
        self.store.update_buffer_parent(tree_id, level, summary_id, node.token_count)
        return node


Summariser = Callable[[list[str], str], Any]


class MemoryTree(ABC):
    """记忆树基类。"""

    kind: TreeKind

    def __init__(self, store: MemoryStore, tree_id: str, scope: str):
        self.store = store
        self.tree_id = tree_id
        self.scope = scope
        self._bucket_seal = BucketSeal(store)
        self._ensure_tree()

    def _ensure_tree(self) -> None:
        existing = self.store.get_tree(self.tree_id)
        if not existing:
            self.store.create_tree(self.tree_id, self.kind, self.scope)

    def append(self, content: str, source_kind: SourceKind, source_id: str, **kwargs: Any) -> Chunk:
        chunk = Chunk.create(
            content=content,
            source_kind=source_kind,
            source_id=source_id,
            tree_id=self.tree_id,
            **kwargs,
        )
        self.store.insert_chunk(chunk)
        return chunk

    async def maybe_seal(self, summariser: Summariser) -> list[SummaryNode]:
        sealed: list[SummaryNode] = []
        tree = self.store.get_tree(self.tree_id)
        if not tree:
            return sealed
        max_level = tree.get("max_level", 2)
        for level in range(max_level):
            node = await self._bucket_seal.seal_one_level(self.tree_id, level, summariser)
            if node:
                sealed.append(node)
        return sealed

    def get_buffer(self, level: int = 0) -> Buffer:
        return self.store.get_buffer(self.tree_id, level)

    def query(self, query: str, limit: int = 20) -> list[dict]:
        return self.store.search(query, limit)

    def get_chunks(self, limit: int = 100) -> list[dict]:
        return self.store.get_chunks(self.tree_id, limit)

    def get_summaries(self, level: int | None = None) -> list[dict]:
        return self.store.get_summaries(self.tree_id, level)

    def drill_down(self, summary_id: str) -> list[dict]:
        return self.store.get_summary_children(summary_id)


class SourceTree(MemoryTree):
    """Agent 级源树 — 会话 JSONL + 工具输出。"""

    kind = TreeKind.SOURCE

    def append_chat(self, role: str, content: str, source_id: str, **kwargs: Any) -> Chunk:
        return self.append(content, SourceKind.CHAT, source_id, **kwargs)

    def append_tool_output(self, tool_name: str, output: str, source_id: str, **kwargs: Any) -> Chunk:
        return self.append(
            f"[{tool_name}]\n{output}",
            SourceKind.TOOL_OUTPUT,
            source_id,
            tags=kwargs.pop("tags", ()) + ("tool", tool_name),
            **kwargs,
        )


class TopicTree(MemoryTree):
    """车间级主题树 — 按实体/主题跨 Agent 聚合。"""

    kind = TreeKind.TOPIC

    def add_to_entity(self, entity: str, content: str, source: str) -> Chunk:
        return self.append(
            content,
            SourceKind.DOCUMENT,
            source_id=source,
            tags=(f"entity/{entity}",),
            metadata={"entity": entity},
        )

    def query_entity(self, entity: str, query: str, limit: int = 20) -> list[dict]:
        return self.store.search(f"{entity} {query}", limit)

    def aggregate_from(self, source_tree: MemoryTree, entity: str = "",
                       limit: int = 50) -> list[Chunk]:
        """Pull chunks from a SourceTree into this TopicTree.

        Copies recent chunks from the source tree, re-tagged under the
        given entity for cross-agent topic aggregation.
        """
        chunks = source_tree.get_chunks(limit)
        results = []
        for c in chunks:
            tags = (f"entity/{entity}",) if entity else ()
            meta = {"entity": entity, "source_tree": source_tree.tree_id}
            chunk = self.append(
                c["content"],
                SourceKind.DOCUMENT,
                source_id=c.get("id", ""),
                tags=tags,
                metadata=meta,
            )
            results.append(chunk)
        return results


class GlobalTree(MemoryTree):
    """工厂级全局树 — daily → weekly → monthly 级联摘要。"""

    kind = TreeKind.GLOBAL

    def get_daily(self, date_str: str | None = None) -> list[dict]:
        date_str = date_str or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        summaries = self.store.get_summaries(self.tree_id, level=1)
        return [s for s in summaries if date_str in (s.get("time_start") or "")]

    def rollup_from(self, topic_tree: MemoryTree, date_str: str = "",
                    limit: int = 50) -> list[dict]:
        """Roll up summaries from a TopicTree into this GlobalTree.

        Pulls level-1 summaries (daily) from the topic tree and copies
        them into the global tree as level-2 (weekly/monthly) entries.
        """
        summaries = topic_tree.store.get_summaries(topic_tree.tree_id, level=1)
        results = []
        for s in summaries[:limit]:
            if date_str and date_str not in (s.get("time_start") or ""):
                continue
            content = s.get("content", "")
            if not content:
                continue
            # Copy into global tree as a document chunk with source reference
            chunk = self.append(
                content,
                SourceKind.DOCUMENT,
                source_id=s.get("id", ""),
                metadata={
                    "source_tree": topic_tree.tree_id,
                    "original_level": str(s.get("level", 1)),
                },
            )
            results.append(chunk)
        return results


async def dummy_summariser(contents: list[str], tree_id: str) -> str:
    """测试用摘要器 — 取前 3 段拼接。"""
    return "\n\n".join(c[:200] for c in contents[:3])


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _short_hash(text: str, length: int = 8) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:length]

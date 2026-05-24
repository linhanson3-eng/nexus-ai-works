from __future__ import annotations

"""Memory — 工厂记忆系统（双层架构）。

Memory Tree (SQLite): 短期操作记忆
    Source Tree (Agent 级) → Topic Tree (工作区级) → Global Tree (工厂级)
    Bucket-Seal 级联压缩，FTS5 全文搜索，Obsidian Markdown 双写。

Memory V2 (文件型): 长期语义记忆
    MEMORY.md 索引 + profile/ + events/ + rules/
    跨会话持久化，人类可读，注入 system prompt。
"""

from factory.memory.store import MemoryStore, SourceKind, TreeKind, Chunk, SummaryNode, Buffer
from factory.memory.tree import (
    MemoryTree,
    SourceTree,
    TopicTree,
    GlobalTree,
    BucketSeal,
    BucketSealConfig,
    dummy_summariser,
)
from factory.memory.vault import VaultWriter
from factory.memory.v2_store import MemoryV2Store, MemoryEntry
from factory.memory.v2_extractor import MemoryV2Extractor, ExtractedFacts

__all__ = [
    # Memory Tree
    "MemoryStore",
    "SourceKind",
    "TreeKind",
    "Chunk",
    "SummaryNode",
    "Buffer",
    "MemoryTree",
    "SourceTree",
    "TopicTree",
    "GlobalTree",
    "BucketSeal",
    "BucketSealConfig",
    "dummy_summariser",
    "VaultWriter",
    # Memory V2
    "MemoryV2Store",
    "MemoryEntry",
    "MemoryV2Extractor",
    "ExtractedFacts",
]

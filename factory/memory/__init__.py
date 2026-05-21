"""Memory Tree — 工厂记忆系统。

Source Tree (Agent 级) → Topic Tree (车间级) → Global Tree (工厂级)
Bucket-Seal 级联压缩，SQLite + FTS5 存储，Obsidian Markdown 双写。
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

__all__ = [
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
]

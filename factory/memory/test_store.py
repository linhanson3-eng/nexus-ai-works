"""Memory Store 存储层测试。"""

import tempfile
from pathlib import Path

import pytest

from factory.memory.store import (
    Buffer,
    Chunk,
    MemoryStore,
    SourceKind,
    SummaryNode,
    TreeKind,
    estimate_tokens,
)


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = MemoryStore(Path(tmp) / "test.db")
        yield s
        s.close()


class TestEstimateTokens:
    def test_english_text(self):
        n = estimate_tokens("hello world")
        assert 2 <= n < 5

    def test_chinese_text(self):
        n = estimate_tokens("你好世界")
        assert 1 < n < 5

    def test_empty_string(self):
        assert estimate_tokens("") == 0


class TestTreeCRUD:
    def test_create_and_get(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        tree = store.get_tree("src-agent-1")
        assert tree["id"] == "src-agent-1"
        assert tree["kind"] == "source"
        assert tree["scope"] == "agent:主力"
        assert tree["status"] == "active"

    def test_get_nonexistent(self, store):
        assert store.get_tree("nonexistent") is None


class TestChunkCRUD:
    def test_insert_and_get(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        chunk = Chunk.create(
            content="修复了登录页面的 XSS 漏洞",
            source_kind=SourceKind.CHAT,
            source_id="agent:主力",
            tree_id="src-agent-1",
            tags=("security", "bug-fix"),
        )
        store.insert_chunk(chunk)
        fetched = store.get_chunk(chunk.id)
        assert fetched is not None
        assert fetched["content"] == chunk.content
        assert fetched["source_kind"] == "chat"

    def test_get_chunks_ordered(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        chunk1 = Chunk.create("first", SourceKind.CHAT, "agent:主力", "src-agent-1")
        chunk2 = Chunk.create("second", SourceKind.TOOL_OUTPUT, "agent:主力", "src-agent-1")
        store.insert_chunk(chunk1)
        store.insert_chunk(chunk2)
        chunks = store.get_chunks("src-agent-1")
        assert len(chunks) >= 2


class TestFTSSearch:
    def test_search_finds_content(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        store.insert_chunk(Chunk.create("XSS vulnerability fixed", SourceKind.CHAT, "agent:主力", "src-agent-1"))
        store.insert_chunk(Chunk.create("added new feature", SourceKind.CHAT, "agent:主力", "src-agent-1"))
        results = store.search("XSS")
        assert len(results) >= 1
        assert "XSS" in results[0]["content"]

    def test_search_no_match(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        store.insert_chunk(Chunk.create("hello world", SourceKind.CHAT, "agent:主力", "src-agent-1"))
        results = store.search("nonexistent_xyz")
        assert len(results) == 0


class TestSummaryCRUD:
    def test_insert_and_get_summary(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        node = SummaryNode(
            id="sum-1",
            tree_id="src-agent-1",
            level=1,
            content="修复了多个安全问题",
            entities=("security",),
            child_ids=("chunk-1", "chunk-2"),
        )
        store.insert_summary(node)
        fetched = store.get_summary("sum-1")
        assert fetched["content"] == node.content

    def test_get_summaries_by_level(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        store.insert_summary(SummaryNode(id="s1", tree_id="src-agent-1", level=1, content="L1 summary"))
        store.insert_summary(SummaryNode(id="s2", tree_id="src-agent-1", level=2, content="L2 summary"))
        l1 = store.get_summaries("src-agent-1", level=1)
        assert len(l1) == 1
        assert l1[0]["content"] == "L1 summary"


class TestBuffer:
    def test_buffer_auto_created_on_insert(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        store.insert_chunk(Chunk.create("test", SourceKind.CHAT, "agent:主力", "src-agent-1"))
        buf = store.get_buffer("src-agent-1", level=0)
        assert len(buf.item_ids) == 1

    def test_clear_buffer(self, store):
        store.create_tree("src-agent-1", TreeKind.SOURCE, "agent:主力")
        store.insert_chunk(Chunk.create("test", SourceKind.CHAT, "agent:主力", "src-agent-1"))
        store.clear_buffer("src-agent-1", 0)
        buf = store.get_buffer("src-agent-1", 0)
        assert len(buf.item_ids) == 0

from __future__ import annotations
"""Unit tests for LibraryStore."""


import tempfile
from pathlib import Path

import pytest

from factory.library.models import EntryType
from factory.library.store import LibraryStore


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = LibraryStore(Path(tmp) / "library")
        yield s


class TestLibraryStoreSave:
    def test_save_and_get_workflow(self, store):
        body = "name: test-wf\ndescription: A test workflow\nnodes: []\n"
        entry = store.save(
            EntryType.WORKFLOW, "test-wf", body,
            description="A test workflow",
            category="代码工具",
            tags=["test", "demo"],
        )
        assert entry is not None
        assert entry.name == "test-wf"
        assert entry.entry_type == EntryType.WORKFLOW
        assert entry.category == "代码工具"
        assert "test" in entry.tags
        assert entry.body == body

    def test_save_overwrites_existing(self, store):
        store.save(EntryType.WORKFLOW, "dup", "v1")
        store.save(EntryType.WORKFLOW, "dup", "v2")
        entry = store.get(EntryType.WORKFLOW, "dup")
        assert entry is not None
        assert entry.body == "v2"

    def test_save_different_types_same_name(self, store):
        store.save(EntryType.WORKFLOW, "shared", "wf body")
        store.save(EntryType.AGENT, "shared", "agent body")
        wf = store.get(EntryType.WORKFLOW, "shared")
        ag = store.get(EntryType.AGENT, "shared")
        assert wf is not None
        assert ag is not None
        assert wf.body == "wf body"
        assert ag.body == "agent body"


class TestLibraryStoreList:
    def test_list_empty(self, store):
        assert store.list_all(EntryType.WORKFLOW) == []

    def test_list_by_type(self, store):
        store.save(EntryType.WORKFLOW, "wf1", "body1")
        store.save(EntryType.WORKFLOW, "wf2", "body2")
        store.save(EntryType.AGENT, "ag1", "body3")
        wfs = store.list_all(EntryType.WORKFLOW)
        assert len(wfs) == 2
        ags = store.list_all(EntryType.AGENT)
        assert len(ags) == 1

    def test_list_search(self, store):
        store.save(EntryType.WORKFLOW, "market-analysis", "body", description="市场分析工具")
        store.save(EntryType.WORKFLOW, "code-review", "body", description="代码审查")
        results = store.list_all(EntryType.WORKFLOW, search="市场")
        assert len(results) == 1
        assert results[0].name == "market-analysis"

    def test_list_category_filter(self, store):
        store.save(EntryType.WORKFLOW, "wf1", "b", category="代码工具")
        store.save(EntryType.WORKFLOW, "wf2", "b", category="市场分析")
        results = store.list_all(EntryType.WORKFLOW, category="市场分析")
        assert len(results) == 1

    def test_list_tag_filter(self, store):
        store.save(EntryType.WORKFLOW, "wf1", "b", tags=["prod"])
        store.save(EntryType.WORKFLOW, "wf2", "b", tags=["dev"])
        results = store.list_all(EntryType.WORKFLOW, tag="prod")
        assert len(results) == 1
        assert results[0].name == "wf1"


class TestLibraryStoreDelete:
    def test_delete_removes_entry(self, store):
        store.save(EntryType.WORKFLOW, "to-delete", "body")
        assert store.delete(EntryType.WORKFLOW, "to-delete") is True
        assert store.get(EntryType.WORKFLOW, "to-delete") is None

    def test_delete_nonexistent(self, store):
        assert store.delete(EntryType.WORKFLOW, "nonexistent") is False

    def test_delete_only_removes_targeted_type(self, store):
        store.save(EntryType.WORKFLOW, "shared", "wf")
        store.save(EntryType.AGENT, "shared", "ag")
        store.delete(EntryType.WORKFLOW, "shared")
        assert store.get(EntryType.WORKFLOW, "shared") is None
        assert store.get(EntryType.AGENT, "shared") is not None


class TestLibraryStoreGet:
    def test_get_nonexistent(self, store):
        assert store.get(EntryType.WORKFLOW, "nonexistent") is None

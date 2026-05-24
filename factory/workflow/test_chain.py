from __future__ import annotations
"""Unit tests for Chain, ChainStep, and ChainStore."""

import tempfile
from pathlib import Path

import pytest

from factory.workflow.chain import Chain, ChainStep, ChainStore


class TestChainStep:
    def test_create_step(self):
        step = ChainStep(workshop="test-ws")
        assert step.workshop == "test-ws"
        assert step.workflow == ""
        assert step.description == ""

    def test_create_step_full(self):
        step = ChainStep(workshop="ws1", workflow="build", description="Build step")
        assert step.workshop == "ws1"
        assert step.workflow == "build"
        assert step.description == "Build step"

    def test_to_dict(self):
        step = ChainStep(workshop="ws1", workflow="build")
        d = step.to_dict()
        assert d["workshop"] == "ws1"
        assert d["workflow"] == "build"

    def test_from_dict(self):
        d = {"workshop": "ws1", "workflow": "build", "description": "desc"}
        step = ChainStep.from_dict(d)
        assert step.workshop == "ws1"
        assert step.workflow == "build"
        assert step.description == "desc"

    def test_from_dict_minimal(self):
        step = ChainStep.from_dict({"workshop": "minimal"})
        assert step.workshop == "minimal"
        assert step.workflow == ""


class TestChain:
    def test_create_empty(self):
        chain = Chain(name="test", description="", steps=[])
        assert chain.name == "test"
        assert chain.steps == []

    def test_create_with_steps(self):
        steps = [ChainStep(workshop="ws1"), ChainStep(workshop="ws2")]
        chain = Chain(name="multi", description="Multi-step", steps=steps)
        assert len(chain.steps) == 2

    def test_to_dict(self):
        steps = [ChainStep(workshop="ws1")]
        chain = Chain(name="c1", description="desc", steps=steps)
        d = chain.to_dict()
        assert d["name"] == "c1"
        assert d["description"] == "desc"
        assert len(d["steps"]) == 1

    def test_from_dict(self):
        d = {
            "name": "imported",
            "description": "Imported chain",
            "steps": [{"workshop": "ws1", "workflow": "build"}],
        }
        chain = Chain.from_dict(d)
        assert chain.name == "imported"
        assert len(chain.steps) == 1
        assert chain.steps[0].workshop == "ws1"


class TestChainStore:
    @pytest.fixture
    def store(self, tmp_path):
        return ChainStore(str(tmp_path))

    def test_save_and_load(self, store):
        chain = Chain(name="test-chain", description="Test", steps=[ChainStep(workshop="ws1")])
        path = store.save(chain)
        assert isinstance(path, Path)

        loaded = store.load("test-chain")
        assert loaded is not None
        assert loaded.name == "test-chain"
        assert len(loaded.steps) == 1

    def test_load_not_found(self, store):
        assert store.load("nonexistent") is None

    def test_delete(self, store):
        chain = Chain(name="del-me", steps=[])
        store.save(chain)
        assert store.delete("del-me") is True
        assert store.load("del-me") is None

    def test_delete_not_found(self, store):
        assert store.delete("nonexistent") is False

    def test_list_all(self, store):
        store.save(Chain(name="c1", steps=[]))
        store.save(Chain(name="c2", steps=[]))
        items = store.list_all()
        assert len(items) >= 2
        names = [i["name"] for i in items]
        assert "c1" in names
        assert "c2" in names

    def test_list_all_empty(self, store):
        assert store.list_all() == []

    def test_overwrite(self, store):
        c1 = Chain(name="overwrite", steps=[ChainStep(workshop="old")])
        store.save(c1)
        c2 = Chain(name="overwrite", steps=[ChainStep(workshop="new")])
        store.save(c2)
        loaded = store.load("overwrite")
        assert loaded.steps[0].workshop == "new"

from __future__ import annotations
"""Unit tests for Chain, ChainStep, and ChainStore."""

from pathlib import Path

import pytest

from factory.workflow.chain import Chain, ChainStep, ChainStore


class TestChainStep:
    def test_create_step(self):
        step = ChainStep(id="step-1", template="build")
        assert step.id == "step-1"
        assert step.template == "build"
        assert step.label == ""
        assert step.enabled is True

    def test_create_step_full(self):
        step = ChainStep(id="step-1", template="build", label="Build", description="Build step")
        assert step.id == "step-1"
        assert step.template == "build"
        assert step.label == "Build"
        assert step.description == "Build step"

    def test_to_dict(self):
        step = ChainStep(id="step-1", template="build")
        d = step.to_dict()
        assert d["id"] == "step-1"
        assert d["template"] == "build"

    def test_from_dict(self):
        d = {"id": "step-1", "template": "build", "label": "Build"}
        step = ChainStep.from_dict(d)
        assert step.id == "step-1"
        assert step.template == "build"
        assert step.label == "Build"

    def test_from_dict_minimal(self):
        step = ChainStep.from_dict({"id": "minimal"})
        assert step.id == "minimal"
        assert step.template == ""


class TestChain:
    def test_create_empty(self):
        chain = Chain(name="test", description="", steps=[])
        assert chain.name == "test"
        assert chain.steps == []

    def test_create_with_steps(self):
        steps = [ChainStep(id="s1"), ChainStep(id="s2")]
        chain = Chain(name="multi", description="Multi-step", steps=steps)
        assert len(chain.steps) == 2

    def test_to_dict(self):
        steps = [ChainStep(id="s1", template="build")]
        chain = Chain(name="c1", description="desc", steps=steps)
        d = chain.to_dict()
        assert d["name"] == "c1"
        assert d["description"] == "desc"
        assert len(d["steps"]) == 1

    def test_from_dict(self):
        d = {
            "name": "imported",
            "description": "Imported chain",
            "steps": [{"id": "s1", "template": "build"}],
        }
        chain = Chain.from_dict(d)
        assert chain.name == "imported"
        assert len(chain.steps) == 1
        assert chain.steps[0].id == "s1"


class TestChainStore:
    @pytest.fixture
    def store(self, tmp_path):
        return ChainStore(str(tmp_path))

    def test_save_and_load(self, store):
        chain = Chain(name="test-chain", description="Test", steps=[ChainStep(id="s1")])
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
        c1 = Chain(name="overwrite", steps=[ChainStep(id="s1", template="old")])
        store.save(c1)
        c2 = Chain(name="overwrite", steps=[ChainStep(id="s1", template="new")])
        store.save(c2)
        loaded = store.load("overwrite")
        assert loaded.steps[0].template == "new"

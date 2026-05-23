"""Workflow engine tests."""

from __future__ import annotations

import pytest

import os
from pathlib import Path

from factory.workflow import (
    WorkflowNode,
    WorkflowTemplate,
    WorkflowRunner,
    WorkflowStore,
    NodeResult,
    NodeStatus,
)


class DummyWorkshop:
    def __init__(self):
        self.agents = {}
        self.workspace = None


@pytest.fixture
def workshop():
    return DummyWorkshop()


@pytest.fixture
def runner(workshop, tmp_path, monkeypatch):
    monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
    return WorkflowRunner(workshop)


# ── Models ────────────────────────────────────────────────────


class TestWorkflowNode:
    def test_minimal(self):
        n = WorkflowNode(id="a", label="Node A", agent_name="test")
        assert n.id == "a"
        assert n.depends_on == []

    def test_serialize_roundtrip(self):
        n = WorkflowNode(id="b", label="B", agent_name="dev", prompt="do it", depends_on=["a"], expected_output="code")
        d = n.to_dict()
        n2 = WorkflowNode.from_dict(d)
        assert n2.id == "b"
        assert n2.agent_name == "dev"
        assert n2.depends_on == ["a"]

    def test_gate_serialize(self):
        n = WorkflowNode(id="r", label="Review", agent_name="qa", gate={"type": "review"})
        d = n.to_dict()
        assert d["gate"] == {"type": "review"}
        n2 = WorkflowNode.from_dict(d)
        assert n2.gate == {"type": "review"}


class TestWorkflowTemplate:
    def test_roundtrip(self):
        nodes = [WorkflowNode(id="a"), WorkflowNode(id="b", depends_on=["a"])]
        t = WorkflowTemplate(name="test", description="desc", workspace="ws-1", nodes=nodes)
        d = t.to_dict()
        t2 = WorkflowTemplate.from_dict(d)
        assert t2.name == "test"
        assert len(t2.nodes) == 2


# ── DAG ───────────────────────────────────────────────────────


class TestDAG:
    def test_linear(self, runner):
        nodes = [WorkflowNode(id="a"), WorkflowNode(id="b"), WorkflowNode(id="c")]
        order = runner._resolve_order(nodes)
        assert set(order) == {"a", "b", "c"}
        assert len(order) == 3

    def test_diamond(self, runner):
        nodes = [
            WorkflowNode(id="x"),
            WorkflowNode(id="y", depends_on=["x"]),
            WorkflowNode(id="z", depends_on=["x"]),
            WorkflowNode(id="w", depends_on=["y", "z"]),
        ]
        order = runner._resolve_order(nodes)
        assert order[0] == "x"
        assert order[3] == "w"

    def test_parallel_ready(self, runner):
        nodes = [
            WorkflowNode(id="a"),
            WorkflowNode(id="b"),
            WorkflowNode(id="c", depends_on=["a", "b"]),
        ]
        order = runner._resolve_order(nodes)
        assert order[0] in ("a", "b")
        assert order[1] in ("a", "b")
        assert order[2] == "c"


# ── Execution ─────────────────────────────────────────────────


class TestExecution:
    @pytest.mark.asyncio
    async def test_single_node(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        tmpl = WorkflowTemplate(name="simple", nodes=[WorkflowNode(id="exec", label="Exec")])
        events: list = []
        async def cb(nid, status, detail):
            events.append((nid, status))

        runner = WorkflowRunner(workshop, on_status=cb)
        result = await runner.run(tmpl, "do it")
        assert result.status == NodeStatus.PASSED
        assert len(events) >= 2
        assert ("exec", "running") in events

    @pytest.mark.asyncio
    async def test_parallel_execution_order(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        """A and B have no dependencies, should execute. C depends on A and B."""
        completed_order: list[str] = []

        async def cb(nid, status, detail):
            if status == "passed":
                completed_order.append(nid)

        nodes = [
            WorkflowNode(id="a", label="A"),
            WorkflowNode(id="b", label="B"),
            WorkflowNode(id="c", label="C", depends_on=["a", "b"]),
        ]
        tmpl = WorkflowTemplate(name="parallel", nodes=nodes)
        runner = WorkflowRunner(workshop, on_status=cb)
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.PASSED
        # A and B finish before C starts
        assert completed_order.index("a") < completed_order.index("c")
        assert completed_order.index("b") < completed_order.index("c")

    @pytest.mark.asyncio
    async def test_mock_outputs(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="a", label="A"),
            WorkflowNode(id="b", label="B", depends_on=["a"]),
        ]
        tmpl = WorkflowTemplate(name="mock", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "a": {"output": "result from a"},
            "b": {"output": "result from b"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.PASSED
        assert result.node_results["a"].output == "result from a"

    @pytest.mark.asyncio
    async def test_mock_failure(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [WorkflowNode(id="bad", label="Bad")]
        tmpl = WorkflowTemplate(name="fail", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "bad": {"status": "failed", "error": "boom"},
        })
        result = await runner.run(tmpl, "test")
        assert result.status == NodeStatus.FAILED
        assert result.node_results["bad"].error == "boom"

    @pytest.mark.asyncio
    async def test_context_passing(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="up", label="Up"),
            WorkflowNode(id="down", label="Down", depends_on=["up"], prompt="use upstream"),
        ]
        tmpl = WorkflowTemplate(name="ctx", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "up": {"output": "upstream data"},
            "down": {"output": "processed"},
        })
        result = await runner.run(tmpl, "test")
        assert "upstream data" in runner._context.get("up", "")

    @pytest.mark.asyncio
    async def test_gate_fail_retries(self, workshop, tmp_path, monkeypatch):
        monkeypatch.setenv("SNAPSHOT_DIR", str(tmp_path / "runs"))
        nodes = [
            WorkflowNode(id="impl", label="Impl"),
            WorkflowNode(id="review", label="Review", depends_on=["impl"], gate={"type": "review"}),
        ]
        tmpl = WorkflowTemplate(name="gate", nodes=nodes)
        runner = WorkflowRunner(workshop, mock_outputs={
            "impl": {"output": "code"},
            "review": {"output": "审查不通过，需要修改"},
        })
        result = await runner.run(tmpl, "test")
        # Should have retried impl at least once
        assert result.node_results["impl"].retries >= 1


# ── Store ─────────────────────────────────────────────────────


class TestStore:
    def test_save_and_load(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        t = WorkflowTemplate(name="test-wf", description="Test", nodes=[WorkflowNode(id="a")])
        store.save(t)
        loaded = store.load("test-wf")
        assert loaded is not None
        assert loaded.name == "test-wf"
        assert len(loaded.nodes) == 1

    def test_list_all(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save(WorkflowTemplate(name="wf1"))
        store.save(WorkflowTemplate(name="wf2"))
        items = store.list_all()
        assert len(items) == 2

    def test_delete(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        store.save(WorkflowTemplate(name="del-me"))
        assert store.delete("del-me") is True
        assert store.load("del-me") is None

    def test_delete_missing(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.delete("nope") is False

    def test_load_missing(self, tmp_path):
        store = WorkflowStore(tmp_path / "workflows")
        assert store.load("nope") is None

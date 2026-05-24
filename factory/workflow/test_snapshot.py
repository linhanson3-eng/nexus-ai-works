from __future__ import annotations
"""Unit tests for RunSnapshot."""


import tempfile
from pathlib import Path

import pytest

from factory.workflow.models import (
    WorkflowNode, WorkflowTemplate,
)
from factory.workflow.snapshot import RunSnapshot


@pytest.fixture
def template():
    return WorkflowTemplate(
        name="test-wf",
        description="A test workflow",
        nodes=[
            WorkflowNode(id="n1", agent_name="agent1"),
            WorkflowNode(id="n2", agent_name="agent2", depends_on=["n1"]),
        ],
    )


class TestRunSnapshot:
    def test_save_and_load(self, template):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        rid = RunSnapshot.new_run_id()
        assert rid.startswith("run-")

        snap.save(
            run_id=rid,
            template=template,
            task="test task",
            node_states={"n1": "passed", "n2": "pending"},
            node_outputs={"n1": "output from n1", "n2": ""},
            node_errors={"n1": "", "n2": ""},
            retries={"n1": 0, "n2": 0},
        )

        data = snap.load(rid)
        assert data is not None
        assert data["template_name"] == "test-wf"
        assert data["task"] == "test task"
        assert data["node_states"] == {"n1": "passed", "n2": "pending"}
        assert data["node_outputs"]["n1"] == "output from n1"

    def test_load_nonexistent(self):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        assert snap.load("nonexistent") is None

    def test_delete(self, template):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        rid = RunSnapshot.new_run_id()
        snap.save(rid, template, "t", {"n1": "passed", "n2": "passed"}, {"n1": "", "n2": ""}, {"n1": "", "n2": ""}, {"n1": 0, "n2": 0})
        assert snap.load(rid) is not None
        snap.delete(rid)
        assert snap.load(rid) is None

    def test_list_incomplete(self, template):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        rid1 = RunSnapshot.new_run_id()
        rid2 = RunSnapshot.new_run_id()

        # Complete run
        snap.save(rid1, template, "t", {"n1": "passed", "n2": "passed"}, {"n1": "", "n2": ""}, {"n1": "", "n2": ""}, {"n1": 0, "n2": 0})
        # Incomplete run
        snap.save(rid2, template, "t", {"n1": "passed", "n2": "failed"}, {"n1": "", "n2": ""}, {"n1": "", "n2": "error"}, {"n1": 0, "n2": 1})

        incomplete = snap.list_incomplete()
        assert len(incomplete) == 1
        assert incomplete[0]["run_id"] == rid2

    def test_list_incomplete_with_pending(self, template):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        rid = RunSnapshot.new_run_id()
        snap.save(rid, template, "t", {"n1": "passed", "n2": "pending"}, {"n1": "", "n2": ""}, {"n1": "", "n2": ""}, {"n1": 0, "n2": 0})
        assert len(snap.list_incomplete()) == 1

    def test_invalid_json_returns_none(self, template):
        snap = RunSnapshot(Path(tempfile.mkdtemp()))
        rid = RunSnapshot.new_run_id()
        snap._path(rid).write_text("not valid json")
        assert snap.load(rid) is None

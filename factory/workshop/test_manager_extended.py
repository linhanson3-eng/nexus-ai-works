from __future__ import annotations

"""Extended tests for WorkshopManager core operations."""

import tempfile
from pathlib import Path

import pytest

from factory.workshop.manager import WorkshopManager
from factory.kanban.store import KanbanStore


class DummyWorkshop:
    def __init__(self, name, workspace):
        self.name = name
        self.workspace = workspace
        self.workflow_name = "default"
        self.agent_count = lambda: 1
        self.spec = type("Spec", (), {"agents": []})()
        self.agents: dict = {}


class DummyOrg:
    def __init__(self):
        self.workshops: list[DummyWorkshop] = []

    def create_one(self, dept_spec):
        # Simulate duplicate check (real OrgEngine does this)
        for ws in self.workshops:
            if ws.name == dept_spec.name:
                return None
        ws = DummyWorkshop(dept_spec.name, dept_spec.workspace)
        self.workshops.append(ws)
        return ws


class TestWorkshopManagerCreate:
    def test_create_minimal_workshop(self, tmp_path):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        ws = mgr.create(name="test-ws", workspace=str(tmp_path), agent_names=[], workflow_name="none")
        assert ws is not None
        assert ws.name == "test-ws"

    def test_create_duplicate_returns_none(self, tmp_path):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        mgr.create(name="dup", workspace=str(tmp_path), agent_names=[], workflow_name="none")
        ws2 = mgr.create(name="dup", workspace=str(tmp_path), agent_names=[], workflow_name="none")
        assert ws2 is None


class TestWorkshopManagerGet:
    def test_get_existing(self, tmp_path):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        mgr.create(name="get-me", workspace=str(tmp_path), agent_names=[], workflow_name="none")
        ws = mgr.get("get-me")
        assert ws is not None
        assert ws.name == "get-me"

    def test_get_missing(self):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        assert mgr.get("no-such") is None


class TestWorkshopManagerList:
    def test_list_all(self, tmp_path):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        mgr.create(name="a", workspace=str(tmp_path / "a"), agent_names=[], workflow_name="none")
        mgr.create(name="b", workspace=str(tmp_path / "b"), agent_names=[], workflow_name="none")
        info = mgr.list_all()
        names = [i.name for i in info]
        assert set(names) == {"a", "b"}

    def test_list_empty(self):
        org = DummyOrg()
        store = KanbanStore(":memory:")
        mgr = WorkshopManager(org, store)
        assert mgr.list_all() == []

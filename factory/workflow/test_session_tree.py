from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from factory.workflow.session_tree import SessionNode, SessionTree, SessionStatus


def make_node(session_id: str, parent_id: str = "", **kwargs) -> SessionNode:
    defaults = {
        "session_id": session_id,
        "parent_id": parent_id,
        "workshop_name": "demo",
        "task": "test task",
    }
    defaults.update(kwargs)
    return SessionNode(**defaults)


class TestSessionNode:
    def test_to_dict_and_back(self):
        node = SessionNode(
            session_id="sess-1",
            parent_id="sess-root",
            workshop_name="demo",
            task="build feature X",
            status=SessionStatus.RUNNING,
            git_sha="abc1234",
        )
        data = node.to_dict()
        restored = SessionNode.from_dict(data)
        assert restored.session_id == "sess-1"
        assert restored.parent_id == "sess-root"
        assert restored.workshop_name == "demo"
        assert restored.git_sha == "abc1234"


class TestSessionTree:
    @pytest.fixture
    def tree(self, tmp_path):
        import os
        os.environ["SESSION_TREE_DIR"] = str(tmp_path)
        return SessionTree(workshop_name="test-workshop")

    def test_add_root(self, tree):
        root = make_node("sess-root")
        tree.add(root)
        assert tree.root is not None
        assert tree.root.session_id == "sess-root"

    def test_spawn_child(self, tree):
        tree.add(make_node("sess-root"))
        child = make_node("sess-child", parent_id="sess-root")
        tree.add(child)
        assert len(tree.children_of("sess-root")) == 1
        assert tree.children_of("sess-root")[0].session_id == "sess-child"

    def test_fork_creates_sibling(self, tree):
        tree.add(make_node("sess-root"))
        tree.add(make_node("sess-a", parent_id="sess-root"))
        tree.fork("sess-a", "sess-b", task="alternative approach")
        siblings = tree.children_of("sess-root")
        assert len(siblings) == 2
        assert {s.session_id for s in siblings} == {"sess-a", "sess-b"}

    def test_get_ancestors(self, tree):
        tree.add(make_node("sess-root"))
        tree.add(make_node("sess-1", parent_id="sess-root"))
        tree.add(make_node("sess-2", parent_id="sess-1"))
        ancestors = tree.ancestors_of("sess-2")
        assert [a.session_id for a in ancestors] == ["sess-root", "sess-1"]

    def test_get_siblings(self, tree):
        tree.add(make_node("sess-root"))
        tree.add(make_node("sess-a", parent_id="sess-root"))
        tree.add(make_node("sess-b", parent_id="sess-root"))
        tree.add(make_node("sess-c", parent_id="sess-root"))
        siblings = tree.siblings_of("sess-b")
        assert {s.session_id for s in siblings} == {"sess-a", "sess-c"}

    def test_btw_creates_child(self, tree):
        tree.add(make_node("sess-root"))
        tree.btw("sess-root", "sess-btw", task="quick question")
        children = tree.children_of("sess-root")
        assert len(children) == 1
        assert children[0].session_type.value == "btw"

    def test_persistence_survives_reload(self, tmp_path):
        import os
        os.environ["SESSION_TREE_DIR"] = str(tmp_path)
        tree1 = SessionTree(workshop_name="persist-test")
        tree1.add(make_node("sess-root"))
        tree1.add(make_node("sess-child", parent_id="sess-root"))

        tree2 = SessionTree(workshop_name="persist-test")
        assert tree2.root is not None
        assert tree2.root.session_id == "sess-root"
        children = tree2.children_of("sess-root")
        assert len(children) == 1
        assert children[0].session_id == "sess-child"

    def test_duplicate_session_id_raises(self, tree):
        tree.add(make_node("sess-root"))
        with pytest.raises(ValueError, match="already exists"):
            tree.add(make_node("sess-root"))

    def test_unknown_parent_raises(self, tree):
        with pytest.raises(ValueError, match="not found"):
            tree.add(make_node("sess-child", parent_id="nonexistent"))

    def test_all_nodes(self, tree):
        tree.add(make_node("sess-root"))
        tree.add(make_node("sess-1", parent_id="sess-root"))
        tree.add(make_node("sess-2", parent_id="sess-root"))
        assert len(tree.all_nodes()) == 3

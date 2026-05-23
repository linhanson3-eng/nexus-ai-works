"""Workshop manager and bridge tests."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import yaml


import conftest
pytestmark = conftest.needs_writable_config
from config.schema import DepartmentSpec, AgentSpec, WorkflowSpec
from factory.org import OrgEngine
from factory.kanban.store import KanbanStore
from factory.workshop.manager import WorkshopManager, WorkshopInfo
from factory.workshop.bridge import WorkshopBridge


@pytest.fixture
def engine():
    """Create a minimal OrgEngine backed by a temporary org.yaml."""
    tmp_warehouse = Path(tempfile.mkdtemp()) / "warehouse"
    config = {
        "departments": [],
        "warehouse": {"path": str(tmp_warehouse)},
        "channels": [],
    }
    with tempfile.NamedTemporaryFile(suffix=".yaml", mode="w", delete=False) as f:
        yaml.dump(config, f)
        config_path = f.name
    org = OrgEngine(config_path)
    yield org
    Path(config_path).unlink(missing_ok=True)
    org.warehouse.root  # no-op access to avoid unused warnings


@pytest.fixture
def manager(engine):
    """Create a WorkshopManager with a temporary KanbanStore."""
    store = KanbanStore(Path(tempfile.mkdtemp()) / "test_kanban.db")
    mgr = WorkshopManager(engine, store)
    yield mgr
    store.close()


@pytest.fixture
def manager_no_kanban(engine):
    """Create a WorkshopManager without a kanban store."""
    return WorkshopManager(engine, None)


# ---------------------------------------------------------------------------
# WorkshopInfo
# ---------------------------------------------------------------------------

class TestWorkshopInfo:
    def test_construct_minimal(self):
        info = WorkshopInfo(
            name="test",
            workspace="/tmp/ws/test",
            agent_count=1,
            agent_names=["test"],
            workflow_name="simple",
        )
        assert info.name == "test"
        assert info.workspace == "/tmp/ws/test"
        assert info.agent_count == 1
        assert info.agent_names == ["test"]
        assert info.workflow_name == "simple"
        assert info.has_kanban is False

    def test_construct_with_kanban(self):
        info = WorkshopInfo(
            name="test",
            workspace="/tmp/ws/test",
            agent_count=2,
            agent_names=["test"],
            workflow_name="simple",
            has_kanban=True,
        )
        assert info.has_kanban is True


# ---------------------------------------------------------------------------
# WorkshopManager — create
# ---------------------------------------------------------------------------

class TestWorkshopCreate:
    def test_create_workshop_default_agent(self, manager):
        ws = manager.create("lab-alpha")
        assert ws.name == "lab-alpha"
        assert ws.agent_count() == 1
        assert "lab-alpha" in list(ws.agents.keys())
        assert str(ws.workspace).endswith("lab-alpha")

    def test_create_workshop_custom_workspace(self, manager):
        ws = manager.create("lab-beta", workspace="/tmp/custom-ws")
        assert ws.name == "lab-beta"
        # Resolve both sides as strings because /tmp is a symlink to /private/tmp on macOS
        assert str(ws.workspace.resolve()) == str(Path("/tmp/custom-ws").resolve())

    def test_create_workshop_multiple_agents(self, manager):
        ws = manager.create("lab-multi", agent_names=["test", "beta"])
        assert ws.agent_count() == 2
        agent_names = list(ws.agents.keys())
        assert "test" in agent_names
        assert "beta" in agent_names

    def test_create_workshop_custom_workflow(self, manager):
        ws = manager.create("lab-wf", workflow_name="research")
        assert ws.workflow_name == "research"

    def test_create_workshop_custom_model(self, manager):
        ws = manager.create("lab-model", model="anthropic/claude-haiku-4-5")
        for spec in ws.agents.values():
            assert spec.model == "anthropic/claude-haiku-4-5"

    def test_create_workshop_auto_creates_kanban(self, manager):
        ws = manager.create("lab-kanban")
        assert manager.kanban_store is not None
        board = manager.kanban_store.get_board_by_name("lab-kanban", "lab-kanban")
        assert board is not None
        assert board["name"] == "lab-kanban"
        # Should have created 4 default lists
        lists = manager.kanban_store.get_lists(board["id"])
        list_names = {lst["name"] for lst in lists}
        assert list_names == {"To Do", "In Progress", "Done", "Blocked"}


# ---------------------------------------------------------------------------
# WorkshopManager — get
# ---------------------------------------------------------------------------

class TestWorkshopGet:
    def test_get_existing_workshop(self, manager):
        manager.create("lab-get")
        ws = manager.get("lab-get")
        assert ws is not None
        assert ws.name == "lab-get"

    def test_get_nonexistent_workshop(self, manager):
        ws = manager.get("nonexistent")
        assert ws is None

    def test_get_after_multiple_creates(self, manager):
        manager.create("lab-a")
        manager.create("lab-b")
        manager.create("lab-c")
        ws = manager.get("lab-b")
        assert ws is not None
        assert ws.name == "lab-b"


# ---------------------------------------------------------------------------
# WorkshopManager — list_all
# ---------------------------------------------------------------------------

class TestWorkshopListAll:
    def test_list_all_empty(self, manager):
        results = manager.list_all()
        assert results == []

    def test_list_all_with_workshops(self, manager):
        manager.create("lab-1")
        manager.create("lab-2", agent_names=["test", "gamma"])
        results = manager.list_all()
        assert len(results) == 2
        names = {r.name for r in results}
        assert names == {"lab-1", "lab-2"}
        # All should be WorkshopInfo instances
        for r in results:
            assert isinstance(r, WorkshopInfo)
        # lab-1 has 1 agent, lab-2 has 2
        counts = {r.name: r.agent_count for r in results}
        assert counts["lab-1"] == 1
        assert counts["lab-2"] == 2

    def test_list_all_shows_agent_names(self, manager):
        manager.create("lab-super", agent_names=["test"])
        results = manager.list_all()
        assert len(results) == 1
        assert results[0].agent_names == ["test"]

    def test_list_all_shows_kanban_flag(self, manager):
        manager.create("lab-flag")
        results = manager.list_all()
        assert len(results) == 1
        assert results[0].has_kanban is True

    def test_list_all_no_kanban_store(self, manager_no_kanban):
        manager_no_kanban.create("lab-nokb")
        results = manager_no_kanban.list_all()
        assert len(results) == 1
        assert results[0].has_kanban is False


# ---------------------------------------------------------------------------
# WorkshopManager — delete
# ---------------------------------------------------------------------------

class TestWorkshopDelete:
    def test_delete_workshop(self, manager):
        manager.create("lab-del")
        assert manager.get("lab-del") is not None
        deleted = manager.delete("lab-del")
        assert deleted is True
        assert manager.get("lab-del") is None

    def test_delete_nonexistent_workshop(self, manager):
        deleted = manager.delete("nonexistent")
        assert deleted is False

    def test_delete_removes_from_list(self, manager):
        manager.create("lab-x")
        manager.create("lab-y")
        manager.create("lab-z")
        manager.delete("lab-y")
        results = manager.list_all()
        names = {r.name for r in results}
        assert names == {"lab-x", "lab-z"}

    def test_delete_cleans_up_kanban(self, manager):
        manager.create("lab-kbdel")
        board = manager.kanban_store.get_board_by_name("lab-kbdel", "lab-kbdel")
        assert board is not None
        board_id = board["id"]
        manager.delete("lab-kbdel")
        # Board should be gone
        assert manager.kanban_store.get_board(board_id) is None


# ---------------------------------------------------------------------------
# WorkshopManager — status
# ---------------------------------------------------------------------------

class TestWorkshopStatus:
    def test_status_returns_workshop_info(self, manager):
        manager.create("lab-status")
        info = manager.status("lab-status")
        assert info is not None
        assert info["name"] == "lab-status"
        assert "workspace" in info
        assert "agents" in info
        assert "workflow" in info

    def test_status_nonexistent_workshop(self, manager):
        info = manager.status("nonexistent")
        assert info is None

    def test_status_includes_kanban_info(self, manager):
        manager.create("lab-status-kb")
        info = manager.status("lab-status-kb")
        assert info is not None
        assert "kanban_board_id" in info
        assert "kanban_stats" in info
        assert info["kanban_stats"]["To Do"] == 0
        assert info["kanban_stats"]["In Progress"] == 0
        assert info["kanban_stats"]["Done"] == 0
        assert info["kanban_stats"]["Blocked"] == 0

    def test_status_without_kanban_store(self, manager_no_kanban):
        manager_no_kanban.create("lab-status-nokb")
        info = manager_no_kanban.status("lab-status-nokb")
        assert info is not None
        assert "kanban_board_id" not in info
        assert "kanban_stats" not in info


# ===========================================================================
# WorkshopBridge
# ===========================================================================


@pytest.fixture
def bridge():
    """Create a WorkshopBridge backed by a temporary warehouse."""
    from factory.warehouse import Warehouse

    wh_root = Path(tempfile.mkdtemp()) / "warehouse"
    wh = Warehouse(wh_root)
    return WorkshopBridge(wh)


@pytest.fixture
def bridge_with_products(bridge):
    """Create a bridge with pre-populated workshop products.

    Note: Warehouse.read_dept() and .index() only glob *.md files,
    so all test products must use .md extension.
    """
    bridge.warehouse.write("research-lab", "report.md", "# Research Report\n\nFindings here.")
    bridge.warehouse.write("research-lab", "data.md", "## Data\n\ncol1,col2\n1,2")
    bridge.warehouse.write("design-lab", "mockup.md", "# Mockup\n\nWireframe.")
    return bridge


class TestWorkshopBridgeShare:
    def test_share_product_creates_link(self, bridge_with_products):
        link = bridge_with_products.share_product(
            from_workshop="research-lab",
            filename="report.md",
            to_workshop="design-lab",
        )
        assert link is not None
        assert "report.md" in link

    def test_share_product_with_custom_name(self, bridge_with_products):
        link = bridge_with_products.share_product(
            from_workshop="research-lab",
            filename="report.md",
            to_workshop="design-lab",
            to_filename="shared-research.md",
        )
        assert "shared-research.md" in link


class TestWorkshopBridgeRead:
    def test_read_peer_product(self, bridge_with_products):
        content = bridge_with_products.read_peer_product("research-lab", "report.md")
        assert content.startswith("# Research Report")

    def test_read_peer_product_file_not_found(self, bridge_with_products):
        with pytest.raises(FileNotFoundError):
            bridge_with_products.read_peer_product("research-lab", "nonexistent.md")


class TestWorkshopBridgeList:
    def test_list_peer_products(self, bridge_with_products):
        files = bridge_with_products.list_peer_products("research-lab")
        assert len(files) == 2
        assert "report.md" in files
        assert "data.md" in files

    def test_list_peer_products_empty(self, bridge):
        files = bridge.list_peer_products("empty-lab")
        assert files == []


class TestWorkshopBridgeIndex:
    def test_list_all_departments(self, bridge_with_products):
        index = bridge_with_products.list_all_departments()
        assert "research-lab" in index
        assert "design-lab" in index
        assert len(index["research-lab"]) == 2
        assert len(index["design-lab"]) == 1

    def test_list_all_departments_empty(self, bridge):
        index = bridge.list_all_departments()
        assert index == {}


class TestWorkshopBridgeMemory:
    def test_share_memory_no_store(self, bridge):
        """share_memory should be a no-op when memory_store is None."""
        # Should not raise
        bridge.share_memory(
            from_tree_id="tree-1",
            content="shared insight",
            to_tree_id="tree-2",
        )

    def test_share_memory_with_store(self, bridge):
        """share_memory should accept a memory_store and not raise."""
        from factory.memory.store import MemoryStore

        store = MemoryStore(Path(tempfile.mkdtemp()) / "test_memory.db")
        bridge2 = WorkshopBridge(bridge.warehouse, store)
        try:
            bridge2.share_memory(
                from_tree_id="tree-1",
                content="shared insight",
                to_tree_id="tree-2",
            )
        finally:
            store.close()


class TestWorkshopBridgeWithMemory:
    @pytest.fixture
    def bridge_with_memory(self):
        from factory.memory.store import MemoryStore
        from factory.warehouse import Warehouse

        wh_root = Path(tempfile.mkdtemp()) / "warehouse"
        wh = Warehouse(wh_root)
        store = MemoryStore(Path(tempfile.mkdtemp()) / "test_bridge_memory.db")
        b = WorkshopBridge(wh, store)
        yield b
        store.close()

    def test_memory_store_is_accessible(self, bridge_with_memory):
        assert bridge_with_memory.memory_store is not None

    def test_combined_warehouse_and_memory(self, bridge_with_memory):
        bridge_with_memory.warehouse.write("lab-a", "output.md", "# Output")
        content = bridge_with_memory.read_peer_product("lab-a", "output.md")
        assert content == "# Output"

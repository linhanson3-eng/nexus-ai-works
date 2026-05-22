"""Gateway API tests — REST and WebSocket endpoints."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from factory.kanban.store import KanbanStore
from gateway.server import KanbanWSManager, create_app


class DummyOrg:
    """Minimal stub to satisfy create_app signature."""

    def status(self) -> dict:
        return {
            "departments": [],
            "total_agents": 0,
            "warehouse": "",
            "warehouse_products": {},
        }


@pytest_asyncio.fixture
async def kanban_store():
    with tempfile.TemporaryDirectory() as tmp:
        s = KanbanStore(Path(tmp) / "test_gateway_kanban.db")
        yield s
        s.close()


@pytest_asyncio.fixture
async def app(kanban_store):
    org = DummyOrg()
    return create_app(org=org, kanban_store=kanban_store)


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def board_id(client):
    resp = await client.post(
        "/api/boards",
        json={"name": "Test Board", "workshop_name": "test-ws", "description": "desc"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def list_id(client, board_id):
    resp = await client.post(
        f"/api/boards/{board_id}/lists",
        json={"name": "To Do"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


@pytest_asyncio.fixture
async def card_id(client, list_id):
    resp = await client.post(
        f"/api/lists/{list_id}/cards",
        json={"title": "Test Card"},
    )
    assert resp.status_code == 201
    return resp.json()["id"]


class TestHealth:
    @pytest.mark.asyncio
    async def test_health_endpoint(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data


class TestOrgStatus:
    @pytest.mark.asyncio
    async def test_org_status(self, client):
        resp = await client.get("/api/org/status")
        assert resp.status_code == 200
        data = resp.json()
        assert "departments" in data
        assert "total_agents" in data


class TestBoardAPI:
    @pytest.mark.asyncio
    async def test_create_board(self, client):
        resp = await client.post(
            "/api/boards",
            json={"name": "New Board", "workshop_name": "ws1"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "New Board"
        assert data["workshop_name"] == "ws1"
        assert data["id"] != ""

    @pytest.mark.asyncio
    async def test_create_board_defaults(self, client):
        resp = await client.post("/api/boards", json={})
        assert resp.status_code == 201
        assert resp.json()["name"] == "Untitled Board"

    @pytest.mark.asyncio
    async def test_list_boards(self, client):
        await client.post("/api/boards", json={"name": "B1", "workshop_name": "ws1"})
        await client.post("/api/boards", json={"name": "B2", "workshop_name": "ws1"})
        resp = await client.get("/api/boards?workshop_name=ws1")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_list_all_boards(self, client):
        resp = await client.get("/api/boards")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    @pytest.mark.asyncio
    async def test_get_board(self, client, board_id):
        resp = await client.get(f"/api/boards/{board_id}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["name"] == "Test Board"
        assert "lists" in data

    @pytest.mark.asyncio
    async def test_get_board_not_found(self, client):
        resp = await client.get("/api/boards/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_board(self, client, board_id):
        resp = await client.delete(f"/api/boards/{board_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == board_id

    @pytest.mark.asyncio
    async def test_delete_board_not_found(self, client):
        resp = await client.delete("/api/boards/nonexistent")
        assert resp.status_code == 404


class TestListAPI:
    @pytest.mark.asyncio
    async def test_create_list(self, client, board_id):
        resp = await client.post(
            f"/api/boards/{board_id}/lists",
            json={"name": "In Progress", "color": "#f0f0f0"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "In Progress"
        assert data["board_id"] == board_id

    @pytest.mark.asyncio
    async def test_create_list_board_not_found(self, client):
        resp = await client.post(
            "/api/boards/nonexistent/lists",
            json={"name": "List"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_lists(self, client, board_id):
        await client.post(f"/api/boards/{board_id}/lists", json={"name": "To Do"})
        await client.post(f"/api/boards/{board_id}/lists", json={"name": "Done"})
        resp = await client.get(f"/api/boards/{board_id}/lists")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_move_list(self, client, list_id):
        resp = await client.put(
            f"/api/lists/{list_id}/move",
            json={"position": 3},
        )
        assert resp.status_code == 200
        assert resp.json()["position"] == 3

    @pytest.mark.asyncio
    async def test_move_list_not_found(self, client):
        resp = await client.put(
            "/api/lists/nonexistent/move",
            json={"position": 0},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_delete_list(self, client, list_id):
        resp = await client.delete(f"/api/lists/{list_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == list_id

    @pytest.mark.asyncio
    async def test_delete_list_not_found(self, client):
        resp = await client.delete("/api/lists/nonexistent")
        assert resp.status_code == 404


class TestCardAPI:
    @pytest.mark.asyncio
    async def test_create_card(self, client, list_id):
        resp = await client.post(
            f"/api/lists/{list_id}/cards",
            json={
                "title": "Fix bug",
                "description": "Fix the login bug",
                "labels": ["bug", "urgent"],
                "assignee": "agent-1",
                "task_status": "todo",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["title"] == "Fix bug"
        assert data["description"] == "Fix the login bug"
        assert data["labels"] == ["bug", "urgent"]

    @pytest.mark.asyncio
    async def test_create_card_list_not_found(self, client):
        resp = await client.post(
            "/api/lists/nonexistent/cards",
            json={"title": "Test"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_get_cards(self, client, list_id):
        await client.post(f"/api/lists/{list_id}/cards", json={"title": "C1"})
        await client.post(f"/api/lists/{list_id}/cards", json={"title": "C2"})
        resp = await client.get(f"/api/lists/{list_id}/cards")
        assert resp.status_code == 200
        assert len(resp.json()) >= 2

    @pytest.mark.asyncio
    async def test_get_card(self, client, card_id):
        resp = await client.get(f"/api/cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["title"] == "Test Card"

    @pytest.mark.asyncio
    async def test_get_card_not_found(self, client):
        resp = await client.get("/api/cards/nonexistent")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update_card(self, client, card_id):
        resp = await client.put(
            f"/api/cards/{card_id}",
            json={"title": "Updated Title", "task_status": "done"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Updated Title"
        assert data["task_status"] == "done"

    @pytest.mark.asyncio
    async def test_update_card_not_found(self, client):
        resp = await client.put(
            "/api/cards/nonexistent",
            json={"title": "No"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_move_card(self, client, board_id, card_id):
        # Create a target list first
        list_resp = await client.post(
            f"/api/boards/{board_id}/lists",
            json={"name": "Done"},
        )
        target_list_id = list_resp.json()["id"]
        resp = await client.put(
            f"/api/cards/{card_id}/move",
            json={"list_id": target_list_id, "position": 0},
        )
        assert resp.status_code == 200
        assert resp.json()["list_id"] == target_list_id

    @pytest.mark.asyncio
    async def test_move_card_not_found(self, client):
        resp = await client.put(
            "/api/cards/nonexistent/move",
            json={"list_id": "some-list"},
        )
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_move_card_missing_list_id(self, client, card_id):
        resp = await client.put(
            f"/api/cards/{card_id}/move",
            json={},
        )
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_delete_card(self, client, card_id):
        resp = await client.delete(f"/api/cards/{card_id}")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == card_id

    @pytest.mark.asyncio
    async def test_delete_card_not_found(self, client):
        resp = await client.delete("/api/cards/nonexistent")
        assert resp.status_code == 404


class TestAgentSyncAPI:
    @pytest.mark.asyncio
    async def test_upsert_card_from_task(self, client, list_id):
        resp = await client.post(
            "/api/cards/upsert-from-task",
            json={
                "agent_name": "builder",
                "task_id": "task-001",
                "title": "Build feature",
                "task_status": "todo",
                "list_id": list_id,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["title"] == "Build feature"
        assert data["source_agent"] == "builder"
        assert data["source_task_id"] == "task-001"

    @pytest.mark.asyncio
    async def test_get_cards_by_agent(self, client, list_id):
        await client.post(
            f"/api/lists/{list_id}/cards",
            json={
                "title": "Task 1",
                "source_agent": "builder",
                "source_task_id": "t1",
            },
        )
        resp = await client.get("/api/cards/agent/builder")
        assert resp.status_code == 200
        cards = resp.json()
        assert len(cards) >= 1
        assert any(c["source_agent"] == "builder" for c in cards)

    @pytest.mark.asyncio
    async def test_get_cards_by_agent_empty(self, client):
        resp = await client.get("/api/cards/agent/unknown")
        assert resp.status_code == 200
        assert resp.json() == []


class TestKanbanWSManager:
    def test_initial_state(self):
        mgr = KanbanWSManager()
        assert mgr.rooms == {}

    def test_rooms_property(self):
        mgr = KanbanWSManager()
        mgr._rooms["board-1"] = set()
        mgr._rooms["board-2"] = {object()}
        assert mgr.rooms == {"board-1": 0, "board-2": 1}

    def test_disconnect_cleans_empty_room(self):
        mgr = KanbanWSManager()
        mgr._rooms["board-1"] = {object()}
        dummy_ws = list(mgr._rooms["board-1"])[0]
        mgr.disconnect("board-1", dummy_ws)
        assert "board-1" not in mgr._rooms

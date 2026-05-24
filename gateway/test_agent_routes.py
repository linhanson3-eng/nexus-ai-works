from __future__ import annotations

"""Tests for agent endpoint auth."""

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from factory.kanban.store import KanbanStore
from gateway.auth import get_or_create_api_key
from gateway.server import create_app


class DummyOrg:
    workshops: list = []
    warehouse = type("W", (), {"storage": type("S", (), {"list_products": lambda: []})()})()

    def status(self) -> dict:
        return {"departments": [], "total_agents": 0}


@pytest_asyncio.fixture
async def client():
    store = KanbanStore(":memory:")
    org = DummyOrg()
    app = create_app(org=org, kanban_store=store)
    transport = ASGITransport(app=app)
    api_key = get_or_create_api_key()
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, api_key


class TestAgentRunAuth:
    async def test_rejects_unauthenticated(self, client):
        ac, _ = client
        resp = await ac.post(
            "/api/agent/run/stream",
            json={"task": "hello", "workshop": ""},
        )
        assert resp.status_code == 401

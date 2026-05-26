from __future__ import annotations
"""Comprehensive tests for gateway routes: workshops, workflows, library, chains, market, settings."""

import asyncio
import os
import tempfile
import zipfile
import io
from pathlib import Path

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from factory.workflow.models import WorkflowTemplate, WorkflowNode
from factory.workflow.store import WorkflowStore
from factory.kanban.store import KanbanStore
from gateway.auth import get_or_create_api_key
from gateway.server import create_app


# ── Stub org that supports all route dependencies ──


class DummyWorkspace:
    def __init__(self, name, workspace=".", agents=None, workflow_name="simple"):
        self.name = name
        self.workspace = Path(workspace)
        self.agents = agents or {}
        self.workflow_name = workflow_name
        self.spec = type("Spec", (), {"agents": list(self.agents.values())})()


class DummyAgentSpec:
    def __init__(self, name, mode="super"):
        self.name = name
        self.mode = mode
        self.model = ""
        self.tools = []
        self.system_prompt = ""
        self.guide_file = ""
        self.skills = []
        self.permissions = type("Perm", (), {
            "filesystem": type("FS", (), {"write": ["workspace"]})(),
            "shell": type("Sh", (), {"exec": True})(),
            "subagent": type("Sub", (), {"spawn": True, "max": 5})(),
        })()
        self.budget = type("Budget", (), {})()


class DummyWorkshopManager:
    """Stub that mimics WorkshopManager for route testing. Shared state across instances."""

    _workshops: dict = {}  # class-level, shared across stub instances

    def __init__(self, org, kanban_store):
        self.org = org
        self.kanban_store = kanban_store
        if not DummyWorkshopManager._workshops:
            DummyWorkshopManager._workshops = {
                "test-ws": DummyWorkspace("test-ws", workspace=str(Path(tempfile.gettempdir()) / "nexus-test-ws")),
            }
            DummyWorkshopManager._workshops["test-ws"].agents = {"default": DummyAgentSpec("default")}

    def get(self, name):
        return DummyWorkshopManager._workshops.get(name)

    def create(self, name, workspace="", agent_names=None, workflow_name="simple", model=""):
        ws = DummyWorkspace(name, workspace=workspace or f"workspaces/{name}", workflow_name=workflow_name)
        for aname in (agent_names or ["default"]):
            ws.agents[str(aname)[:64]] = DummyAgentSpec(str(aname)[:64])
        DummyWorkshopManager._workshops[name] = ws
        return ws

    def list_all(self):
        return [
            type("Info", (), {
                "name": ws.name, "workspace": str(ws.workspace),
                "agent_count": len(ws.agents), "agent_names": list(ws.agents.keys()),
                "workflow_name": ws.workflow_name, "has_kanban": self.kanban_store is not None,
            })()
            for ws in DummyWorkshopManager._workshops.values()
        ]

    def status(self, name):
        ws = DummyWorkshopManager._workshops.get(name)
        if ws is None:
            return None
        return {"name": ws.name, "total_agents": len(ws.agents), "agents": list(ws.agents.keys())}

    def delete(self, name):
        if name not in DummyWorkshopManager._workshops:
            return False
        del DummyWorkshopManager._workshops[name]
        return True

    def list_agents(self, name):
        ws = DummyWorkshopManager._workshops.get(name)
        if ws is None:
            return None
        return [{"name": a.name, "mode": a.mode} for a in ws.agents.values()]

    def add_agent(self, workshop_name, spec):
        ws = DummyWorkshopManager._workshops.get(workshop_name)
        if ws is None:
            return None
        ws.agents[spec.name] = spec
        return spec.name

    def remove_agent(self, workshop_name, agent_name):
        ws = DummyWorkshopManager._workshops.get(workshop_name)
        if ws is None or agent_name not in ws.agents:
            return False
        del ws.agents[agent_name]
        return True

    def update_agent(self, workshop_name, agent_name, updates):
        ws = DummyWorkshopManager._workshops.get(workshop_name)
        if ws is None or agent_name not in ws.agents:
            return None
        return agent_name

    def export_workspace(self, name, output_dir=""):
        ws = DummyWorkshopManager._workshops.get(name)
        if ws is None:
            return None
        d = Path(output_dir) if output_dir else Path(tempfile.mkdtemp())
        d.mkdir(parents=True, exist_ok=True)
        (d / "manifest.json").write_text('{"name":"' + name + '"}')
        return str(d)

    def import_package(self, pkg_dir, custom_name=""):
        name = custom_name or Path(pkg_dir).name
        if name in DummyWorkshopManager._workshops:
            return None
        ws = DummyWorkspace(name)
        DummyWorkshopManager._workshops[name] = ws
        return {"name": name, "created": True}


class DummyOrg:
    """Extended stub org with workflow_store, library support, settings, etc."""

    def __init__(self):
        self.workflow_templates = {
            "simple": WorkflowTemplate(
                name="simple", description="Simple workflow",
                workspace="", nodes=[WorkflowNode(id="run", agent_name="default", prompt="do it")]
            ),
            "review": WorkflowTemplate(
                name="review", description="Review workflow",
                workspace="", nodes=[
                    WorkflowNode(id="draft", agent_name="default", prompt="draft"),
                    WorkflowNode(id="review", agent_name="default", prompt="review")
                ]
            ),
        }
        self.workflow_store = DummyWorkflowStore(self.workflow_templates)
        self.settings = type("Settings", (), {
            "_data": {
                "providers": {"deepseek": {"provider_type": "deepseek", "base_url": "https://api.deepseek.com", "api_key": "sk-test"}},
                "search": {"tavily_api_key": "", "brave_api_key": ""},
                "preferences": {"language": "zh"},
            }
        })()
        self.workshops = []
        self.channels = []
        self.warehouse = type("Warehouse", (), {"path": ""})()

    def status(self):
        return {"departments": [], "total_agents": 0, "warehouse": ""}


class DummyWorkflowStore:
    def __init__(self, templates=None):
        self._templates = templates or {}

    def list_all(self):
        return [{"name": n, "description": t.description} for n, t in self._templates.items()]

    def load(self, name):
        return self._templates.get(name)

    def save(self, tmpl):
        self._templates[tmpl.name] = tmpl
        return f"/tmp/{tmpl.name}.yaml"

    def delete(self, name):
        if name not in self._templates:
            return False
        del self._templates[name]
        return True


# ── Fixtures ──


@pytest_asyncio.fixture
async def tmp_kanban():
    with tempfile.TemporaryDirectory() as tmp:
        s = KanbanStore(Path(tmp) / "test_routes_kanban.db")
        yield s
        s.close()


@pytest_asyncio.fixture
async def org():
    return DummyOrg()


@pytest_asyncio.fixture
async def app(org, tmp_kanban):
    return create_app(org=org, kanban_store=tmp_kanban)


@pytest_asyncio.fixture
async def client(app):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        resp = await c.get("/api/csrf-token")
        token = resp.json()["token"]
        c.headers["X-CSRF-Token"] = token
        c.headers["X-API-Key"] = get_or_create_api_key()
        yield c


# ── Helper: replace WorkshopManager with stub ──

@pytest.fixture(autouse=True)
def _patch_workshop_manager(monkeypatch):
    """Replace WorkshopManager in factory.workshop.manager so lazy imports in routes use the stub."""
    import factory.workshop.manager as fwm
    import factory.workflow.engine as wfe
    import factory.runner as fr

    monkeypatch.setattr(fwm, "WorkshopManager", lambda org, kb=None: DummyWorkshopManager(org, kb))
    monkeypatch.setattr(fr, "NexusAgentRunner", lambda *a, **kw: _StubRunner())
    monkeypatch.setattr(wfe, "WorkflowRunner", lambda ws, store=None, on_status=None, org=None: _StubWorkflowRunner())

    # Also patch workshop.bridge for the bridge/product routes
    monkeypatch.setattr(
        "factory.workshop.bridge.WorkshopBridge",
        lambda warehouse: _StubBridge(warehouse),
        raising=False,
    )
    # Patch SettingsStore and ChainStore for settings/chains routes
    monkeypatch.setattr(
        "gateway.server.SettingsStore",
        lambda: _StubSettingsStore(),
        raising=False,
    )
    monkeypatch.setattr(
        "gateway.server.ChainStore",
        lambda: _StubChainStore(),
        raising=False,
    )
    # Patch ChainRunner for chain execution routes
    monkeypatch.setattr(
        "factory.workflow.chain.ChainRunner",
        lambda org, kb, on_status=None: _StubChainRunner(),
        raising=False,
    )


class _StubBridge:
    def __init__(self, warehouse):
        self.warehouse = warehouse

    def list_peer_products(self, name):
        return []


class _StubRunner:
    async def run(self, task, progress_queue=None):
        class Result:
            content = "stub reply"
            turns = 1
            cost_usd = 0.0
            tools_used = []
            session_id = "stub-session"
            model = "test-model"
            events = []
            error = None
        return Result()


class _StubWorkflowRunner:
    def __init__(self, ws=None, store=None, on_status=None):
        pass

    async def run(self, tmpl, task):
        from dataclasses import dataclass
        from enum import Enum

        class _NS(str, Enum):
            PASSED = "passed"
            RUNNING = "running"
            FAILED = "failed"
            PENDING = "pending"
            SKIPPED = "skipped"

        @dataclass
        class _NR:
            node_id: str = "run"
            agent_name: str = "default"
            status: _NS = _NS.PASSED
            output: str = "done"
            error: str | None = None

        @dataclass
        class _WR:
            status: _NS = _NS.PASSED
            template_name: str = ""
            node_results: dict = None  # type: ignore[assignment]
            final_output: str = "done"

        return _WR(
            template_name=tmpl.name,
            node_results={"run": _NR()},
            final_output="done",
        )


class _StubSettingsStore:
    """Stub SettingsStore for settings routes."""

    def __init__(self):
        self._data = {
            "providers": {},
            "plugins": {},
            "search": {"tavily_api_key": "", "brave_api_key": "", "deep_search_enabled": False},
            "preferences": {"language": "zh"},
        }

    def list_providers(self, mask_keys=False):
        return list(self._data.get("providers", {}).values())

    def save_provider(self, name, **kwargs):
        self._data.setdefault("providers", {})[name] = {"name": name, **kwargs}
        return {"status": "ok", "name": name}

    def delete_provider(self, name):
        if name not in self._data.get("providers", {}):
            return False
        del self._data["providers"][name]
        return True

    def sync_models(self, name):
        return {"name": name, "models": [], "updated": 0}

    def list_plugins(self):
        return self._data.get("plugins", {})

    def save_plugin(self, name, **kwargs):
        self._data.setdefault("plugins", {})[name] = {"name": name, **kwargs}
        return {"status": "ok", "name": name}

    def delete_plugin(self, name):
        if name not in self._data.get("plugins", {}):
            return False
        del self._data["plugins"][name]
        return True

    def get_search(self):
        return dict(self._data.get("search", {}))

    def save_search(self, **fields):
        self._data.setdefault("search", {}).update(fields)
        return {"status": "ok"}

    def save_tool(self, name, **kwargs):
        return {"status": "ok", "name": name}

    def _save(self):
        pass  # no-op for stub


class _StubChainStore:
    """Stub ChainStore for chains routes."""

    def __init__(self):
        self._chains = {}

    def list_all(self):
        return [{"name": n, "description": c.get("description", "")} for n, c in self._chains.items()]

    def load(self, name):
        return self._chains.get(name)

    def save(self, chain):
        self._chains[chain.name] = chain
        return f"/tmp/{chain.name}.yaml"

    def delete(self, name):
        if name not in self._chains:
            return False
        del self._chains[name]
        return True

    def to_dict(self, chain=None):
        return {}


class _StubChainRunner:
    """Stub ChainRunner that returns a mock result."""

    def __init__(self, org=None, kb=None, on_status=None):
        pass

    async def run(self, chain, task):
        from dataclasses import dataclass

        @dataclass
        class _CR:
            status: str = "passed"
            chain_name: str = chain.name
            step_results: list = []
            final_output: str = "done"

        return _CR()


# ═══════════════════════════════════════════════════════════════════
# Workshop Routes
# ═══════════════════════════════════════════════════════════════════


class TestWorkshopRoutes:
    async def test_create_workshop(self, client):
        resp = await client.post("/api/workshops", json={"name": "new-ws"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "new-ws"

    async def test_create_workshop_no_name(self, client):
        resp = await client.post("/api/workshops", json={})
        assert resp.status_code == 400

    async def test_list_workshops(self, client):
        resp = await client.get("/api/workshops")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(w["name"] == "test-ws" for w in data)

    async def test_get_workshop(self, client):
        resp = await client.get("/api/workshops/test-ws")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-ws"

    async def test_get_workshop_not_found(self, client):
        resp = await client.get("/api/workshops/nope")
        assert resp.status_code == 404

    async def test_delete_workshop(self, client):
        await client.post("/api/workshops", json={"name": "del-me"})
        resp = await client.delete("/api/workshops/del-me")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "del-me"

    async def test_delete_workshop_not_found(self, client):
        resp = await client.delete("/api/workshops/nonexistent")
        assert resp.status_code == 404

    async def test_export_workshop(self, client):
        resp = await client.post("/api/workshops/test-ws/export")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "application/zip"

    async def test_export_workshop_not_found(self, client):
        resp = await client.post("/api/workshops/nope/export")
        assert resp.status_code == 404

    async def test_import_workshop(self, client):
        # Build a minimal .nexus zip in memory
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", '{"name":"imported-ws"}')
            zf.writestr("agents.json", '{"agents":[{"name":"agent1"}]}')
        buf.seek(0)

        resp = await client.post(
            "/api/workshops/import",
            files={"file": ("test.nexus.zip", buf.read(), "application/zip")},
            data={"name": "imported-ws"},
        )
        assert resp.status_code == 201
        assert resp.json()["name"] == "imported-ws"

    async def test_import_workshop_no_file(self, client):
        resp = await client.post("/api/workshops/import")
        assert resp.status_code == 400

    async def test_import_workshop_already_exists(self, client):
        # Import with a name that already exists
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("manifest.json", '{"name":"will-fail"}')
        buf.seek(0)

        # First import succeeds
        await client.post(
            "/api/workshops/import",
            files={"file": ("dup.nexus.zip", buf.read(), "application/zip")},
            data={"name": "will-fail"},
        )
        # Second import with same name fails
        buf.seek(0)
        resp = await client.post(
            "/api/workshops/import",
            files={"file": ("dup.nexus.zip", buf.read(), "application/zip")},
            data={"name": "will-fail"},
        )
        assert resp.status_code == 409

    async def test_list_workshop_agents(self, client):
        resp = await client.get("/api/workshops/test-ws/agents")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    async def test_list_agents_workshop_not_found(self, client):
        resp = await client.get("/api/workshops/nope/agents")
        assert resp.status_code == 404

    async def test_org_status(self, client):
        resp = await client.get("/api/org/status")
        assert resp.status_code == 200

    async def test_read_workshop_file_not_found(self, client):
        resp = await client.get("/api/workshops/test-ws/files/nonexistent.txt")
        assert resp.status_code == 404

    async def test_workshop_products(self, client):
        resp = await client.get("/api/workshops/test-ws/products")
        assert resp.status_code == 200
        assert "products" in resp.json()

    async def test_bridge_peer_products(self, client):
        resp = await client.get("/api/workshops/test-ws/bridge/peer-ws")
        assert resp.status_code == 200
        assert resp.json()["peer"] == "peer-ws"


# ═══════════════════════════════════════════════════════════════════
# Workflow Routes
# ═══════════════════════════════════════════════════════════════════


class TestWorkflowRoutes:
    async def test_list_workflows(self, client):
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert any(w["name"] == "simple" for w in data)

    async def test_get_workflow(self, client):
        resp = await client.get("/api/workflows/simple")
        assert resp.status_code == 200
        assert resp.json()["name"] == "simple"

    async def test_get_workflow_not_found(self, client):
        resp = await client.get("/api/workflows/nope")
        assert resp.status_code == 404

    async def test_create_workflow(self, client):
        resp = await client.post("/api/workflows", json={
            "name": "custom-wf",
            "description": "Custom workflow",
            "workspace": "test-ws",
            "nodes": [{"id": "step1", "agent_name": "default", "prompt": "do it"}],
        })
        assert resp.status_code == 200
        assert resp.json()["saved"]

    async def test_delete_workflow(self, client):
        await client.post("/api/workflows", json={
            "name": "to-delete", "nodes": [],
        })
        resp = await client.delete("/api/workflows/to-delete")
        assert resp.status_code == 200
        assert resp.json()["deleted"] == "to-delete"

    async def test_delete_workflow_not_found(self, client):
        resp = await client.delete("/api/workflows/nope")
        assert resp.status_code == 404

    async def test_execute_workflow_no_task(self, client):
        resp = await client.post("/api/workflows/simple/execute", json={"task": "", "workshop": "test-ws"})
        assert resp.status_code == 400

    async def test_execute_workflow_not_found(self, client):
        resp = await client.post("/api/workflows/nope/execute", json={"task": "hello", "workshop": "test-ws"})
        assert resp.status_code == 404

    async def test_execute_workflow_workshop_not_found(self, client):
        resp = await client.post("/api/workflows/simple/execute", json={"task": "hello", "workshop": "missing"})
        assert resp.status_code == 404

    async def test_execute_workflow_stream(self, client):
        """SSE streaming endpoint returns proper event stream."""
        resp = await client.post("/api/workflows/simple/execute", json={"task": "hello world", "workshop": "test-ws"})
        assert resp.status_code == 200
        assert "text/event-stream" in resp.headers["content-type"]


# ═══════════════════════════════════════════════════════════════════
# Library Routes
# ═══════════════════════════════════════════════════════════════════


class TestLibraryRoutes:
    async def test_list_workflow_entries(self, client):
        resp = await client.get("/api/library/workflow")
        assert resp.status_code == 200

    async def test_list_invalid_entry_type(self, client):
        resp = await client.get("/api/library/invalid")
        assert resp.status_code == 400

    async def test_get_entry_not_found(self, client):
        resp = await client.get("/api/library/workflow/nonexistent")
        assert resp.status_code == 404

    async def test_save_entry_invalid_type(self, client):
        resp = await client.post("/api/library/invalid", json={"name": "test"})
        assert resp.status_code == 400

    async def test_delete_entry_not_found(self, client):
        resp = await client.delete("/api/library/workflow/nonexistent")
        assert resp.status_code == 404

    async def test_install_entry_not_found(self, client):
        resp = await client.post("/api/library/workflow/nonexistent/install", json={"workshop": "test-ws"})
        assert resp.status_code == 404


# ═══════════════════════════════════════════════════════════════════
# Settings Routes
# ═══════════════════════════════════════════════════════════════════


class TestSettingsRoutes:
    async def test_list_providers(self, client):
        resp = await client.get("/api/settings/providers")
        assert resp.status_code == 200

    async def test_save_provider(self, client):
        resp = await client.post("/api/settings/providers", json={
            "name": "test-provider", "base_url": "https://api.example.com",
        })
        assert resp.status_code == 200

    async def test_save_provider_no_name(self, client):
        resp = await client.post("/api/settings/providers", json={"base_url": "https://x.com"})
        assert resp.status_code == 400

    async def test_delete_provider(self, client):
        await client.post("/api/settings/providers", json={"name": "del-provider"})
        resp = await client.delete("/api/settings/providers/del-provider")
        assert resp.status_code == 200

    async def test_delete_provider_not_found(self, client):
        resp = await client.delete("/api/settings/providers/nonexistent")
        assert resp.status_code == 404

    async def test_sync_provider_models(self, client):
        await client.post("/api/settings/providers", json={"name": "sync-me"})
        resp = await client.post("/api/settings/providers/sync-me/sync-models")
        assert resp.status_code == 200

    async def test_get_preferences(self, client):
        resp = await client.get("/api/settings/preferences")
        assert resp.status_code == 200

    async def test_save_preferences(self, client):
        resp = await client.post("/api/settings/preferences", json={"language": "en"})
        assert resp.status_code == 200

    async def test_get_search_config(self, client):
        resp = await client.get("/api/settings/search")
        assert resp.status_code == 200

    async def test_save_search_config(self, client):
        resp = await client.post("/api/settings/search", json={
            "tavily_api_key": "tvly-test12345678",
            "deep_search_enabled": True,
        })
        assert resp.status_code == 200

    async def test_save_plugin(self, client):
        resp = await client.post("/api/settings/plugins", json={
            "name": "slack", "enabled": True,
        })
        assert resp.status_code == 200

    async def test_save_plugin_no_name(self, client):
        resp = await client.post("/api/settings/plugins", json={"enabled": True})
        assert resp.status_code == 400

    async def test_delete_plugin(self, client):
        await client.post("/api/settings/plugins", json={"name": "del-plugin"})
        resp = await client.delete("/api/settings/plugins/del-plugin")
        assert resp.status_code == 200

    async def test_delete_plugin_not_found(self, client):
        resp = await client.delete("/api/settings/plugins/nonexistent")
        assert resp.status_code == 404

    async def test_list_settings_tools(self, client):
        resp = await client.get("/api/settings/tools")
        assert resp.status_code == 200

    async def test_save_tool(self, client):
        resp = await client.post("/api/settings/tools", json={
            "name": "custom-tool", "description": "A custom tool",
        })
        assert resp.status_code == 200

    async def test_save_tool_no_name(self, client):
        resp = await client.post("/api/settings/tools", json={"description": "no name"})
        assert resp.status_code == 400

    async def test_sync_tools(self, client):
        resp = await client.post("/api/settings/tools/sync")
        assert resp.status_code == 200


# ═══════════════════════════════════════════════════════════════════
# Chain Routes
# ═══════════════════════════════════════════════════════════════════


class TestChainRoutes:
    async def test_list_chains(self, client):
        resp = await client.get("/api/chains")
        assert resp.status_code == 200

    async def test_create_chain(self, client):
        resp = await client.post("/api/chains", json={
            "name": "test-chain",
            "description": "A test chain",
            "steps": [{"workshop": "test-ws", "task": "do it"}],
        })
        assert resp.status_code == 200
        assert resp.json()["saved"]

    async def test_get_chain_not_found(self, client):
        resp = await client.get("/api/chains/nonexistent")
        assert resp.status_code == 404

    async def test_delete_chain_not_found(self, client):
        resp = await client.delete("/api/chains/nonexistent")
        assert resp.status_code == 404

    async def test_delete_chain(self, client):
        await client.post("/api/chains", json={"name": "del-chain", "steps": []})
        resp = await client.delete("/api/chains/del-chain")
        assert resp.status_code == 200

    async def test_execute_chain_no_task(self, client):
        await client.post("/api/chains", json={"name": "exec-chain", "steps": []})
        resp = await client.post("/api/chains/exec-chain/execute", json={"task": ""})
        assert resp.status_code == 400

    async def test_execute_chain_not_found(self, client):
        resp = await client.post("/api/chains/nope/execute", json={"task": "hello"})
        assert resp.status_code == 404

    async def test_execute_chain_stream(self, client):
        await client.post("/api/chains", json={"name": "stream-chain", "steps": []})
        resp = await client.post("/api/chains/stream-chain/execute", json={"task": "run test"})
        assert resp.status_code == 200

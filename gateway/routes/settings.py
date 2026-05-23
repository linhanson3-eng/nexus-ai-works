"""Settings endpoints: providers, skills, tools, plugins, and search."""

from __future__ import annotations

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse

from gateway.auth import require_auth

router = APIRouter(prefix="/api", tags=["settings"])


def _settings_store(request: Request):
    return request.app.state.settings_store


# ── Providers ──


@router.get("/settings/providers", dependencies=[Depends(require_auth)])
async def list_providers(request: Request):
    return JSONResponse(content=_settings_store(request).list_providers(mask_keys=True))


@router.post("/settings/providers", dependencies=[Depends(require_auth)])
async def save_provider(request: Request):
    body = await request.json()
    name = body.pop("name", "")
    if not name:
        return JSONResponse(content={"detail": "name is required"}, status_code=400)
    result = _settings_store(request).save_provider(name, **body)
    return JSONResponse(content=result)


@router.delete("/settings/providers/{name}", dependencies=[Depends(require_auth)])
async def delete_provider(name: str, request: Request):
    ok = _settings_store(request).delete_provider(name)
    if not ok:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})


@router.post("/settings/providers/{name}/sync-models", dependencies=[Depends(require_auth)])
async def sync_provider_models(name: str, request: Request):
    """Fetch latest model list from provider's /v1/models endpoint."""
    result = _settings_store(request).sync_models(name)
    return JSONResponse(content=result)


# ── Skills ──


@router.get("/settings/skills", dependencies=[Depends(require_auth)])
async def list_settings_skills():
    from factory.skills.marketplace import SkillMarketplace

    mp = SkillMarketplace()
    mp.discover()
    return JSONResponse(content=[
        {
            "name": s.name, "full_name": s.full_name, "description": s.description,
            "plugin": s.plugin, "source": s.source, "file_path": s.file_path,
        }
        for s in mp.list_all()
    ])


@router.post("/settings/skills/sync", dependencies=[Depends(require_auth)])
async def sync_skills():
    from factory.skills.marketplace import SkillMarketplace

    mp = SkillMarketplace()
    count = mp.discover()
    return JSONResponse(content={
        "status": "ok", "count": count,
        "skills": [
            {
                "name": s.name, "full_name": s.full_name, "description": s.description,
                "plugin": s.plugin, "source": s.source,
            }
            for s in mp.list_all()
        ],
    })


@router.get("/settings/skills/{name}", dependencies=[Depends(require_auth)])
async def get_skill_detail(name: str):
    from factory.skills.marketplace import SkillMarketplace

    mp = SkillMarketplace()
    mp.discover()
    skill = mp.get(name)
    if skill is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={
        "name": skill.name, "full_name": skill.full_name,
        "description": skill.description, "plugin": skill.plugin,
        "source": skill.source, "file_path": skill.file_path,
        "body": skill.get_body()[:5000],
    })


# ── Tools ──


@router.get("/settings/tools", dependencies=[Depends(require_auth)])
async def list_settings_tools():
    from factory.mcp.registry import MCPRegistry

    registry = MCPRegistry()
    servers = []
    for s in registry.list_servers():
        servers.append({
            "name": s.name, "description": s.description,
            "category": s.category, "transport": s.transport,
        })
    for entry in registry.list_marketplace():
        servers.append({
            "name": entry.name, "description": entry.description,
            "category": entry.category, "install_command": entry.install_command,
        })
    return JSONResponse(content=servers)


@router.post("/settings/tools", dependencies=[Depends(require_auth)])
async def save_tool(request: Request):
    body = await request.json()
    name = body.pop("name", "")
    if not name:
        return JSONResponse(content={"detail": "name is required"}, status_code=400)
    result = _settings_store(request).save_tool(name, **body)
    return JSONResponse(content=result)


@router.post("/settings/tools/sync", dependencies=[Depends(require_auth)])
async def sync_tools():
    from factory.mcp.registry import MCPRegistry

    registry = MCPRegistry()
    servers = []
    for s in registry.list_servers():
        servers.append({
            "name": s.name, "description": s.description, "category": s.category,
        })
    for entry in registry.list_marketplace():
        servers.append({
            "name": entry.name, "description": entry.description,
            "category": entry.category, "install_command": entry.install_command,
        })
    return JSONResponse(content={"status": "ok", "count": len(servers), "servers": servers})


# ── Plugins ──


@router.get("/settings/plugins", dependencies=[Depends(require_auth)])
async def list_settings_plugins(request: Request):
    from factory.channel.adapter import get_adapter, list_adapters as list_channel_names

    names = list_channel_names()
    stored = _settings_store(request).list_plugins()
    result = {}
    for name in names:
        adapter = get_adapter(name)
        result[name] = {
            "name": name,
            "enabled": stored.get(name, {}).get("enabled", True),
            "healthy": adapter.health() if adapter else False,
        }
    for name, cfg in stored.items():
        if name not in result:
            result[name] = {"name": name, "enabled": cfg.get("enabled", False), "healthy": False}
    return JSONResponse(content=result)


@router.post("/settings/plugins", dependencies=[Depends(require_auth)])
async def save_plugin(request: Request):
    body = await request.json()
    name = body.pop("name", "")
    if not name:
        return JSONResponse(content={"detail": "name is required"}, status_code=400)
    result = _settings_store(request).save_plugin(name, **body)
    return JSONResponse(content=result)


@router.delete("/settings/plugins/{name}", dependencies=[Depends(require_auth)])
async def delete_plugin(name: str, request: Request):
    ok = _settings_store(request).delete_plugin(name)
    if not ok:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})


# ── Preferences ──


@router.get("/settings/preferences", dependencies=[Depends(require_auth)])
async def get_preferences(request: Request):
    store = _settings_store(request)
    prefs = store._data.setdefault("preferences", {})
    return JSONResponse(content=dict(prefs))


@router.post("/settings/preferences", dependencies=[Depends(require_auth)])
async def save_preferences(request: Request):
    body = await request.json()
    store = _settings_store(request)
    prefs = store._data.setdefault("preferences", {})
    prefs.update(body)
    store._save()
    return JSONResponse(content=dict(prefs))


# ── Search ──


@router.get("/settings/search", dependencies=[Depends(require_auth)])
async def get_search_config(request: Request):
    cfg = _settings_store(request).get_search()
    for key in ("tavily_api_key", "brave_api_key"):
        k = cfg.get(key, "")
        if k and len(k) > 8:
            cfg[key] = k[:4] + "..." + k[-4:]
    return JSONResponse(content=cfg)


@router.post("/settings/search", dependencies=[Depends(require_auth)])
async def save_search_config(body: dict = Body(...), request: Request = None):  # type: ignore[assignment]  # FastAPI injects Request via DI
    allowed = {
        "tavily_api_key", "brave_api_key", "searxng_base_url",
        "active_provider", "deep_search_enabled", "max_results",
    }
    fields = {k: v for k, v in body.items() if k in allowed}
    result = _settings_store(request).save_search(**fields)
    return JSONResponse(content=result)

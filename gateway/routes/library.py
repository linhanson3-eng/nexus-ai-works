"""Local template library API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from factory.library.models import EntryType, InstallRequest, SaveRequest
from factory.library.store import (
    LibraryStore,
    save_agent_to_library,
    save_role_to_library,
    save_workflow_to_library,
)

router = APIRouter(prefix="/api/library", tags=["library"])


def _store() -> LibraryStore:
    return LibraryStore()


def _org(request: Request):
    return request.app.state.org


# ── Save ──


@router.post("/{entry_type}")
async def save_entry(entry_type: str, body: SaveRequest, request: Request):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}. Use workflow/agent/role."},
            status_code=400,
        )
    store = _store()
    try:
        if et == EntryType.WORKFLOW:
            entry = save_workflow_to_library(
                store, body.name, _org(request),
                description=body.description, category=body.category,
                tags=body.tags, source_workshop=body.workshop,
            )
        elif et == EntryType.AGENT:
            entry = save_agent_to_library(
                store, body.name, body.workshop, _org(request),
                description=body.description, category=body.category,
                tags=body.tags,
            )
        else:
            entry = save_role_to_library(
                store, body.name, body.workshop or "config/roles",
                description=body.description, category=body.category,
                tags=body.tags,
            )
        return JSONResponse(content=entry.model_dump(), status_code=201)
    except ValueError as e:
        return JSONResponse(content={"detail": str(e)}, status_code=404)


# ── List ──


@router.get("/{entry_type}")
async def list_entries(
    entry_type: str,
    search: str = "",
    category: str = "",
    tag: str = "",
):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    entries = _store().list_all(et, search=search, category=category, tag=tag)
    return JSONResponse(content=[e.model_dump() for e in entries])


# ── Get ──


@router.get("/{entry_type}/{name}")
async def get_entry(entry_type: str, name: str):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    entry = _store().get(et, name)
    if entry is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=entry.model_dump())


# ── Install ──


@router.post("/{entry_type}/{name}/install")
async def install_entry(entry_type: str, name: str, body: InstallRequest, request: Request):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    store = _store()
    entry = store.get(et, name)
    if entry is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    org = _org(request)
    try:
        if et == EntryType.WORKFLOW:
            ok = store.install_workflow(name, org.workflow_store)
        elif et == EntryType.AGENT:
            ok = store.install_agent(name, body.workshop, org)
        else:
            ok = store.install_role(name)
        if not ok:
            return JSONResponse(content={"detail": "Install failed"}, status_code=500)
        return JSONResponse(content={"installed": name, "type": entry_type, "workshop": body.workshop})
    except Exception as e:
        return JSONResponse(content={"detail": str(e)}, status_code=500)


# ── Delete ──


@router.delete("/{entry_type}/{name}")
async def delete_entry(entry_type: str, name: str):
    try:
        et = EntryType(entry_type)
    except ValueError:
        return JSONResponse(
            content={"detail": f"Invalid entry_type: {entry_type}"},
            status_code=400,
        )
    ok = _store().delete(et, name)
    if not ok:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})

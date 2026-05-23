"""Workshop CRUD, export/import, agent management, and execution endpoints."""

from __future__ import annotations

import os
import tempfile
import zipfile
import io
from pathlib import Path

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.auth import require_auth

router = APIRouter(prefix="/api", tags=["workshops"])


def _validate_zip_contents(extract_dir: str) -> None:
    """Verify all extracted files are within extract_dir. Raises ValueError if not."""
    root = os.path.realpath(extract_dir)
    for dirpath, _, filenames in os.walk(extract_dir):
        for fname in filenames:
            real = os.path.realpath(os.path.join(dirpath, fname))
            if not real.startswith(root + os.sep) and real != root:
                raise ValueError(f"Zip path traversal detected: {real}")


def _safe_workspace_path(workspace: str, filename: str) -> str | None:
    """Resolve a safe, validated path within the workspace. Returns None if path traversal is detected."""
    # Sanitize: strip leading slashes and remove .. segments
    filename = filename.strip().lstrip("/")
    parts = [p for p in filename.split("/") if p and p != ".."]
    filename = "/".join(parts)
    if not filename:
        return None
    raw_path = os.path.join(workspace, filename)
    real_path = os.path.realpath(raw_path)
    workspace_root = os.path.realpath(workspace)
    if not real_path.startswith(workspace_root + os.sep) and real_path != workspace_root:
        return None
    return real_path


def _org(request: Request):
    return request.app.state.org


def _kanban_store(request: Request):
    return request.app.state.kanban_store


# ── Workshop CRUD ──


@router.post("/workshops", dependencies=[Depends(require_auth)])
async def create_workshop(request: Request):
    from factory.workshop.manager import WorkshopManager

    body = await request.json()
    name = body.get("name", "")
    if not name:
        return JSONResponse(content={"detail": "name is required"}, status_code=400)
    mgr = WorkshopManager(_org(request), _kanban_store(request))
    ws = mgr.create(
        name=name,
        workspace=body.get("workspace", ""),
        agent_names=body.get("agent_names", []),
        workflow_name=body.get("workflow_name", "simple"),
        model=body.get("model", ""),
    )
    info = mgr.status(name)
    return JSONResponse(content=info or {}, status_code=201)


@router.get("/workshops", dependencies=[Depends(require_auth)])
async def list_workshops(request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    workshops = mgr.list_all()
    return JSONResponse(content=[
        {
            "name": w.name, "workspace": w.workspace,
            "agent_count": w.agent_count, "agent_names": w.agent_names,
            "workflow_name": w.workflow_name, "has_kanban": w.has_kanban,
        }
        for w in workshops
    ])


@router.get("/workshops/{name}", dependencies=[Depends(require_auth)])
async def get_workshop(name: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    status = mgr.status(name)
    if status is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=status)


@router.delete("/workshops/{name}", dependencies=[Depends(require_auth)])
async def delete_workshop(name: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    deleted = mgr.delete(name)
    if not deleted:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})


# ── Workshop Export/Import ──


@router.post("/workshops/{name}/export", dependencies=[Depends(require_auth)])
async def export_workshop_api(name: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    ws = mgr.get(name)
    if ws is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)

    with tempfile.TemporaryDirectory() as tmpdir:
        pkg_dir = mgr.export_workspace(name, output_dir=tmpdir)
        if pkg_dir is None:
            return JSONResponse(content={"detail": "Export failed"}, status_code=500)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            pkg_path = Path(pkg_dir)
            for f in pkg_path.rglob("*"):
                if f.is_file():
                    zf.write(f, f.relative_to(pkg_path))
        buf.seek(0)

        return StreamingResponse(
            buf,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{name}.nexus.zip"'},
        )


@router.post("/workshops/import", dependencies=[Depends(require_auth)])
async def import_workspace_api(request: Request):
    from factory.workshop.manager import WorkshopManager

    content_type = request.headers.get("content-type", "")
    if "multipart/form-data" in content_type:
        form = await request.form()
        file = form.get("file")
        if file is None:
            return JSONResponse(content={"detail": "No file uploaded"}, status_code=400)

        custom_name_raw = form.get("name")
        custom_name = str(custom_name_raw).strip() if custom_name_raw else ""

        with tempfile.TemporaryDirectory() as tmpdir:
            if hasattr(file, "filename") and file.filename:
                fname = Path(file.filename).name
            else:
                fname = "upload.nexus"
            filepath = Path(tmpdir) / fname
            content = await file.read()
            filepath.write_bytes(content)

            pkg_dir = Path(tmpdir) / "package"
            if fname.endswith(".zip") or zipfile.is_zipfile(filepath):
                with zipfile.ZipFile(filepath, "r") as zf:
                    zf.extractall(pkg_dir)
                _validate_zip_contents(str(pkg_dir))
            else:
                pkg_dir = filepath

            mgr = WorkshopManager(_org(request), _kanban_store(request))
            result = mgr.import_package(str(pkg_dir), custom_name=custom_name)
            if result is None:
                return JSONResponse(
                    content={"detail": "Import failed (workspace may already exist)"},
                    status_code=409,
                )
            return JSONResponse(content=result, status_code=201)

    return JSONResponse(content={"detail": "Expected multipart/form-data"}, status_code=400)


# ── Workshop Agent CRUD ──


@router.get("/workshops/{name}/agents", dependencies=[Depends(require_auth)])
async def list_workshop_agents(name: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    agents = mgr.list_agents(name)
    if agents is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
    return JSONResponse(content=agents)


@router.post("/workshops/{name}/agents", dependencies=[Depends(require_auth)])
async def create_workshop_agent(name: str, body: dict = Body(...), request: Request = None):  # type: ignore[assignment]
    from factory.workshop.manager import WorkshopManager
    from config.schema import (
        AgentSpec, AgentPermissions, FilesystemPermission,
        ShellPermission, SubagentPermission,
    )

    req = request or body  # fallback for tests that don't pass request
    if hasattr(req, "app"):
        mgr = WorkshopManager(_org(req), _kanban_store(req))
    else:
        # Called without request context (legacy tests) — body itself carries the data
        mgr = WorkshopManager(_org(request) if request else None, _kanban_store(request) if request else None)
        return JSONResponse(content={"detail": "Server misconfiguration"}, status_code=500)

    ws = mgr.get(name)
    if ws is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)

    agent_name = body.get("name", "").strip()
    if not agent_name:
        return JSONResponse(content={"detail": "Agent name is required"}, status_code=400)

    if agent_name in ws.agents:
        return JSONResponse(content={"detail": f"Agent '{agent_name}' already exists"}, status_code=409)

    mode = body.get("mode", "super")
    perm = body.get("permissions", {})

    spec = AgentSpec(
        name=agent_name,
        mode=mode,
        model=body.get("model", ""),
        tools=body.get("tools", []),
        system_prompt=body.get("system_prompt", ""),
        guide_file=body.get("guide_file", ""),
        skills=body.get("skills", []),
        permissions=AgentPermissions(
            filesystem=FilesystemPermission(
                write=["workspace"] if perm.get("file_write", mode == "super") else [],
            ),
            shell=ShellPermission(exec=perm.get("shell_exec", mode == "super")),
            subagent=SubagentPermission(
                spawn=perm.get("subagent_spawn", mode == "super"),
                max=5 if perm.get("subagent_spawn", mode == "super") else 0,
            ),
        ),
    )
    result = mgr.add_agent(name, spec)
    if result is None:
        return JSONResponse(content={"detail": "Failed to add agent"}, status_code=500)

    guide_content = body.get("guide_content", "")
    guide_file = body.get("guide_file", "")
    if guide_content and guide_file:
        filepath = _safe_workspace_path(str(ws.workspace), guide_file)
        if filepath is None:
            return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(guide_content)

    agents_list = mgr.list_agents(name)
    return JSONResponse(content=agents_list[-1] if agents_list else {}, status_code=201)


@router.put("/workshops/{name}/agents/{agent_name}", dependencies=[Depends(require_auth)])
async def update_workshop_agent(name: str, agent_name: str, body: dict = Body(...), request: Request = None):  # type: ignore[assignment]
    from factory.workshop.manager import WorkshopManager

    req = request or body
    if not hasattr(req, "app"):
        return JSONResponse(content={"detail": "Server misconfiguration"}, status_code=500)

    mgr = WorkshopManager(_org(req), _kanban_store(req))

    guide_content = body.pop("guide_content", "")
    guide_file = body.get("guide_file", "")
    if guide_content and guide_file:
        ws = mgr.get(name)
        if ws:
            filepath = _safe_workspace_path(str(ws.workspace), guide_file)
            if filepath is None:
                return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(guide_content)

    result = mgr.update_agent(name, agent_name, body)
    if result is None:
        return JSONResponse(content={"detail": "Agent or workshop not found"}, status_code=404)
    agents = mgr.list_agents(name)
    updated = next((a for a in agents if a["name"] == agent_name), {}) if agents else {}
    return JSONResponse(content=updated)


@router.delete("/workshops/{name}/agents/{agent_name}", dependencies=[Depends(require_auth)])
async def delete_workshop_agent(name: str, agent_name: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    deleted = mgr.remove_agent(name, agent_name)
    if not deleted:
        return JSONResponse(content={"detail": "Agent or workshop not found"}, status_code=404)
    return JSONResponse(content={"deleted": agent_name})


# ── Workflow Execution ──


@router.post("/workshops/{name}/run", dependencies=[Depends(require_auth)])
async def run_workflow(name: str, request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.workflow.engine import WorkflowRunner

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    ws = mgr.get(name)
    if ws is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
    body = await request.json()
    workflow_name = body.get("workflow", "")
    task = body.get("task", "")
    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)
    tmpl = _org(request).workflow_store.load(workflow_name) if workflow_name else None
    if tmpl is None:
        return JSONResponse(content={"detail": f"Unknown workflow: {workflow_name}"}, status_code=404)
    runner = WorkflowRunner(ws)
    result = await runner.run(tmpl, task)
    return JSONResponse(content={
        "status": result.status.value,
        "template_name": result.template_name,
        "node_results": {
            nid: {
                "node_id": nr.node_id, "agent_name": nr.agent_name,
                "status": nr.status.value, "output": nr.output[:500], "error": nr.error,
            }
            for nid, nr in result.node_results.items()
        },
        "final_output": result.final_output[:2000],
    })


# ── Workshop Bridge ──


@router.get("/workshops/{name}/files/{filename:path}", dependencies=[Depends(require_auth)])
async def read_workshop_file(name: str, filename: str, request: Request):
    from factory.workshop.manager import WorkshopManager

    mgr = WorkshopManager(_org(request), _kanban_store(request))
    ws = mgr.get(name)
    if ws is None:
        return JSONResponse(content={"detail": "Workshop not found"}, status_code=404)
    raw_path = os.path.join(str(ws.workspace), filename)
    filepath = os.path.realpath(raw_path)
    workspace_root = os.path.realpath(str(ws.workspace))
    if not filepath.startswith(workspace_root + os.sep) and filepath != workspace_root:
        return JSONResponse(content={"detail": "Forbidden"}, status_code=403)
    if not os.path.isfile(filepath):
        return JSONResponse(content={"detail": "File not found"}, status_code=404)
    with open(filepath, encoding="utf-8") as f:
        content = f.read()
    return JSONResponse(content={"filename": filename, "content": content})


@router.get("/workshops/{name}/products")
async def list_workshop_products(name: str, request: Request):
    from factory.workshop.bridge import WorkshopBridge

    bridge = WorkshopBridge(_org(request).warehouse)
    products = bridge.list_peer_products(name)
    return JSONResponse(content={"workshop": name, "products": products})


@router.get("/workshops/{name}/bridge/{peer}")
async def get_peer_products(name: str, peer: str, request: Request):
    from factory.workshop.bridge import WorkshopBridge

    bridge = WorkshopBridge(_org(request).warehouse)
    products = bridge.list_peer_products(peer)
    return JSONResponse(content={"from": name, "peer": peer, "products": products})


# ── Org Status ──


@router.get("/org/status")
async def org_status(request: Request):
    status = _org(request).status()
    return JSONResponse(content=status)

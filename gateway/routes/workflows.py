from __future__ import annotations
"""Workflow CRUD and execution endpoints."""


import asyncio
import json
import logging

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel

from gateway.auth import require_auth

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["workflows"])


class ExecuteWorkflowRequest(BaseModel):
    task: str
    workshop: str = ""


def _org(request: Request):
    return request.app.state.org


def _kanban_store(request: Request):
    return request.app.state.kanban_store


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/workflows", dependencies=[Depends(require_auth)])
async def list_workflows(request: Request):
    return JSONResponse(content=_org(request).workflow_store.list_all())


@router.get("/workflows/{name}", dependencies=[Depends(require_auth)])
async def get_workflow(name: str, request: Request):
    tmpl = _org(request).workflow_store.load(name)
    if tmpl is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=tmpl.to_dict())


@router.post("/workflows", dependencies=[Depends(require_auth)])
async def save_workflow(body: dict = Body(...), request: Request = None):  # type: ignore[assignment]
    from factory.workflow.models import WorkflowNode, WorkflowTemplate

    nodes = [WorkflowNode.from_dict(n) for n in body.get("nodes", [])]
    tmpl = WorkflowTemplate(
        name=body["name"],
        description=body.get("description", ""),
        workspace=body.get("workspace", ""),
        nodes=nodes,
    )
    org = _org(request) if request and hasattr(request, "app") else None
    path = org.workflow_store.save(tmpl) if org else ""
    return JSONResponse(content={"saved": str(path), **tmpl.to_dict()})


@router.delete("/workflows/{name}", dependencies=[Depends(require_auth)])
async def delete_workflow(name: str, request: Request):
    deleted = _org(request).workflow_store.delete(name)
    if not deleted:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})


@router.post("/workflows/{name}/execute", dependencies=[Depends(require_auth)])
async def execute_workflow_stream(name: str, body: ExecuteWorkflowRequest, request: Request):
    from factory.workshop.manager import WorkshopManager
    from factory.workflow.engine import WorkflowRunner

    task = body.task.strip()
    workshop_name = body.workshop

    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)

    org = _org(request)
    tmpl = org.workflow_store.load(name)
    if tmpl is None:
        return JSONResponse(content={"detail": f"Workflow not found: {name}"}, status_code=404)

    mgr = WorkshopManager(org, _kanban_store(request))
    ws = mgr.get(workshop_name) if workshop_name else None
    if ws is None:
        return JSONResponse(content={"detail": f"Workshop not found: {workshop_name}"}, status_code=404)

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def on_status(node_id: str, status: str, detail: str) -> None:
        try:
            queue.put_nowait(("node_status", {"node_id": node_id, "status": status, "detail": detail[:500]}))
        except asyncio.QueueFull:
            pass  # drop event if consumer is too slow

    runner = WorkflowRunner(ws, store=org.workflow_store, on_status=on_status)

    async def event_stream():
        yield _sse("started", {"template": name, "task": task[:200], "workshop": workshop_name})

        run_task = asyncio.ensure_future(runner.run(tmpl, task))

        while True:
            try:
                event, data = await asyncio.wait_for(queue.get(), timeout=0.1)
                yield _sse(event, data)
            except asyncio.TimeoutError:
                if run_task.done():
                    break

        try:
            result = run_task.result()
            yield _sse("completed", {
                "status": result.status.value,
                "template_name": result.template_name,
                "node_results": {
                    nid: {
                        "node_id": nr.node_id, "agent_name": nr.agent_name,
                        "status": nr.status.value, "output": nr.output[:500], "error": nr.error,
                    }
                    for nid, nr in result.node_results.items()
                },
                "final_output": result.final_output[:3000],
            })
        except Exception:
            logger.exception("Workflow run SSE failed")
            yield _sse("error", {"message": "An internal error occurred. Please try again."})
        finally:
            if not run_task.done():
                run_task.cancel()
                try:
                    await run_task
                except asyncio.CancelledError:
                    pass

        yield _sse("done", {})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )

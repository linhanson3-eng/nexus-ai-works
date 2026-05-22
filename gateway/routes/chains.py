"""Cross-workshop Chain CRUD and execution endpoints."""

from __future__ import annotations

import asyncio
import json

from fastapi import APIRouter, Body, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse

from gateway.auth import require_auth

router = APIRouter(prefix="/api", tags=["chains"])


def _org(request: Request):
    return request.app.state.org


def _kanban_store(request: Request):
    return request.app.state.kanban_store


def _chain_store(request: Request):
    return request.app.state.chain_store


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@router.get("/chains")
async def list_chains(request: Request):
    return JSONResponse(content=_chain_store(request).list_all())


@router.get("/chains/{name}")
async def get_chain(name: str, request: Request):
    chain = _chain_store(request).load(name)
    if chain is None:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=chain.to_dict())


@router.post("/chains", dependencies=[Depends(require_auth)])
async def save_chain(body: dict = Body(...), request: Request = None):  # type: ignore[assignment]
    from factory.workflow.chain import Chain, ChainStep

    steps = [ChainStep.from_dict(s) for s in body.get("steps", [])]
    chain = Chain(
        name=body["name"],
        description=body.get("description", ""),
        steps=steps,
    )
    store = _chain_store(request) if request and hasattr(request, "app") else None
    path = store.save(chain) if store else ""
    return JSONResponse(content={"saved": str(path), **chain.to_dict()})


@router.delete("/chains/{name}", dependencies=[Depends(require_auth)])
async def delete_chain(name: str, request: Request):
    deleted = _chain_store(request).delete(name)
    if not deleted:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content={"deleted": name})


@router.post("/chains/{name}/execute", dependencies=[Depends(require_auth)])
async def execute_chain_stream(name: str, request: Request):
    from factory.workflow.chain import ChainRunner

    chain = _chain_store(request).load(name)
    if chain is None:
        return JSONResponse(content={"detail": f"Chain not found: {name}"}, status_code=404)

    body = await request.json()
    task = body.get("task", "").strip()
    if not task:
        return JSONResponse(content={"detail": "task is required"}, status_code=400)

    queue: asyncio.Queue = asyncio.Queue(maxsize=100)

    async def on_status(event: str, target: str, detail: str) -> None:
        try:
            queue.put_nowait((event, {"target": target, "detail": detail[:500]}))
        except asyncio.QueueFull:
            pass  # drop event if consumer is too slow

    runner = ChainRunner(_org(request), _kanban_store(request), on_status=on_status)

    async def event_stream():
        yield _sse("started", {
            "chain": name, "task": task[:200],
            "steps": [s.workshop for s in chain.steps],
        })

        run_task = asyncio.ensure_future(runner.run(chain, task))

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
                "status": result.status,
                "chain_name": result.chain_name,
                "step_results": result.step_results,
                "final_output": result.final_output[:3000],
            })
        except Exception as exc:
            yield _sse("error", {"message": str(exc)})
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

"""Kanban Board, List, and Card CRUD endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse

from gateway.auth import require_auth

router = APIRouter(prefix="/api", tags=["kanban"])


def _kanban_store(request: Request):
    return request.app.state.kanban_store


def _ws_manager(request: Request):
    return request.app.state.ws_manager


# ── Board CRUD ──


@router.post("/boards", dependencies=[Depends(require_auth)])
async def create_board(request: Request):
    body = await request.json()
    store = _kanban_store(request)
    board = store.create_board(
        name=body.get("name", "Untitled Board"),
        workshop_name=body.get("workshop_name", ""),
        description=body.get("description", ""),
    )
    return JSONResponse(
        content={
            "id": board.id,
            "name": board.name,
            "workshop_name": board.workshop_name,
            "description": board.description,
            "created_at": board.created_at,
            "updated_at": board.updated_at,
        },
        status_code=201,
    )


@router.get("/boards")
async def list_boards(request: Request):
    workshop_name = request.query_params.get("workshop_name", "")
    boards = _kanban_store(request).list_boards(workshop_name)
    return JSONResponse(content=boards)


@router.get("/boards/{board_id}")
async def get_board(board_id: str, request: Request):
    full = _kanban_store(request).get_board_full(board_id)
    if not full:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=full)


@router.delete("/boards/{board_id}", dependencies=[Depends(require_auth)])
async def delete_board(board_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_board(board_id)
    if not existing:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    store.delete_board(board_id)
    return JSONResponse(content={"deleted": board_id})


# ── List CRUD ──


@router.post("/boards/{board_id}/lists", dependencies=[Depends(require_auth)])
async def create_list(board_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_board(board_id)
    if not existing:
        return JSONResponse(content={"detail": "Board not found"}, status_code=404)
    body = await request.json()
    lst = store.create_list(
        board_id,
        body.get("name", "Untitled List"),
        position=body.get("position", -1),
        color=body.get("color", ""),
    )
    await _ws_manager(request).broadcast(board_id, "list_created", {"id": lst.id, "name": lst.name})
    return JSONResponse(
        content={
            "id": lst.id,
            "board_id": lst.board_id,
            "name": lst.name,
            "position": lst.position,
            "color": lst.color,
        },
        status_code=201,
    )


@router.get("/boards/{board_id}/lists")
async def get_lists(board_id: str, request: Request):
    lists = _kanban_store(request).get_lists(board_id)
    return JSONResponse(content=lists)


@router.put("/lists/{list_id}/move", dependencies=[Depends(require_auth)])
async def move_list(list_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_list(list_id)
    if not existing:
        return JSONResponse(content={"detail": "List not found"}, status_code=404)
    body = await request.json()
    new_position = body.get("position", 0)
    store.move_list(list_id, new_position)
    board_id = existing["board_id"]
    await _ws_manager(request).broadcast(board_id, "list_moved", {"id": list_id, "position": new_position})
    return JSONResponse(content={"id": list_id, "position": new_position})


@router.delete("/lists/{list_id}", dependencies=[Depends(require_auth)])
async def delete_list(list_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_list(list_id)
    if not existing:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    board_id = existing["board_id"]
    store.delete_list(list_id)
    await _ws_manager(request).broadcast(board_id, "list_deleted", {"id": list_id})
    return JSONResponse(content={"deleted": list_id})


# ── Card CRUD ──


@router.post("/lists/{list_id}/cards", dependencies=[Depends(require_auth)])
async def create_card(list_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_list(list_id)
    if not existing:
        return JSONResponse(content={"detail": "List not found"}, status_code=404)
    body = await request.json()
    card = store.create_card(
        list_id=list_id,
        title=body.get("title", ""),
        description=body.get("description", ""),
        position=body.get("position", -1),
        labels=body.get("labels"),
        assignee=body.get("assignee", ""),
        due_date=body.get("due_date"),
        source_agent=body.get("source_agent", ""),
        source_task_id=body.get("source_task_id", ""),
        task_status=body.get("task_status", "todo"),
    )
    board_id = existing["board_id"]
    payload = {
        "id": card.id,
        "list_id": card.list_id,
        "title": card.title,
        "description": card.description,
        "position": card.position,
        "labels": list(card.labels),
        "assignee": card.assignee,
        "due_date": card.due_date,
        "task_status": card.task_status,
        "source_agent": card.source_agent,
        "source_task_id": card.source_task_id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }
    await _ws_manager(request).broadcast(board_id, "card_created", payload)
    return JSONResponse(content=payload, status_code=201)


@router.get("/lists/{list_id}/cards")
async def get_cards(list_id: str, request: Request):
    cards = _kanban_store(request).get_cards(list_id)
    return JSONResponse(content=cards)


@router.get("/cards/{card_id}")
async def get_card(card_id: str, request: Request):
    card = _kanban_store(request).get_card(card_id)
    if not card:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    return JSONResponse(content=card)


@router.put("/cards/{card_id}", dependencies=[Depends(require_auth)])
async def update_card(card_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_card(card_id)
    if not existing:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    body = await request.json()
    store.update_card(card_id, **body)
    updated = store.get_card(card_id)
    list_info = store.get_list(existing["list_id"])
    if list_info:
        await _ws_manager(request).broadcast(list_info["board_id"], "card_updated", updated)
    return JSONResponse(content=updated)


@router.put("/cards/{card_id}/move", dependencies=[Depends(require_auth)])
async def move_card(card_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_card(card_id)
    if not existing:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    body = await request.json()
    target_list_id = body.get("list_id", "")
    position = body.get("position", -1)
    if not target_list_id:
        return JSONResponse(content={"detail": "list_id required"}, status_code=400)
    store.move_card(card_id, target_list_id, position=position)
    moved = store.get_card(card_id)
    list_info = store.get_list(target_list_id)
    if list_info:
        await _ws_manager(request).broadcast(list_info["board_id"], "card_moved", moved)
    return JSONResponse(content=moved)


@router.delete("/cards/{card_id}", dependencies=[Depends(require_auth)])
async def delete_card(card_id: str, request: Request):
    store = _kanban_store(request)
    existing = store.get_card(card_id)
    if not existing:
        return JSONResponse(content={"detail": "Not found"}, status_code=404)
    list_info = store.get_list(existing["list_id"])
    store.delete_card(card_id)
    if list_info:
        await _ws_manager(request).broadcast(list_info["board_id"], "card_deleted", {"id": card_id})
    return JSONResponse(content={"deleted": card_id})


# ── Agent Sync ──


@router.get("/cards/agent/{agent_name}")
async def get_cards_by_agent(agent_name: str, request: Request):
    cards = _kanban_store(request).get_cards_by_agent(agent_name)
    return JSONResponse(content=cards)


@router.post("/cards/upsert-from-task", dependencies=[Depends(require_auth)])
async def upsert_card_from_task(request: Request):
    body = await request.json()
    store = _kanban_store(request)
    card = store.upsert_card_from_task(
        agent_name=body.get("agent_name", ""),
        task_id=body.get("task_id", ""),
        title=body.get("title", ""),
        status=body.get("task_status", "todo"),
        list_id=body.get("list_id", ""),
    )
    payload = {
        "id": card.id,
        "list_id": card.list_id,
        "title": card.title,
        "description": card.description,
        "position": card.position,
        "labels": list(card.labels),
        "assignee": card.assignee,
        "due_date": card.due_date,
        "task_status": card.task_status,
        "source_agent": card.source_agent,
        "source_task_id": card.source_task_id,
        "created_at": card.created_at,
        "updated_at": card.updated_at,
    }
    return JSONResponse(content=payload)

"""WebSocket endpoint for real-time kanban updates."""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/boards/{board_id}")
async def ws_board(ws: WebSocket, board_id: str):
    """Clients connect to /ws/boards/{board_id} for real-time kanban updates."""
    manager = ws.app.state.ws_manager
    await manager.connect(board_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(board_id, ws)

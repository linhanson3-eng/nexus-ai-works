from __future__ import annotations
"""WebSocket endpoint for real-time kanban updates."""


from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/boards/{board_id}")
async def ws_board(ws: WebSocket, board_id: str):
    """Clients connect to /ws/boards/{board_id} for real-time kanban updates."""
    # Authenticate via token query param or Authorization header
    from gateway.auth import verify_token
    token = ws.query_params.get("token") or ""
    if not token:
        # Try from sec-websocket-protocol header (common workaround)
        protocols = ws.headers.get("sec-websocket-protocol", "").split(",")
        token = next((p.strip() for p in protocols if p.strip().startswith("auth.")), "")
        token = token.removeprefix("auth.") if token else ""
    try:
        verify_token(token)
    except Exception:
        await ws.close(code=4001, reason="Unauthorized")
        return

    manager = ws.app.state.ws_manager
    await manager.connect(board_id, ws)
    try:
        while True:
            data = await ws.receive_text()
            if data == "ping":
                await ws.send_text("pong")
    except WebSocketDisconnect:
        manager.disconnect(board_id, ws)

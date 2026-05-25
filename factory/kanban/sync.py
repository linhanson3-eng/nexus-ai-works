from __future__ import annotations
"""Agent task — Kanban card auto-sync bridge."""


from dataclasses import dataclass
from typing import Callable, Awaitable

from factory.kanban.store import KanbanStore, KanbanCard


@dataclass
class TaskEvent:
    agent_name: str
    task_id: str
    event_type: str  # "task_started" | "task_progress" | "task_completed" | "task_blocked" | "task_failed"
    title: str = ""
    detail: str = ""
    timestamp: str = ""
    output_full: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    tools_used: list[str] | None = None
    model: str = ""


class KanbanSync:
    """Auto-syncs agent task events to kanban cards.

    Hooks into FactoryAgentRunner to detect task state changes
    and propagate them to the kanban board.
    """

    STATUS_TO_LIST: dict[str, str] = {
        "todo": "执行中",
        "task_started": "执行中",
        "in_progress": "执行中",
        "task_progress": "执行中",
        "done": "已完成",
        "task_completed": "已完成",
        "blocked": "需关注",
        "task_failed": "需关注",
        "paused": "已暂停",
        "task_paused": "已暂停",
    }

    LIST_TO_STATUS: dict[str, str] = {
        "执行中": "in_progress",
        "已完成": "done",
        "需关注": "blocked",
        "已暂停": "paused",
    }

    def __init__(
        self, store: KanbanStore, workshop_name: str, board_id: str | None = None,
    ):
        self.store = store
        self.workshop = workshop_name
        self.board_id = board_id
        self._list_ids: dict[str, str] = {}  # list_name -> list_id cache
        self._listeners: list[Callable[[TaskEvent], Awaitable[None]]] = []

    async def ensure_board(self) -> str:
        """Get or create the kanban board for this workshop."""
        if self.board_id:
            return self.board_id
        board = self.store.get_board_by_name(self.workshop, self.workshop)
        if board:
            self.board_id = board["id"]
            return self.board_id
        board_obj = self.store.create_board(
            name=self.workshop, workshop_name=self.workshop,
            description=f"Kanban board for workshop: {self.workshop}",
        )
        self.board_id = board_obj.id
        # Create default lists
        for list_name in ["执行中", "已完成", "需关注", "已暂停"]:
            lst = self.store.create_list(self.board_id, list_name)
            self._list_ids[list_name] = lst.id
        return self.board_id

    async def _ensure_list(self, list_name: str) -> str:
        if list_name in self._list_ids:
            return self._list_ids[list_name]
        await self.ensure_board()
        existing = self.store.get_lists(self.board_id)
        for lst in existing:
            self._list_ids[lst["name"]] = lst["id"]
        if list_name in self._list_ids:
            return self._list_ids[list_name]
        lst = self.store.create_list(self.board_id, list_name)
        self._list_ids[list_name] = lst.id
        return lst.id

    async def on_task_event(self, event: TaskEvent) -> KanbanCard | None:
        """Main entry point. Creates or updates a kanban card from a task event."""
        await self.ensure_board()
        list_name = self.STATUS_TO_LIST.get(event.event_type, "执行中")
        status = self.LIST_TO_STATUS.get(list_name, "todo")
        list_id = await self._ensure_list(list_name)

        # Build description from execution metadata
        import json
        desc_parts = []
        if event.output_full:
            desc_parts.append(event.output_full)
        elif event.detail:
            desc_parts.append(event.detail)
        if event.turns or event.cost_usd or event.tools_used:
            meta = {
                "turns": event.turns,
                "cost_usd": event.cost_usd,
                "tools_used": event.tools_used or [],
                "model": event.model,
            }
            desc_parts.append("__META__" + json.dumps(meta, ensure_ascii=False))
        description = "\n".join(desc_parts) if desc_parts else ""

        card = self.store.upsert_card_from_task(
            agent_name=event.agent_name, task_id=event.task_id,
            title=event.title[:200], status=status, list_id=list_id,
        )
        # Update description with full output + metadata
        if description:
            self.store.update_card(card.id, description=description)
        await self._notify(event)
        return card

    def add_listener(self, callback: Callable[[TaskEvent], Awaitable[None]]) -> None:
        self._listeners.append(callback)

    async def _notify(self, event: TaskEvent) -> None:
        for cb in self._listeners:
            try:
                await cb(event)
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Kanban listener failed: %s", e)

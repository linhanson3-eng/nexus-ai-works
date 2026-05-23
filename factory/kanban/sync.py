"""Agent task — Kanban card auto-sync bridge."""

from __future__ import annotations

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


class KanbanSync:
    """Auto-syncs agent task events to kanban cards.

    Hooks into FactoryAgentRunner to detect task state changes
    and propagate them to the kanban board.
    """

    STATUS_TO_LIST: dict[str, str] = {
        "todo": "To Do",
        "task_started": "To Do",
        "in_progress": "In Progress",
        "task_progress": "In Progress",
        "done": "Done",
        "task_completed": "Done",
        "blocked": "Blocked",
        "task_failed": "Blocked",
    }

    LIST_TO_STATUS: dict[str, str] = {
        "To Do": "todo",
        "In Progress": "in_progress",
        "Done": "done",
        "Blocked": "blocked",
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
        for list_name in ["To Do", "In Progress", "Done", "Blocked"]:
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
        list_name = self.STATUS_TO_LIST.get(event.event_type, "To Do")
        status = self.LIST_TO_STATUS.get(list_name, "todo")
        list_id = await self._ensure_list(list_name)
        card = self.store.upsert_card_from_task(
            agent_name=event.agent_name, task_id=event.task_id,
            title=event.title[:200], status=status, list_id=list_id,
        )
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

from __future__ import annotations
"""Kanban Store and Sync layer tests."""


import tempfile
from pathlib import Path

import pytest

from factory.kanban.store import KanbanStore
from factory.kanban.sync import KanbanSync, TaskEvent


@pytest.fixture
def store():
    with tempfile.TemporaryDirectory() as tmp:
        s = KanbanStore(Path(tmp) / "test_kanban.db")
        yield s
        s.close()


@pytest.fixture
def board_id(store):
    board = store.create_board("Test Board", "test-workshop", "A test board")
    return board.id


def _create_default_board(store):
    return store.create_board("Test Board", "test-workshop", "A test board")


def _create_default_list(store, board_id, name="执行中"):
    return store.create_list(board_id, name)


class TestBoardCRUD:
    def test_create_board(self, store):
        board = store.create_board("My Board", "ws1", "Desc")
        assert board.name == "My Board"
        assert board.workshop_name == "ws1"
        assert board.description == "Desc"
        assert board.id != ""
        assert board.created_at != ""
        assert board.updated_at != ""

    def test_get_board(self, store, board_id):
        board = store.get_board(board_id)
        assert board is not None
        assert board["name"] == "Test Board"
        assert board["workshop_name"] == "test-workshop"

    def test_get_board_nonexistent(self, store):
        assert store.get_board("nonexistent") is None

    def test_get_board_by_name(self, store):
        store.create_board("Unique Board", "ws1")
        found = store.get_board_by_name("Unique Board", "ws1")
        assert found is not None
        assert found["name"] == "Unique Board"

    def test_get_board_by_name_not_found(self, store):
        assert store.get_board_by_name("NoSuch", "ws1") is None

    def test_list_boards(self, store):
        store.create_board("B1", "ws1")
        store.create_board("B2", "ws1")
        store.create_board("B3", "ws2")
        all_boards = store.list_boards()
        assert len(all_boards) >= 3
        ws1_boards = store.list_boards("ws1")
        assert len(ws1_boards) == 2

    def test_delete_board(self, store, board_id):
        store.delete_board(board_id)
        assert store.get_board(board_id) is None

    def test_delete_board_cascades(self, store, board_id):
        list_obj = store.create_list(board_id, "To Do")
        store.create_card(list_obj.id, "Card 1")
        store.delete_board(board_id)
        assert store.get_board(board_id) is None
        assert store.get_list(list_obj.id) is None


class TestListCRUD:
    def test_create_list(self, store, board_id):
        lst = store.create_list(board_id, "In Progress")
        assert lst.name == "In Progress"
        assert lst.board_id == board_id
        assert lst.position == 0
        assert lst.id != ""

    def test_create_list_auto_position(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "In Progress")
        assert l1.position == 0
        assert l2.position == 1

    def test_create_list_explicit_position(self, store, board_id):
        lst = store.create_list(board_id, "Done", position=5)
        assert lst.position == 5

    def test_get_list(self, store, board_id):
        lst = store.create_list(board_id, "Backlog")
        fetched = store.get_list(lst.id)
        assert fetched is not None
        assert fetched["name"] == "Backlog"

    def test_get_list_nonexistent(self, store):
        assert store.get_list("nonexistent") is None

    def test_get_lists(self, store, board_id):
        store.create_list(board_id, "To Do")
        store.create_list(board_id, "In Progress")
        store.create_list(board_id, "Done")
        lists = store.get_lists(board_id)
        assert len(lists) == 3
        assert lists[0]["name"] == "To Do"
        assert lists[1]["name"] == "In Progress"
        assert lists[2]["name"] == "Done"

    def test_move_list(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "In Progress")
        store.move_list(l1.id, 5)
        moved = store.get_list(l1.id)
        assert moved["position"] == 5

    def test_delete_list(self, store, board_id):
        lst = store.create_list(board_id, "Temp")
        store.delete_list(lst.id)
        assert store.get_list(lst.id) is None

    def test_delete_list_cascades(self, store, board_id):
        lst = store.create_list(board_id, "Temp")
        card = store.create_card(lst.id, "Card")
        store.delete_list(lst.id)
        assert store.get_list(lst.id) is None
        assert store.get_card(card.id) is None


class TestCardCRUD:
    def test_create_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(lst.id, "Fix login bug")
        assert card.title == "Fix login bug"
        assert card.list_id == lst.id
        assert card.task_status == "todo"
        assert card.id != ""

    def test_create_card_auto_position(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        c1 = store.create_card(lst.id, "Card 1")
        c2 = store.create_card(lst.id, "Card 2")
        assert c1.position == 0
        assert c2.position == 1

    def test_create_card_with_details(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(
            lst.id, "Complex task", description="Detailed desc",
            labels=["bug", "urgent"], assignee="agent-1",
            due_date="2026-06-01", task_status="in_progress",
            source_agent="builder", source_task_id="task-001",
        )
        assert card.description == "Detailed desc"
        assert card.labels == ("bug", "urgent")
        assert card.assignee == "agent-1"
        assert card.due_date == "2026-06-01"
        assert card.task_status == "in_progress"
        assert card.source_agent == "builder"
        assert card.source_task_id == "task-001"

    def test_get_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(lst.id, "A card")
        fetched = store.get_card(card.id)
        assert fetched is not None
        assert fetched["title"] == "A card"

    def test_get_card_nonexistent(self, store):
        assert store.get_card("nonexistent") is None

    def test_get_cards(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        store.create_card(lst.id, "C1")
        store.create_card(lst.id, "C2")
        store.create_card(lst.id, "C3")
        cards = store.get_cards(lst.id)
        assert len(cards) == 3

    def test_update_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(lst.id, "Old title")
        store.update_card(card.id, title="New title", task_status="done")
        updated = store.get_card(card.id)
        assert updated["title"] == "New title"
        assert updated["task_status"] == "done"

    def test_update_card_empty_fields(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(lst.id, "Title")
        store.update_card(card.id)
        fetched = store.get_card(card.id)
        assert fetched["title"] == "Title"

    def test_move_card(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "Done")
        card = store.create_card(l1.id, "Movable")
        store.move_card(card.id, l2.id)
        moved = store.get_card(card.id)
        assert moved["list_id"] == l2.id

    def test_move_card_with_position(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "Done")
        card = store.create_card(l1.id, "Movable")
        store.move_card(card.id, l2.id, position=3)
        moved = store.get_card(card.id)
        assert moved["list_id"] == l2.id
        assert moved["position"] == 3

    def test_delete_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.create_card(lst.id, "Delete me")
        store.delete_card(card.id)
        assert store.get_card(card.id) is None


class TestAgentSync:
    def test_upsert_creates_new_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        card = store.upsert_card_from_task(
            "builder", "task-001", "Build login", status="todo", list_id=lst.id,
        )
        assert card.title == "Build login"
        assert card.source_agent == "builder"
        assert card.source_task_id == "task-001"

    def test_upsert_updates_existing_card(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        store.create_card(
            lst.id, "Old title", source_agent="builder", source_task_id="task-001",
        )
        card = store.upsert_card_from_task(
            "builder", "task-001", "Updated title", status="done", list_id=lst.id,
        )
        assert card.title == "Updated title"

    def test_get_cards_by_agent(self, store, board_id):
        lst = store.create_list(board_id, "To Do")
        store.create_card(
            lst.id, "C1", source_agent="agent-a", source_task_id="t1",
        )
        store.create_card(
            lst.id, "C2", source_agent="agent-b", source_task_id="t2",
        )
        store.create_card(
            lst.id, "C3", source_agent="agent-a", source_task_id="t3",
        )
        cards = store.get_cards_by_agent("agent-a")
        assert len(cards) == 2

    def test_get_cards_by_agent_none(self, store):
        assert store.get_cards_by_agent("unknown") == []

    def test_get_cards_by_status(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "Done")
        store.create_card(l1.id, "C1", task_status="todo")
        store.create_card(l1.id, "C2", task_status="in_progress")
        store.create_card(l2.id, "C3", task_status="done")
        done_cards = store.get_cards_by_status(board_id, "done")
        assert len(done_cards) == 1
        assert done_cards[0]["title"] == "C3"


class TestBoardFull:
    def test_get_board_full(self, store, board_id):
        l1 = store.create_list(board_id, "To Do")
        l2 = store.create_list(board_id, "In Progress")
        store.create_card(l1.id, "Card A")
        store.create_card(l1.id, "Card B")
        store.create_card(l2.id, "Card C")
        full = store.get_board_full(board_id)
        assert full["name"] == "Test Board"
        assert len(full["lists"]) == 2
        assert len(full["lists"][0]["cards"]) == 2
        assert len(full["lists"][1]["cards"]) == 1

    def test_get_board_full_nonexistent(self, store):
        assert store.get_board_full("nonexistent") == {}


class TestKanbanSync:
    @pytest.fixture
    def sync_store(self):
        with tempfile.TemporaryDirectory() as tmp:
            s = KanbanStore(Path(tmp) / "test_sync.db")
            yield s
            s.close()

    def test_ensure_board_creates_new(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        # We need to run the async method synchronously
        import asyncio
        board_id = asyncio.run(sync.ensure_board())
        assert board_id != ""
        board = sync_store.get_board(board_id)
        assert board is not None
        assert board["workshop_name"] == "workshop-a"
        lists = sync_store.get_lists(board_id)
        assert len(lists) == 4
        list_names = {l["name"] for l in lists}
        assert list_names == {"执行中", "已完成", "需关注", "已暂停"}

    def test_ensure_board_returns_existing(self, sync_store):
        existing = sync_store.create_board("workshop-a", "workshop-a")
        sync = KanbanSync(sync_store, "workshop-a")
        import asyncio
        board_id = asyncio.run(sync.ensure_board())
        assert board_id == existing.id

    def test_ensure_board_reuses_cached_board_id(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        import asyncio
        first = asyncio.run(sync.ensure_board())
        second = asyncio.run(sync.ensure_board())
        assert first == second

    @pytest.mark.asyncio
    async def test_on_task_event_creates_card(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        event = TaskEvent(
            agent_name="builder", task_id="task-1",
            event_type="task_started", title="Build something",
        )
        card = await sync.on_task_event(event)
        assert card is not None
        assert card.title == "Build something"
        assert card.source_agent == "builder"

    @pytest.mark.asyncio
    async def test_on_task_event_updates_card(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        await sync.ensure_board()
        list_id = await sync._ensure_list("执行中")
        sync_store.create_card(
            list_id, "Old", source_agent="builder", source_task_id="task-1",
        )
        event = TaskEvent(
            agent_name="builder", task_id="task-1",
            event_type="task_completed", title="Done",
        )
        card = await sync.on_task_event(event)
        assert card is not None
        assert card.title == "Done"

    @pytest.mark.asyncio
    async def test_on_task_event_maps_status(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        cases = [
            ("task_started", "执行中"),
            ("task_progress", "执行中"),
            ("task_completed", "已完成"),
            ("task_failed", "需关注"),
        ]
        for event_type, expected_list in cases:
            event = TaskEvent(
                agent_name="agent", task_id=f"task-{event_type}",
                event_type=event_type, title=f"Task {event_type}",
            )
            card = await sync.on_task_event(event)
            fetched = sync_store.get_card(card.id)
            list_row = sync_store.get_list(fetched["list_id"])
            assert list_row["name"] == expected_list, (
                f"Expected {expected_list} for {event_type}, got {list_row['name']}"
            )

    @pytest.mark.asyncio
    async def test_on_task_event_unknown_event_type(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        event = TaskEvent(
            agent_name="agent", task_id="task-x",
            event_type="unknown_type", title="Mystery task",
        )
        card = await sync.on_task_event(event)
        assert card is not None
        fetched = sync_store.get_card(card.id)
        list_row = sync_store.get_list(fetched["list_id"])
        assert list_row["name"] == "执行中"

    @pytest.mark.asyncio
    async def test_listener_notification(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        received: list[TaskEvent] = []

        async def callback(event: TaskEvent) -> None:
            received.append(event)

        sync.add_listener(callback)
        event = TaskEvent(
            agent_name="builder", task_id="task-1",
            event_type="task_started", title="Notify test",
        )
        await sync.on_task_event(event)
        assert len(received) == 1
        assert received[0].title == "Notify test"

    @pytest.mark.asyncio
    async def test_title_truncation(self, sync_store):
        sync = KanbanSync(sync_store, "workshop-a")
        long_title = "A" * 500
        event = TaskEvent(
            agent_name="agent", task_id="task-1",
            event_type="task_started", title=long_title,
        )
        card = await sync.on_task_event(event)
        assert len(card.title) <= 200

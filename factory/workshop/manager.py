"""Workshop lifecycle manager — runtime create, list, get, delete workshops."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.schema import DepartmentSpec, AgentSpec, WorkflowSpec
from factory.org import OrgEngine, Workshop


@dataclass
class WorkshopInfo:
    """Lightweight workshop metadata for listing (does NOT load full state)."""

    name: str
    workspace: str
    agent_count: int
    super_agents: list[str]
    workflow_name: str
    has_kanban: bool = False


class WorkshopManager:
    """Runtime workshop lifecycle manager.

    Wraps OrgEngine to provide runtime CRUD for workshops without
    needing to edit org.yaml and restart.
    """

    def __init__(self, org: OrgEngine, kanban_store: Any = None):
        self.org = org
        self.kanban_store = kanban_store

    def create(
        self,
        name: str,
        workspace: str = "",
        agent_names: list[str] | None = None,
        workflow_name: str = "simple",
        model: str = "anthropic/claude-sonnet-4-6",
    ) -> Workshop:
        """Create a new workshop at runtime.

        Args:
            name: Workshop name (also used as department name).
            workspace: Path for workspace files (default: workspaces/{name}).
            agent_names: Agent template names to spawn (default: ["super"]).
            workflow_name: Workflow template name.
            model: Default LLM model for agents.
        """
        agents = agent_names or ["super"]
        agent_specs: list[AgentSpec] = []
        for aname in agents:
            spec = self.org.templates.create_agent_spec(
                template_name=aname,
                name=aname,
                model=model,
            )
            agent_specs.append(spec)

        dept_spec = DepartmentSpec(
            name=name,
            workspace=workspace or f"workspaces/{name}",
            agents=agent_specs,
            workflow=WorkflowSpec(name=workflow_name),
        )
        workshop = self.org.create_one(dept_spec)

        # Auto-create kanban board
        if self.kanban_store:
            board = self.kanban_store.create_board(
                name=name,
                workshop_name=name,
                description=f"Kanban board for workshop: {name}",
            )
            for list_name in ["To Do", "In Progress", "Done", "Blocked"]:
                self.kanban_store.create_list(board.id, list_name)

        return workshop

    def get(self, name: str) -> Workshop | None:
        """Get a workshop by name."""
        for ws in self.org.workshops:
            if ws.name == name:
                return ws
        return None

    def list_all(self) -> list[WorkshopInfo]:
        """List all workshops with lightweight metadata."""
        result: list[WorkshopInfo] = []
        for ws in self.org.workshops:
            has_kanban = False
            if self.kanban_store:
                board = self.kanban_store.get_board_by_name(ws.name, ws.name)
                has_kanban = board is not None
            result.append(WorkshopInfo(
                name=ws.name,
                workspace=str(ws.workspace),
                agent_count=ws.agent_count(),
                super_agents=ws.super_agents(),
                workflow_name=ws.workflow_name,
                has_kanban=has_kanban,
            ))
        return result

    def delete(self, name: str) -> bool:
        """Delete a workshop by name.

        Returns:
            True if deleted, False if not found.
        """
        ws = self.get(name)
        if ws is None:
            return False
        # Remove kanban board
        if self.kanban_store:
            board = self.kanban_store.get_board_by_name(name, name)
            if board:
                self.kanban_store.delete_board(board["id"])
        # Remove from org
        self.org.workshops = [w for w in self.org.workshops if w.name != name]
        return True

    def status(self, name: str) -> dict | None:
        """Get detailed status for a workshop."""
        ws = self.get(name)
        if ws is None:
            return None
        info = ws.status()
        if self.kanban_store:
            board = self.kanban_store.get_board_by_name(name, name)
            if board:
                info["kanban_board_id"] = board["id"]
                lists = self.kanban_store.get_lists(board["id"])
                info["kanban_stats"] = {
                    lst["name"]: len(self.kanban_store.get_cards(lst["id"]))
                    for lst in lists
                }
        return info

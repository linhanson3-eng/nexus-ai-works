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
    agent_names: list[str]
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
            agent_names: Agent template names to spawn (default: []).
            workflow_name: Workflow template name.
            model: Default LLM model for agents.
        """
        agents = agent_names or []
        agent_specs: list[AgentSpec] = []
        if not agents:
            spec = AgentSpec(name=name, model=model)
            agent_specs.append(spec)
        else:
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
                agent_names=list(ws.agents.keys()),
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

    # ── Agent CRUD ───────────────────────────────────────────────

    def add_agent(self, workshop_name: str, spec: AgentSpec) -> AgentSpec | None:
        """Add an agent to a workshop at runtime."""
        ws = self.get(workshop_name)
        if ws is None:
            return None
        ws.agents[spec.name] = spec
        if spec.name not in [a.name for a in ws.spec.agents]:
            ws.spec.agents.append(spec)
        return spec

    def update_agent(self, workshop_name: str, agent_name: str, updates: dict) -> AgentSpec | None:
        """Update an existing agent in a workshop."""
        ws = self.get(workshop_name)
        if ws is None:
            return None
        if agent_name not in ws.agents:
            return None

        existing = ws.agents[agent_name]

        # Update scalar fields
        for field in ("mode", "model", "system_prompt", "guide_file", "type"):
            if field in updates:
                setattr(existing, field, updates[field])

        # Update tools
        if "tools" in updates:
            existing.tools = updates["tools"]

        # Update skills
        if "skills" in updates:
            existing.skills = updates["skills"]

        # Update permissions
        if "permissions" in updates:
            perm_updates = updates["permissions"]
            if "file_write" in perm_updates:
                existing.permissions.filesystem.write = (
                    ["workspace"] if perm_updates["file_write"] else []
                )
            if "shell_exec" in perm_updates:
                existing.permissions.shell.exec = perm_updates["shell_exec"]
            if "subagent_spawn" in perm_updates:
                existing.permissions.subagent.spawn = perm_updates["subagent_spawn"]

        # Sync spec list
        for i, a in enumerate(ws.spec.agents):
            if a.name == agent_name:
                ws.spec.agents[i] = existing
                break

        return existing

    def remove_agent(self, workshop_name: str, agent_name: str) -> bool:
        """Remove an agent from a workshop."""
        ws = self.get(workshop_name)
        if ws is None:
            return False
        if agent_name not in ws.agents:
            return False

        del ws.agents[agent_name]
        ws.spec.agents = [a for a in ws.spec.agents if a.name != agent_name]
        return True

    def list_agents(self, workshop_name: str) -> list[dict] | None:
        """List all agents in a workshop with their configuration."""
        ws = self.get(workshop_name)
        if ws is None:
            return None
        return [
            {
                "name": a.name,
                "mode": getattr(a, "mode", "super"),
                "model": a.model,
                "tools": a.tools if a.tools else ["all"],
                "tools_all": len(a.tools) == 0,
                "system_prompt": getattr(a, "system_prompt", ""),
                "guide_file": getattr(a, "guide_file", ""),
                "skills": getattr(a, "skills", []),
                "permissions": {
                    "file_write": len(a.permissions.filesystem.write) > 0,
                    "shell_exec": a.permissions.shell.exec,
                    "subagent_spawn": a.permissions.subagent.spawn,
                },
                "is_super": getattr(a, "is_super", len(a.tools) == 0),
            }
            for a in ws.agents.values()
        ]

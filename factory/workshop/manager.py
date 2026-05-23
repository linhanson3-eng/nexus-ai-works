"""Workshop lifecycle manager — runtime create, list, get, delete workshops."""

from __future__ import annotations

import fcntl
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from config.schema import (
    AgentPermissions,
    AgentSpec,
    DepartmentSpec,
    FilesystemPermission,
    ShellPermission,
    SubagentPermission,
    WorkflowSpec,
)
from factory.org import OrgEngine, Workshop

logger = logging.getLogger(__name__)


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
        model: str = "",
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
                spec = AgentSpec(name=aname, model=model)
                agent_specs.append(spec)

        dept_spec = DepartmentSpec(
            name=name,
            workspace=workspace or f"workspaces/{name}",
            agents=agent_specs,
            workflow=WorkflowSpec(name=workflow_name),
        )
        workshop = self.org.create_one(dept_spec)

        # Persist to org.yaml
        self._persist_org()

        # Auto-create kanban board
        if self.kanban_store:
            board = None
            try:
                board = self.kanban_store.create_board(
                    name=name,
                    workshop_name=name,
                    description=f"Kanban board for workshop: {name}",
                )
                for list_name in ["To Do", "In Progress", "Done", "Blocked"]:
                    self.kanban_store.create_list(board.id, list_name)
            except Exception:
                if board:
                    try:
                        self.kanban_store.delete_board(board.id)
                    except Exception as exc:
                        logger.warning("Failed to clean up board after create failure: %s", exc)
                raise

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
        # Remove all kanban boards for this workshop
        if self.kanban_store:
            boards = self.kanban_store.list_boards(name)
            for b in boards:
                self.kanban_store.delete_board(b["id"])
        # Remove from org (in-memory)
        self.org.workshops = [w for w in self.org.workshops if w.name != name]
        # Remove from org spec
        self.org.spec.departments = [
            d for d in self.org.spec.departments if d.name != name
        ]
        # Persist to disk
        self._persist_org()
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
        self._persist_org()
        return spec

    def update_agent(self, workshop_name: str, agent_name: str, updates: dict) -> AgentSpec | None:
        """Update an existing agent in a workshop."""
        ws = self.get(workshop_name)
        if ws is None:
            return None
        if agent_name not in ws.agents:
            return None

        existing = ws.agents[agent_name]

        # Build updated field values
        new_values: dict[str, object] = {}
        for field in ("mode", "model", "system_prompt", "guide_file", "type"):
            if field in updates:
                new_values[field] = updates[field]
            else:
                new_values[field] = getattr(existing, field)

        new_values["tools"] = updates.get("tools", existing.tools)
        new_values["skills"] = updates.get("skills", existing.skills)
        new_values["permissions"] = existing.permissions

        if "permissions" in updates:
            perm_updates = updates["permissions"]
            fs = existing.permissions.filesystem
            sh = existing.permissions.shell
            sa = existing.permissions.subagent
            new_fs = FilesystemPermission(
                read=fs.read,
                write=["workspace"] if perm_updates.get("file_write") else fs.write,
                forbidden=fs.forbidden,
            )
            new_sh = ShellPermission(
                exec=perm_updates.get("shell_exec", sh.exec),
                network=sh.network,
                forbidden_patterns=sh.forbidden_patterns,
            )
            new_sa = SubagentPermission(
                spawn=perm_updates.get("subagent_spawn", sa.spawn),
                max=sa.max,
            )
            new_values["permissions"] = AgentPermissions(
                filesystem=new_fs,
                shell=new_sh,
                subagent=new_sa,
                warehouse=existing.permissions.warehouse,
                self=existing.permissions.self,
            )

        updated = AgentSpec(**{k: v for k, v in new_values.items() if k in AgentSpec.model_fields})

        # Sync spec list
        ws.agents[agent_name] = updated
        for i, a in enumerate(ws.spec.agents):
            if a.name == agent_name:
                ws.spec.agents[i] = updated
                break

        self._persist_org()
        return updated

    def remove_agent(self, workshop_name: str, agent_name: str) -> bool:
        """Remove an agent from a workshop."""
        ws = self.get(workshop_name)
        if ws is None:
            return False
        if agent_name not in ws.agents:
            return False

        del ws.agents[agent_name]
        ws.spec.agents = [a for a in ws.spec.agents if a.name != agent_name]
        self._persist_org()
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

    # ── Export / Import / Remove ──────────────────────────────────

    def export_workspace(
        self,
        name: str,
        output_dir: str = ".",
        version: str = "1.0.0",
    ) -> str | None:
        """Export a workspace to a .nexus package directory.

        Returns the package directory path, or None if workspace not found.
        """
        from factory.workflow.package import pack_workspace

        ws = self.get(name)
        if ws is None:
            return None

        agents = self.list_agents(name) or []
        wf_store = self.org.workflow_store if self.org.workflow_store else None
        workflows: list[dict[str, Any]] = []
        if wf_store:
            for wf_info in wf_store.list_all():
                tmpl = wf_store.load(wf_info["name"])
                if tmpl and (not tmpl.workspace or tmpl.workspace == name):
                    workflows.append(tmpl.to_dict())

        guide_file = ""
        guide_content = ""
        for a in ws.agents.values():
            gf = getattr(a, "guide_file", "")
            if gf:
                guide_file = str(ws.workspace / gf)
                if Path(guide_file).exists():
                    guide_content = Path(guide_file).read_text("utf-8")
                break

        chain_data = None
        try:
            from factory.workflow.chain import ChainStore
            cs = ChainStore()
            for ci in cs.list_all():
                if name in ci.get("steps", []):
                    c = cs.load(ci["name"])
                    if c:
                        chain_data = c.to_dict()
                    break
        except Exception:
            logger.warning("Failed to load chain for export: %s", name, exc_info=True)

        pkg_dir = pack_workspace(
            workspace_name=name,
            workspace_path=str(ws.workspace),
            agents=agents,
            workflows=workflows,
            guide_file=guide_file,
            guide_content=guide_content,
            chain=chain_data,
            tools_dir=str(ws.workspace / "tools"),
            output_dir=output_dir,
            version=version,
        )
        return str(pkg_dir)

    def import_package(self, pkg_dir: str, custom_name: str = "", *, force: bool = False) -> dict[str, Any] | None:
        """Import a .nexus package, creating a new workspace.

        Args:
            pkg_dir: Path to the .nexus package directory.
            custom_name: Optional custom workspace name (defaults to manifest name).
            force: If True, remove existing workspace before re-importing.

        Returns status dict with created resources.
        """
        from factory.workflow.package import unpack_package

        data = unpack_package(pkg_dir)
        manifest = data["manifest"]
        name = custom_name or manifest["name"]

        # Check if already exists
        if self.get(name) is not None:
            if not force:
                return None
            self.remove_workspace(name)

        # Create agents
        agent_names: list[str] = []
        for agent_data in data["agents"]:
            aname = agent_data.get("name", "")
            if not aname:
                continue
            agent_names.append(aname)

        # Create workshop
        ws = self.create(
            name=name,
            workspace=f"workspaces/{name}",
            agent_names=agent_names,
            workflow_name=data["workflows"][0]["name"] if data["workflows"] else "simple",
        )

        # Apply full agent configs
        for agent_data in data["agents"]:
            aname = agent_data.get("name", "")
            if aname and aname in ws.agents:
                spec = ws.agents[aname]
                if "mode" in agent_data:
                    spec.mode = agent_data["mode"]
                if "model" in agent_data:
                    spec.model = agent_data["model"]
                if "system_prompt" in agent_data:
                    spec.system_prompt = agent_data["system_prompt"]
                if "tools" in agent_data:
                    spec.tools = agent_data["tools"]
                if "skills" in agent_data:
                    spec.skills = agent_data.get("skills", [])
                if "permissions" in agent_data:
                    perm = agent_data["permissions"]
                    spec.permissions.filesystem.write = (
                        ["workspace"] if perm.get("file_write") else []
                    )
                    spec.permissions.shell.exec = perm.get("shell_exec", False)
                    spec.permissions.subagent.spawn = perm.get("subagent_spawn", False)

        # Write guide file
        guide_content = data.get("guide_content", "")
        if guide_content:
            guide_path = ws.workspace / "GUIDE.md"
            guide_path.parent.mkdir(parents=True, exist_ok=True)
            guide_path.write_text(guide_content, "utf-8")
            for a in ws.agents.values():
                a.guide_file = "GUIDE.md"

        # Register workflows
        from factory.workflow.models import WorkflowTemplate, WorkflowNode
        for wf_data in data["workflows"]:
            nodes = [WorkflowNode.from_dict(n) for n in wf_data.get("nodes", [])]
            tmpl = WorkflowTemplate(
                name=wf_data["name"],
                description=wf_data.get("description", ""),
                workspace=name,
                nodes=nodes,
            )
            if self.org.workflow_store:
                self.org.workflow_store.save(tmpl)

        # Import chain if present
        if data.get("chain"):
            try:
                from factory.workflow.chain import Chain, ChainStore
                cs = ChainStore()
                chain = Chain.from_dict(data["chain"])
                cs.save(chain)
            except Exception as exc:
                logger.warning("Failed to import chain during package import: %s", exc)
                if result is not None:
                    result.setdefault("skipped", []).append("chain")

        # Copy tools
        for tool_file in data.get("tools", []):
            tools_dir = ws.workspace / "tools"
            tools_dir.mkdir(parents=True, exist_ok=True)
            src = Path(pkg_dir) / "tools" / tool_file
            if src.exists():
                shutil = __import__("shutil")
                shutil.copy(src, tools_dir / tool_file)

        # Persist to org.yaml
        self._persist_org()

        return {
            "workspace": name,
            "agents": len(data["agents"]),
            "workflows": len(data["workflows"]),
            "has_guide": bool(guide_content),
            "has_chain": data.get("chain") is not None,
        }

    def remove_workspace(self, name: str) -> dict[str, Any] | None:
        """Remove a workspace completely.

        Deletes: workspace, agents, workflows, kanban board, workspace directory.
        """
        ws = self.get(name)
        if ws is None:
            return None

        result: dict[str, Any] = {
            "workspace": name,
            "agents_removed": len(ws.agents),
            "workflows_removed": 0,
            "kanban_removed": False,
            "directory_removed": False,
        }

        # Remove workflows
        if self.org.workflow_store:
            for wf_info in list(self.org.workflow_store.list_all()):
                if wf_info.get("workspace") == name:
                    self.org.workflow_store.delete(wf_info["name"])
                    result["workflows_removed"] += 1

        # Remove kanban board
        if self.kanban_store:
            board = self.kanban_store.get_board_by_name(name, name)
            if board:
                self.kanban_store.delete_board(board["id"])
                result["kanban_removed"] = True

        # Remove workspace directory
        import shutil
        ws_dir = Path(ws.workspace).resolve()
        workspaces_root = Path("workspaces").resolve()
        if not str(ws_dir).startswith(str(workspaces_root)):
            raise ValueError(f"Refusing to remove directory outside workspaces: {ws_dir}")
        if ws_dir.exists():
            shutil.rmtree(ws_dir)
            result["directory_removed"] = True

        # Remove from org
        self.org.workshops = [w for w in self.org.workshops if w.name != name]

        # Persist to org.yaml
        self._persist_org()

        return result

    def _persist_org(self) -> None:
        """Write current org state back to org.yaml."""
        import yaml as _yaml
        config_path = Path("config/org.yaml")
        if not config_path.exists():
            return
        with open(config_path, "r+") as f:
            fcntl.flock(f, fcntl.LOCK_EX)
            try:
                data = _yaml.safe_load(f) or {}
                depts: list[dict[str, Any]] = []
                for ws in self.org.workshops:
                    depts.append({
                        "name": ws.name,
                        "type": "custom",
                        "workspace": str(ws.workspace),
                        "agents": [
                            {
                                "name": a.name,
                                "mode": getattr(a, "mode", "super"),
                                "model": a.model,
                                "tools": a.tools if a.tools else [],
                                "system_prompt": getattr(a, "system_prompt", ""),
                                "guide_file": getattr(a, "guide_file", ""),
                                "skills": getattr(a, "skills", []),
                                "permissions": {
                                    "file_write": len(a.permissions.filesystem.write) > 0,
                                    "shell_exec": a.permissions.shell.exec,
                                    "subagent_spawn": a.permissions.subagent.spawn,
                                },
                            }
                            for a in ws.agents.values()
                        ],
                        "workflow": {"name": ws.workflow_name},
                    })
                data["departments"] = depts
                f.seek(0)
                f.truncate()
                _yaml.dump(data, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
            finally:
                fcntl.flock(f, fcntl.LOCK_UN)

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class SessionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    MERGED = "merged"


class SessionType(str, Enum):
    ROOT = "root"
    SPAWN = "spawn"
    FORK = "fork"
    BTW = "btw"


@dataclass
class SessionNode:
    session_id: str
    parent_id: str = ""
    session_type: SessionType = SessionType.ROOT
    workshop_name: str = ""
    worktree_id: str = ""
    task: str = ""
    status: SessionStatus = SessionStatus.PENDING
    agent_name: str = ""
    model: str = ""
    output: str = ""
    error: str = ""
    git_sha: str = ""
    turns: int = 0
    cost_usd: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "parent_id": self.parent_id,
            "session_type": self.session_type.value,
            "workshop_name": self.workshop_name,
            "worktree_id": self.worktree_id,
            "task": self.task,
            "status": self.status.value,
            "agent_name": self.agent_name,
            "model": self.model,
            "output": self.output,
            "error": self.error,
            "git_sha": self.git_sha,
            "turns": self.turns,
            "cost_usd": self.cost_usd,
            "tools_used": self.tools_used,
            "messages": self.messages,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionNode:
        return cls(
            session_id=data["session_id"],
            parent_id=data.get("parent_id", ""),
            session_type=SessionType(data.get("session_type", "root")),
            workshop_name=data.get("workshop_name", ""),
            worktree_id=data.get("worktree_id", ""),
            task=data.get("task", ""),
            status=SessionStatus(data.get("status", "pending")),
            agent_name=data.get("agent_name", ""),
            model=data.get("model", ""),
            output=data.get("output", ""),
            error=data.get("error", ""),
            git_sha=data.get("git_sha", ""),
            turns=data.get("turns", 0),
            cost_usd=data.get("cost_usd", 0.0),
            tools_used=data.get("tools_used", []),
            messages=data.get("messages", []),
        )


class SessionTree:
    """Tree-structured session history with fork, spawn, and btw operations.

    Auto-persists to ~/.factory/sessions/{workshop}.json on every mutation.
    Auto-loads on init.
    """

    def __init__(self, workshop_name: str = "default"):
        self._workshop = workshop_name
        self._nodes: dict[str, SessionNode] = {}
        self._storage = Path(
            os.environ.get("SESSION_TREE_DIR", str(Path("~/.factory/sessions").expanduser()))
        ) / f"{workshop_name}.json"
        self._load()

    def _save(self) -> None:
        self._storage.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._storage.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), ensure_ascii=False, indent=2))
        os.replace(tmp, self._storage)

    def _load(self) -> None:
        if self._storage.exists():
            try:
                data = json.loads(self._storage.read_text())
                for node_data in data.get("nodes", []):
                    self._nodes[node_data["session_id"]] = SessionNode.from_dict(node_data)
            except (json.JSONDecodeError, OSError):
                pass

    @property
    def root(self) -> SessionNode | None:
        for node in self._nodes.values():
            if node.session_type == SessionType.ROOT:
                return node
        return None

    def add(self, node: SessionNode) -> None:
        if node.session_id in self._nodes:
            raise ValueError(f"Session {node.session_id} already exists")
        if node.parent_id and node.parent_id not in self._nodes:
            raise ValueError(f"Parent session {node.parent_id} not found")
        self._nodes[node.session_id] = node
        self._save()

    def get(self, session_id: str) -> SessionNode | None:
        return self._nodes.get(session_id)

    def fork(self, source_session_id: str, new_session_id: str, task: str) -> SessionNode:
        source = self._nodes[source_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=source.parent_id,
            session_type=SessionType.FORK,
            workshop_name=source.workshop_name,
            task=task,
            agent_name=source.agent_name,
            model=source.model,
        )
        self.add(node)
        return node

    def spawn(self, parent_session_id: str, new_session_id: str, task: str) -> SessionNode:
        parent = self._nodes[parent_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=parent_session_id,
            session_type=SessionType.SPAWN,
            workshop_name=parent.workshop_name,
            task=task,
            agent_name=parent.agent_name,
        )
        self.add(node)
        return node

    def btw(
        self,
        target_session_id: str,
        new_session_id: str,
        task: str,
    ) -> SessionNode:
        """Create a bypass inquiry session.

        Does NOT block the target session. Auto-callbacks result
        when complete (Phase 3: async callback queue).
        """
        target = self._nodes[target_session_id]
        node = SessionNode(
            session_id=new_session_id,
            parent_id=target_session_id,
            session_type=SessionType.BTW,
            workshop_name=target.workshop_name,
            task=task,
            agent_name=target.agent_name,
        )
        self.add(node)
        return node

    def children_of(self, session_id: str) -> list[SessionNode]:
        return [n for n in self._nodes.values() if n.parent_id == session_id]

    def siblings_of(self, session_id: str) -> list[SessionNode]:
        node = self._nodes.get(session_id)
        if not node:
            return []
        return [
            n for n in self._nodes.values()
            if n.parent_id == node.parent_id and n.session_id != session_id
        ]

    def ancestors_of(self, session_id: str) -> list[SessionNode]:
        result: list[SessionNode] = []
        current = self._nodes.get(session_id)
        while current and current.parent_id:
            parent = self._nodes.get(current.parent_id)
            if parent:
                result.append(parent)
                current = parent
            else:
                break
        result.reverse()
        return result

    def all_nodes(self) -> list[SessionNode]:
        return list(self._nodes.values())

    def to_dict(self) -> dict[str, Any]:
        return {"nodes": [n.to_dict() for n in self._nodes.values()]}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionTree:
        tree = cls(workshop_name=data.get("workshop", "default"))
        for node_data in data.get("nodes", []):
            tree._nodes[node_data["session_id"]] = SessionNode.from_dict(node_data)
        return tree

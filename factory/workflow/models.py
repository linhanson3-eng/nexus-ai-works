"""Workflow domain models — nodes, templates, execution state."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class NodeStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PASSED = "passed"
    FAILED = "failed"
    SKIPPED = "skipped"


class GateType(str, Enum):
    REVIEW = "review"


@dataclass
class WorkflowNode:
    """A single node in a workflow — one agent execution step."""

    id: str
    label: str = ""
    agent_name: str = ""       # agent in the workspace
    prompt: str = ""           # task prompt for this node
    depends_on: list[str] = field(default_factory=list)
    expected_output: str = ""  # description of expected deliverable
    gate: dict[str, str] | None = None  # e.g. {"type": "review"}

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id, "label": self.label, "agent_name": self.agent_name,
            "prompt": self.prompt, "depends_on": self.depends_on,
            "expected_output": self.expected_output,
        }
        if self.gate:
            d["gate"] = self.gate
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            agent_name=data.get("agent_name", ""),
            prompt=data.get("prompt", ""),
            depends_on=data.get("depends_on", []),
            expected_output=data.get("expected_output", ""),
            gate=data.get("gate"),
        )


@dataclass
class WorkflowTemplate:
    """A reusable workflow definition."""

    name: str
    description: str = ""
    workspace: str = ""        # which workspace this template belongs to
    nodes: list[WorkflowNode] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "nodes": [n.to_dict() for n in self.nodes],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTemplate:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            workspace=data.get("workspace", ""),
            nodes=[WorkflowNode.from_dict(n) for n in data.get("nodes", [])],
        )

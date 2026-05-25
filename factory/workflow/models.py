from __future__ import annotations
"""Workflow domain models — nodes, templates, execution state."""


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
    """A single node in a workflow — one execution step."""

    id: str
    label: str = ""
    node_type: str = "agent"   # "agent" | "condition" | "transform"
    agent_name: str = ""       # agent in the workspace (agent node only)
    prompt: str = ""           # task prompt / condition expression / transform code
    depends_on: list[str] = field(default_factory=list)
    expected_output: str = ""
    gate: dict[str, str] | None = None  # e.g. {"type": "review"}
    timeout_seconds: int = 300  # per-node timeout, 0 = no limit
    notes: str = ""            # node documentation notes
    retry_on_fail: bool = False
    continue_on_fail: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": self.id, "label": self.label, "node_type": self.node_type,
            "agent_name": self.agent_name, "prompt": self.prompt,
            "depends_on": self.depends_on, "expected_output": self.expected_output,
            "timeout_seconds": self.timeout_seconds,
            "notes": self.notes or "", "retry_on_fail": self.retry_on_fail,
            "continue_on_fail": self.continue_on_fail,
        }
        if self.gate:
            d["gate"] = self.gate
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowNode:
        return cls(
            id=data["id"],
            label=data.get("label", ""),
            node_type=data.get("node_type", "agent"),
            agent_name=data.get("agent_name", ""),
            prompt=data.get("prompt", ""),
            depends_on=data.get("depends_on", []),
            expected_output=data.get("expected_output", ""),
            gate=data.get("gate"),
            timeout_seconds=data.get("timeout_seconds", 300),
            notes=data.get("notes", ""),
            retry_on_fail=data.get("retry_on_fail", False),
            continue_on_fail=data.get("continue_on_fail", False),
        )


@dataclass
class WorkflowTemplate:
    """A reusable workflow definition."""

    name: str
    description: str = ""
    workspace: str = ""        # which workspace this template belongs to
    nodes: list[WorkflowNode] = field(default_factory=list)
    max_total_seconds: int = 0  # workflow-level timeout, 0 = no limit

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "workspace": self.workspace,
            "nodes": [n.to_dict() for n in self.nodes],
            "max_total_seconds": self.max_total_seconds,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkflowTemplate:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            workspace=data.get("workspace", ""),
            nodes=[WorkflowNode.from_dict(n) for n in data.get("nodes", [])],
            max_total_seconds=data.get("max_total_seconds", 0),
        )

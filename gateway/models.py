"""Pydantic request/response models for the Gateway API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Board ──

class CreateBoardRequest(BaseModel):
    name: str = "Untitled Board"
    workshop_name: str = ""
    description: str = ""


class BoardResponse(BaseModel):
    id: str
    name: str
    workshop_name: str
    description: str
    created_at: str
    updated_at: str


# ── List ──

class CreateListRequest(BaseModel):
    name: str = "Untitled List"
    position: int = -1
    color: str = ""


class MoveListRequest(BaseModel):
    position: int = 0


class ListResponse(BaseModel):
    id: str
    board_id: str
    name: str
    position: int
    color: str


# ── Card ──

class CreateCardRequest(BaseModel):
    title: str = ""
    description: str = ""
    position: int = -1
    labels: list[str] | None = None
    assignee: str = ""
    due_date: str | None = None
    source_agent: str = ""
    source_task_id: str = ""
    task_status: str = "todo"


class UpdateCardRequest(BaseModel):
    title: str | None = None
    description: str | None = None
    labels: list[str] | None = None
    assignee: str | None = None
    due_date: str | None = None
    task_status: str | None = None


class MoveCardRequest(BaseModel):
    list_id: str
    position: int = -1


class UpsertCardRequest(BaseModel):
    agent_name: str = ""
    task_id: str = ""
    title: str = ""
    task_status: str = "todo"
    list_id: str = ""


# ── Workshop ──

class CreateWorkshopRequest(BaseModel):
    name: str
    workspace: str = ""
    agent_names: list[str] = Field(default_factory=list)
    workflow_name: str = "simple"
    model: str = ""


class CreateAgentRequest(BaseModel):
    name: str
    mode: str = "super"
    model: str = ""
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    guide_file: str = ""
    guide_content: str = ""
    skills: list[str] = Field(default_factory=list)
    permissions: dict[str, Any] = Field(default_factory=dict)


class UpdateAgentRequest(BaseModel):
    mode: str | None = None
    model: str | None = None
    tools: list[str] | None = None
    system_prompt: str | None = None
    guide_file: str | None = None
    guide_content: str = ""
    skills: list[str] | None = None
    permissions: dict[str, Any] | None = None


class RunWorkflowRequest(BaseModel):
    workflow: str = ""
    task: str


# ── Workflow ──

class WorkflowNodeSpec(BaseModel):
    id: str
    agent: str = ""
    task: str = ""
    depends_on: list[str] = Field(default_factory=list)


class SaveWorkflowRequest(BaseModel):
    name: str
    description: str = ""
    workspace: str = ""
    nodes: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteWorkflowRequest(BaseModel):
    task: str
    workshop: str = ""


# ── Chain ──

class ChainStepSpec(BaseModel):
    workshop: str
    task: str = ""


class SaveChainRequest(BaseModel):
    name: str
    description: str = ""
    steps: list[dict[str, Any]] = Field(default_factory=list)


class ExecuteChainRequest(BaseModel):
    task: str


# ── Agent ──

class AgentRunRequest(BaseModel):
    task: str
    workshop: str = ""


class AgentChatRequest(BaseModel):
    message: str = ""


class AgentAnswerRequest(BaseModel):
    request_id: str
    answer: str = ""


# ── Settings ──

class SaveProviderRequest(BaseModel):
    name: str
    provider_type: str | None = None
    base_url: str | None = None
    api_key: str | None = None
    models: list[str] | None = None


class SaveToolRequest(BaseModel):
    name: str
    description: str | None = None
    category: str | None = None
    install_command: str | None = None


class SavePluginRequest(BaseModel):
    name: str
    enabled: bool | None = None


class SaveSearchRequest(BaseModel):
    tavily_api_key: str | None = None
    brave_api_key: str | None = None
    searxng_base_url: str | None = None
    active_provider: str | None = None
    deep_search_enabled: bool | None = None
    max_results: int | None = None

"""工厂配置 Pydantic 模型。"""

from enum import Enum
from pathlib import Path
from typing import Any, Union

from pydantic import BaseModel, Field, field_validator


class AgentType(str, Enum):
    SUPER = "super"
    NORMAL = "normal"


class FilesystemPermission(BaseModel):
    read: list[str] = Field(default_factory=lambda: ["workspace"])
    write: list[str] = Field(default_factory=lambda: ["workspace"])
    forbidden: list[str] = Field(
        default_factory=lambda: ["vendor", "node_modules", ".git", "__pycache__", ".venv"]
    )


class ShellPermission(BaseModel):
    exec: bool = False
    network: bool = False
    forbidden_patterns: list[str] = Field(default_factory=lambda: ["rm -rf /", "sudo"])


class SubagentPermission(BaseModel):
    spawn: bool = False
    max: int = 3


class WarehousePermission(BaseModel):
    read: list[str] = Field(default_factory=lambda: ["all"])
    write: list[str] = []


class SelfPermission(BaseModel):
    modify_prompt: bool = False
    install_skill: bool = False


class AgentPermissions(BaseModel):
    filesystem: FilesystemPermission = Field(default_factory=FilesystemPermission)
    shell: ShellPermission = Field(default_factory=ShellPermission)
    subagent: SubagentPermission = Field(default_factory=SubagentPermission)
    warehouse: WarehousePermission = Field(default_factory=WarehousePermission)
    self: SelfPermission = Field(default_factory=SelfPermission)


class AgentSpec(BaseModel):
    name: str
    template: str = "super"  # 模板名：super/reviewer/analyst/writer
    type: AgentType = AgentType.SUPER  # 类型由模板决定
    model: str = "anthropic/claude-sonnet-4-6"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)

    @field_validator("tools", mode="before")
    @classmethod
    def normalize_tools(cls, v: object) -> list[str]:
        """'all' → 空列表（Agent 加载时展开为全部工具）"""
        if v == "all":
            return []
        if isinstance(v, str):
            return [v]
        if isinstance(v, list):
            return v
        return []

    @property
    def tools_all(self) -> bool:
        return len(self.tools) == 0


class WorkflowSpec(BaseModel):
    name: str
    stages: list[dict[str, Any]] = Field(default_factory=list)


class DepartmentSpec(BaseModel):
    name: str
    type: str = "custom"
    workspace: str = ""
    agents: list[AgentSpec] = Field(default_factory=list)
    workflow: WorkflowSpec = Field(default_factory=WorkflowSpec)


class ChannelSpec(BaseModel):
    name: str
    enabled: bool = False
    config: dict[str, Any] = Field(default_factory=dict)


class WarehouseSpec(BaseModel):
    path: str = ""


class OrgSpec(BaseModel):
    departments: list[DepartmentSpec] = Field(default_factory=list)
    warehouse: WarehouseSpec = Field(default_factory=WarehouseSpec)
    channels: list[ChannelSpec] = Field(default_factory=list)

"""工厂配置 Pydantic 模型。"""

from typing import Any

from pydantic import BaseModel, Field, field_validator


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


class BudgetSpec(BaseModel):
    """Token / cost / call budget per agent execution."""

    max_total_tokens: int = 1_500_000
    max_total_cost_usd: float = 15.0
    max_tool_calls: int = 150
    max_model_calls: int = 60
    max_session_turns: int = 60


class RoleModelSpec(BaseModel):
    """Per-role model preferences."""

    default: str = ""
    budget_work: str = ""


class RolePermissionsSpec(BaseModel):
    """Role-level permission flags (simplified view)."""

    shell_exec: bool = False
    file_write: bool = False
    subagent_spawn: bool = False


class RoleSpec(BaseModel):
    """角色身份配置 — 定义 Agent 的角色提示词、默认预算和权限。

    角色配置文件放在 config/roles/*.yaml，模板通过 ``role:`` 字段引用。
    模板字段覆盖角色默认值。
    """

    name: str
    description: str = ""
    append_prompt: str = ""
    model: RoleModelSpec = Field(default_factory=RoleModelSpec)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)
    permissions: RolePermissionsSpec = Field(default_factory=RolePermissionsSpec)

    def to_permissions(self) -> AgentPermissions:
        """Convert simplified role permissions to full AgentPermissions."""
        return AgentPermissions(
            filesystem=FilesystemPermission(
                read=["workspace"],
                write=["workspace"] if self.permissions.file_write else [],
            ),
            shell=ShellPermission(exec=self.permissions.shell_exec),
            subagent=SubagentPermission(
                spawn=self.permissions.subagent_spawn,
                max=5 if self.permissions.subagent_spawn else 0,
            ),
            warehouse=WarehousePermission(),
            self=SelfPermission(),
        )


class AgentSpec(BaseModel):
    name: str
    mode: str = "super"  # "super" | "normal" — drives tools + subagent defaults
    template: str = ""
    role: str = ""  # references config/roles/<role>.yaml
    type: str = ""
    model: str = "anthropic/claude-sonnet-4-6"
    tools: list[str] = Field(default_factory=list)
    system_prompt: str = ""
    guide_file: str = ""  # path to agent guide/prompt file
    skills: list[str] = Field(default_factory=list)  # skill names to load
    permissions: AgentPermissions = Field(default_factory=AgentPermissions)
    budget: BudgetSpec = Field(default_factory=BudgetSpec)

    def model_post_init(self, __context: object) -> None:
        """Apply mode-driven defaults for tools only when not explicitly set."""
        if self.mode == "normal" and not self.tools:
            self.tools = ["think", "search", "read_file"]

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

    @property
    def is_super(self) -> bool:
        return self.mode == "super"


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

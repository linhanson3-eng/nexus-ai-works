"""组织架构引擎。

读 org.yaml → 创建车间 → 分配 workspace → 实例化 Agent。
"""

from pathlib import Path

import yaml

from config.schema import AgentSpec, DepartmentSpec, OrgSpec
from factory.template import TemplateLibrary
from factory.warehouse import Warehouse
from factory.workflow import WorkflowLibrary


class Workshop:
    """一个车间 = 隔离 workspace + Agent 集合 + 工作流引擎。"""

    def __init__(self, spec: DepartmentSpec, templates: TemplateLibrary, warehouse: Warehouse):
        self.spec = spec
        self.name = spec.name
        self.workspace = Path(spec.workspace).expanduser().resolve()
        self.warehouse = warehouse
        self.agents: dict[str, AgentSpec] = {}
        self.workflow_name = spec.workflow.name if spec.workflow else "simple"

        self._templates = templates
        self._setup_workspace()
        self._spawn_agents()

    def _setup_workspace(self) -> None:
        """创建隔离车间：目录结构 + 禁止目录。"""
        self.workspace.mkdir(parents=True, exist_ok=True)
        # 车间 src 目录
        (self.workspace / "src").mkdir(exist_ok=True)
        # Agent 记忆目录
        (self.workspace / "memory").mkdir(exist_ok=True)

    def _spawn_agents(self) -> None:
        """根据 spec 实例化所有 Agent。"""
        for agent_cfg in self.spec.agents:
            tmpl_name = getattr(agent_cfg, "template", "super") or "super"
            agent_spec = self._templates.create_agent_spec(
                template_name=tmpl_name,
                name=agent_cfg.name,
                model=agent_cfg.model,
            )
            # 限制写权限到本车间
            agent_spec.permissions.warehouse.write = [self.name]
            self.agents[agent_spec.name] = agent_spec

    def status(self) -> dict:
        """车间状态。"""
        return {
            "name": self.name,
            "workspace": str(self.workspace),
            "agents": {
                name: {
                    "type": spec.type.value,
                    "model": spec.model,
                    "tools": spec.tools,
                }
                for name, spec in self.agents.items()
            },
            "workflow": self.workflow_name,
        }

    def agent_count(self) -> int:
        return len(self.agents)

    def super_agents(self) -> list[str]:
        return [name for name, spec in self.agents.items() if spec.type.value == "super"]


class OrgEngine:
    """工厂组织架构引擎。

    从 org.yaml 加载组织架构，创建所有车间。
    """

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.spec: OrgSpec = self._load()
        self.warehouse = Warehouse(self.spec.warehouse.path)
        self.templates = TemplateLibrary()
        self.workflows = WorkflowLibrary()
        self.workshops: list[Workshop] = []

    def _load(self) -> OrgSpec:
        """加载并验证 org.yaml。"""
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        return OrgSpec(**data)

    def create_all(self) -> list[Workshop]:
        """创建所有车间。"""
        self.workshops = []
        for dept_spec in self.spec.departments:
            # 默认 workspace 路径
            if not dept_spec.workspace:
                dept_spec.workspace = f"workspaces/{dept_spec.name}"

            ws = Workshop(dept_spec, self.templates, self.warehouse)
            self.workshops.append(ws)
        return self.workshops

    def create_one(self, dept_spec: DepartmentSpec) -> Workshop:
        """动态创建一个车间（无需重启）。"""
        if not dept_spec.workspace:
            dept_spec.workspace = f"workspaces/{dept_spec.name}"
        ws = Workshop(dept_spec, self.templates, self.warehouse)
        self.workshops.append(ws)
        return ws

    def status(self) -> dict:
        """工厂整体状态。"""
        return {
            "departments": [ws.status() for ws in self.workshops],
            "total_agents": sum(ws.agent_count() for ws in self.workshops),
            "super_agents": sum(len(ws.super_agents()) for ws in self.workshops),
            "warehouse": str(self.warehouse.root),
            "warehouse_products": self.warehouse.index(),
        }

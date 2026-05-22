"""组织架构引擎。

读 org.yaml → 创建工作区 → 分配 workspace → 实例化 Agent。
"""

from pathlib import Path

import yaml

from config.schema import AgentSpec, DepartmentSpec, OrgSpec
from factory.warehouse import Warehouse
from factory.workflow import WorkflowStore


class Workshop:
    """一个工作区 = 隔离 workspace + Agent 集合 + 工作流引擎。"""

    def __init__(self, spec: DepartmentSpec, warehouse: Warehouse):
        self.spec = spec
        self.name = spec.name
        self.workspace = Path(spec.workspace).expanduser().resolve()
        self.warehouse = warehouse
        self.agents: dict[str, AgentSpec] = {}
        self.workflow_name = spec.workflow.name if spec.workflow else "simple"

        self._setup_workspace()
        self._spawn_agents()

    def _setup_workspace(self) -> None:
        """创建隔离工作区：目录结构 + 禁止目录。"""
        self.workspace.mkdir(parents=True, exist_ok=True)
        # 工作区 src 目录
        (self.workspace / "src").mkdir(exist_ok=True)
        # Agent 记忆目录
        (self.workspace / "memory").mkdir(exist_ok=True)

    def _spawn_agents(self) -> None:
        """根据 spec 实例化所有 Agent。"""
        for agent_cfg in self.spec.agents:
            agent_spec = AgentSpec(
                name=agent_cfg.name,
                mode=agent_cfg.mode,
                model=agent_cfg.model,
                tools=agent_cfg.tools,
                system_prompt=agent_cfg.system_prompt,
                guide_file=agent_cfg.guide_file,
                skills=agent_cfg.skills,
                permissions=agent_cfg.permissions,
                budget=agent_cfg.budget,
                template=agent_cfg.template,
                role=agent_cfg.role,
            )
            agent_spec.permissions.warehouse.write = [self.name]
            self.agents[agent_spec.name] = agent_spec

    def status(self) -> dict:
        """工作区状态。"""
        return {
            "name": self.name,
            "workspace": str(self.workspace),
            "agents": {
                name: {
                    "type": spec.type,
                    "model": spec.model,
                    "tools": spec.tools,
                }
                for name, spec in self.agents.items()
            },
            "workflow": self.workflow_name,
        }

    def agent_count(self) -> int:
        return len(self.agents)


class OrgEngine:
    """工厂组织架构引擎。

    从 org.yaml 加载组织架构，创建所有工作区。
    """

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self.spec: OrgSpec = self._load()
        self.warehouse = Warehouse(self.spec.warehouse.path)
        self.workflow_store = WorkflowStore()
        self.workshops: list[Workshop] = []

    def _load(self) -> OrgSpec:
        """加载并验证 org.yaml。"""
        with open(self.config_path) as f:
            data = yaml.safe_load(f)
        return OrgSpec(**data)

    def create_all(self) -> list[Workshop]:
        """创建所有工作区。"""
        self.workshops = []
        for dept_spec in self.spec.departments:
            # 默认 workspace 路径
            if not dept_spec.workspace:
                dept_spec.workspace = f"workspaces/{dept_spec.name}"

            ws = Workshop(dept_spec, self.warehouse)
            self.workshops.append(ws)
        return self.workshops

    def create_one(self, dept_spec: DepartmentSpec) -> Workshop:
        """动态创建一个工作区（无需重启）。"""
        if not dept_spec.workspace:
            dept_spec.workspace = f"workspaces/{dept_spec.name}"
        ws = Workshop(dept_spec, self.warehouse)
        self.workshops.append(ws)
        return ws

    def status(self) -> dict:
        """工厂整体状态。"""
        return {
            "departments": [ws.status() for ws in self.workshops],
            "total_agents": sum(ws.agent_count() for ws in self.workshops),
            "warehouse": str(self.warehouse.root),
            "warehouse_products": self.warehouse.index(),
        }

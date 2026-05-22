"""Agent 模板系统。

从用户自定义模板 YAML 实例化 Agent。模板放在 templates/ 目录下。
模板通过 ``role:`` 字段引用 config/roles/*.yaml 角色配置。
角色提供身份提示词和默认值，模板字段覆盖角色默认值。
"""

from pathlib import Path

import yaml

from config.schema import AgentPermissions, AgentSpec, BudgetSpec
from factory.role_loader import RoleLoader


class AgentTemplateInstance:
    """从模板文件解析出的 Agent 配置。"""

    def __init__(self, data: dict):
        self.name = data["name"]
        self.description = data.get("description", "")
        self.type = data.get("type", "")
        self.model = data.get("model", "anthropic/claude-sonnet-4-6")
        self.tools = data.get("tools", [])
        self.system_prompt = data.get("system_prompt", "")
        self.permissions = AgentPermissions(**data.get("permissions", {}))
        self.role = data.get("role", "")
        self.budget = BudgetSpec(**data.get("budget", {})) if "budget" in data else BudgetSpec()

    def to_spec(self, **overrides) -> AgentSpec:
        """将模板 + 用户覆盖 → AgentSpec，自动解析角色配置。"""
        model = overrides.pop("model", self.model)
        name = overrides.pop("name", self.name)

        spec = AgentSpec(
            name=name,
            type=self.type,
            role=self.role,
            model=model,
            tools=self.tools,
            system_prompt=self.system_prompt,
            permissions=self.permissions,
            budget=self.budget,
        )

        if self.role:
            loader = RoleLoader()
            spec = loader.apply_role(spec)

        return spec


class TemplateLibrary:
    """Agent 模板库。

    从 templates/ 目录加载用户自定义模板 (*.yaml)。
    """

    def __init__(self, templates_dir: Path | None = None):
        self._dir = templates_dir
        self._custom: dict[str, AgentTemplateInstance] = {}
        if self._dir and self._dir.exists():
            self._load_custom()

    def _load_custom(self) -> None:
        """加载用户自定义模板。"""
        assert self._dir is not None
        for f in self._dir.glob("*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            instance = AgentTemplateInstance(data)
            self._custom[instance.name] = instance

    def get(self, name: str) -> AgentTemplateInstance | None:
        """获取模板。"""
        return self._custom.get(name)

    def list_all(self) -> list[dict[str, str]]:
        result = []
        for name, tmpl in self._custom.items():
            result.append(
                {"name": name, "type": tmpl.type, "description": tmpl.description, "source": "custom"}
            )
        return result

    @staticmethod
    def create_agent_spec(template_name: str, **overrides) -> AgentSpec:
        """快捷方法：从模板名直接创建 AgentSpec。

        如果模板不存在，返回基于 overrides 的 bare AgentSpec。
        """
        lib = TemplateLibrary()
        tmpl = lib.get(template_name)
        if tmpl is None:
            return AgentSpec(
                name=overrides.pop("name", template_name),
                type=overrides.pop("type", ""),
                **overrides,
            )
        return tmpl.to_spec(**overrides)

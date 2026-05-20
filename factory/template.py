"""Agent 模板系统。

从模板 YAML 实例化 Agent。内置 super / reviewer / analyst / writer，
支持用户自定义模板。
"""

from pathlib import Path

import yaml

from config.schema import AgentPermissions, AgentSpec, AgentType


class AgentTemplateInstance:
    """从模板文件解析出的 Agent 配置。"""

    def __init__(self, data: dict):
        self.name = data["name"]
        self.description = data.get("description", "")
        self.type = AgentType(data.get("type", "normal"))
        self.model = data.get("model", "anthropic/claude-sonnet-4-6")
        self.tools = data.get("tools", [])
        self.system_prompt = data.get("system_prompt", "")
        self.permissions = AgentPermissions(**data.get("permissions", {}))

    def to_spec(self, **overrides) -> AgentSpec:
        """将模板 + 用户覆盖 → AgentSpec。"""
        model = overrides.pop("model", self.model)
        name = overrides.pop("name", self.name)
        return AgentSpec(
            name=name,
            type=self.type,
            model=model,
            tools=self.tools,
            system_prompt=self.system_prompt,
            permissions=self.permissions,
        )


class TemplateLibrary:
    """Agent 模板库。

    内置模板：super / reviewer / analyst / writer
    自定义模板：templates/ 目录下 *.yaml
    """

    BUILTIN_NAMES = {"super", "reviewer", "analyst", "writer"}

    def __init__(self, templates_dir: Path | None = None):
        self._dir = templates_dir
        self._builtin: dict[str, AgentTemplateInstance] = {}
        self._custom: dict[str, AgentTemplateInstance] = {}
        self._load_builtin()
        if self._dir and self._dir.exists():
            self._load_custom()

    def _load_builtin(self) -> None:
        """加载内置模板。"""
        builtin_dir = Path(__file__).resolve().parent.parent / "templates"
        for name in self.BUILTIN_NAMES:
            path = builtin_dir / f"{name}.yaml"
            if path.exists():
                with open(path) as f:
                    data = yaml.safe_load(f)
                self._builtin[name] = AgentTemplateInstance(data)

    def _load_custom(self) -> None:
        """加载用户自定义模板。"""
        assert self._dir is not None
        for f in self._dir.glob("*.yaml"):
            with open(f) as fh:
                data = yaml.safe_load(fh)
            instance = AgentTemplateInstance(data)
            self._custom[instance.name] = instance

    def get(self, name: str) -> AgentTemplateInstance | None:
        """获取模板。自定义优先于内置。"""
        return self._custom.get(name) or self._builtin.get(name)

    def list_all(self) -> list[dict[str, str]]:
        result = []
        for name, tmpl in {**self._builtin, **self._custom}.items():
            source = "custom" if name in self._custom else "builtin"
            result.append(
                {"name": name, "type": tmpl.type.value, "description": tmpl.description, "source": source}
            )
        return result

    @staticmethod
    def create_agent_spec(template_name: str, **overrides) -> AgentSpec:
        """快捷方法：从模板名直接创建 AgentSpec。"""
        lib = TemplateLibrary()
        tmpl = lib.get(template_name)
        if tmpl is None:
            raise ValueError(f"模板不存在: {template_name}。可用模板: {[t['name'] for t in lib.list_all()]}")
        return tmpl.to_spec(**overrides)

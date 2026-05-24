from __future__ import annotations

"""角色配置加载器 — 从 config/roles/*.yaml 加载角色身份。

角色配置提供 Agent 的身份提示词、默认预算和权限。
模板通过 ``role:`` 字段引用角色，模板字段覆盖角色默认值。
"""


import logging
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

from config.schema import AgentPermissions, AgentSpec, BudgetSpec, RoleSpec


class RoleLoader:
    """加载和解析角色配置。

    用法:
        loader = RoleLoader()
        role = loader.get("developer")
        spec = loader.apply_role(agent_spec, role)
    """

    def __init__(self, roles_dir: str | Path | None = None):
        if roles_dir is None:
            roles_dir = Path(__file__).resolve().parent.parent / "config" / "roles"
        self._dir = Path(roles_dir)
        self._cache: dict[str, RoleSpec] = {}

    def get(self, name: str) -> RoleSpec | None:
        """Load a role by name from config/roles/<name>.yaml."""
        if name in self._cache:
            return self._cache[name]

        path = self._dir / f"{name}.yaml"
        if not path.exists():
            return None

        try:
            with open(path) as f:
                data = yaml.safe_load(f)
            role = RoleSpec(**data)
            self._cache[name] = role
            return role
        except Exception as exc:
            logger.warning("Failed to load role %s: %s", name, exc)
            return None

    def list_all(self) -> list[str]:
        """List available role names."""
        if not self._dir.exists():
            return []
        return [
            p.stem
            for p in self._dir.glob("*.yaml")
            if p.stem != "__init__"
        ]

    def apply_role(self, spec: AgentSpec, role_name: str | None = None) -> AgentSpec:
        """Apply role defaults to an AgentSpec.

        Template fields take precedence over role defaults.
        Role provides: system_prompt prefix, default model, default budget, default permissions.
        """
        name = role_name or spec.role
        if not name:
            return spec

        role = self.get(name)
        if role is None:
            return spec

        return AgentSpec(
            name=spec.name,
            template=spec.template,
            role=name,
            type=spec.type,
            # Model: template overrides role default
            model=spec.model if spec.model else role.model.default,
            tools=spec.tools,
            # System prompt: role append_prompt prefix + template system_prompt
            system_prompt=_merge_prompt(role.append_prompt, spec.system_prompt),
            # Permissions: template overrides role
            permissions=spec.permissions
            if spec.permissions != AgentPermissions()
            else role.to_permissions(),
            # Budget: template overrides role
            budget=spec.budget if spec.budget != BudgetSpec() else role.budget,
        )


def _merge_prompt(role_prompt: str, template_prompt: str) -> str:
    """Merge role identity prompt with template-specific instructions."""
    parts: list[str] = []
    if role_prompt.strip():
        parts.append(role_prompt.strip())
    if template_prompt.strip():
        parts.append(template_prompt.strip())
    return "\n\n".join(parts)
